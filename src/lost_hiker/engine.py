"""Core game loop (Wake → Explore → Camp → Return) for Lost Hiker."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Protocol

from .character import TimedModifier
from .events import Event, EventPool
from .state import GameState, GameStateRepository
from .scenes import SceneCatalog
from .commands import Command, CommandParser
from .seasons import SeasonConfig
from .landmarks import LandmarkCatalog, Landmark
from .runestones import (
    can_repair_runestone,
    has_primitive_mortar,
    apply_physical_repair,
    tune_resonance,
    apply_pulse_alignment,
    get_echo_hint_for_runestone,
    get_echo_repair_reaction,
    is_runestone_fractured,
    load_runestone_definitions,
    initialize_runestone_state,
    mark_runestone_discovered,
    update_quest_state_after_repair,
    get_runestone_at_landmark,
)
from .forest_effects import (
    get_stamina_cost_modifier,
    get_event_category_weights,
    get_max_reliable_depth,
    should_allow_deep_depth_roll,
)
from .forest_memory import (
    init_landmark_memory,
    bump_path_stability,
    ensure_minimum_stability,
    get_known_landmarks_with_stability,
    get_stability_label,
)
from .hunger import (
    update_hunger_at_day_start,
    apply_stamina_cap,
    apply_combined_stamina_cap,
    check_starvation_game_over,
    get_hunger_status_message,
    get_stamina_cap_message,
    get_starvation_game_over_message,
)
from .cooking import CookingCatalog, load_food_items
from .kirin import (
    can_trigger_kirin_intro,
    trigger_kirin_intro,
    get_valid_kirin_destinations,
    can_use_kirin_travel,
    execute_kirin_travel,
)
from .forest_memory import get_path_stability
from .wayfinding import (
    can_use_wayfinding,
    get_valid_wayfinding_destinations,
    execute_wayfinding_teleport,
)
from .encounters import EncounterEngine, load_encounter_definitions
from .rapport import get_rapport_tier
from .npcs import NPCCatalog, load_npc_catalog
from .rare_lore_events import RareLoreEventSystem
from .dialogue import (
    DialogueCatalog,
    load_dialogue_catalog,
    start_dialogue,
    step_dialogue,
    get_current_dialogue_text,
    get_current_dialogue_options,
    DialogueSession,
)
from .echo import (
    is_echo_present_at_glade,
    pet_echo,
    hug_echo,
    boop_echo,
)
from .rapport import get_rapport
from .tea_flavor import enhance_tea_description
from .encounter_outcomes import (
    EncounterOutcome,
    OutcomeContext,
    resolve_encounter_outcome,
)


class UI(Protocol):
    """Interface for user interaction."""

    def heading(self, text: str) -> None: ...

    def echo(self, text: str) -> None: ...

    def menu(self, prompt: str, options: list[str]) -> str: ...

    def prompt(self, prompt: str) -> str: ...

    def set_highlights(self, terms: Iterable[str]) -> None: ...


@dataclass
class EncounterOutcome:
    """Structured result for encounter resolution."""

    flavor: str
    stamina_delta: float = 0.0
    rapport_delta: dict[str, int] = field(default_factory=dict)


@dataclass
class Engine:
    """Coordinates the daily loop."""

    state: GameState
    ui: UI
    repo: GameStateRepository
    events: EventPool
    scenes: SceneCatalog
    creatures: dict[str, dict[str, object]]
    teas: dict[str, dict[str, object]]
    season_config: SeasonConfig
    landmarks: LandmarkCatalog
    cooking: CookingCatalog
    food_items: dict[str, dict[str, str]]
    runestone_defs: dict[str, dict[str, str]] = field(default_factory=dict)
    encounter_engine: EncounterEngine | None = None
    npc_catalog: NPCCatalog = field(default_factory=lambda: NPCCatalog([]))
    dialogue_catalog: DialogueCatalog = field(default_factory=lambda: DialogueCatalog([]))
    rare_lore_events: Optional[RareLoreEventSystem] = field(default=None, init=False)
    _ate_proper_meal_yesterday: bool = field(default=False, init=False)
    _day_start_inventory: list[str] = field(default_factory=list, init=False)
    _day_start_rapport: dict[str, int] = field(default_factory=dict, init=False)
    _transient_extras: dict[str, tuple[str, ...]] = field(
        default_factory=dict, init=False
    )
    _transient_examinables: dict[str, dict[str, str]] = field(
        default_factory=dict, init=False
    )
    _command_parser: CommandParser = field(init=False)

    def __post_init__(self) -> None:
        self._command_parser = CommandParser()
        # Initialize forest memory system
        init_landmark_memory(self.state)
    
    def _get_rare_lore_events(self) -> RareLoreEventSystem | None:
        """Lazy-load rare lore events system."""
        if self.rare_lore_events is None:
            try:
                from . import main
                data_dir, _ = main.resolve_paths()
                self.rare_lore_events = RareLoreEventSystem.load(data_dir, "rare_lore_events.json")
            except Exception:
                self.rare_lore_events = RareLoreEventSystem([])
        return self.rare_lore_events

    def run(self) -> None:
        """Run until the player chooses to exit."""
        # Initialize forest_act1 state on game start
        from .forest_act1 import init_forest_act1_state
        init_forest_act1_state(self.state)
        
        # Resolve belly state on load (Phase 1: safe resolution)
        from .belly_interaction import resolve_belly_on_load
        resolve_belly_on_load(self.state, ui=self.ui)
        
        while self.state.stage == "intro":
            result = self._intro_sequence()
            if result == "quit":
                return
        keep_playing = True
        while keep_playing:
            result = self._run_day()
            if result == "quit":
                keep_playing = False
                continue
            if self.state.stage == "game_over":
                keep_playing = False
                self.ui.echo("Game over.\n")
                continue
            self.repo.save(self.state)
            choice = self.ui.menu("Continue into the next day?", ["yes", "save & quit"])
            if choice == "yes":
                self.state.new_day(self.season_config)
                # Apply Echo vore tension decay on new day
                from .echo_vore import update_echo_vore_tension
                update_echo_vore_tension(self.state, increase=False)
            else:
                keep_playing = False
                self.ui.echo("Game saved. See you soon.\n")

    def _run_day(self) -> str | None:
        self.state.prune_expired_effects()
        # Reset landmark food gathering flags for the new day
        for landmark_id in self.state.landmark_flags:
            if "food_gathered_today" in self.state.landmark_flags[landmark_id]:
                self.state.landmark_flags[landmark_id]["food_gathered_today"] = False
        self._day_start_inventory = list(self.state.inventory)
        self._day_start_rapport = dict(self.state.rapport)
        self._wake_phase()
        
        # Check for belly state first (suspends normal exploration)
        from .belly_interaction import is_belly_active
        if is_belly_active(self.state):
            self._belly_phase()
            return
        
        active_zone = self.state.active_zone or "glade"
        if active_zone == "glade":
            result = self._glade_phase()
            if result == "quit":
                return "quit"
        elif active_zone == "echo_belly":
            self._belly_phase()
        else:
            result = self.explore_zone(active_zone)
            if result == "quit":
                return "quit"

    def _wake_phase(self) -> None:
        self.state.stage = "wake"
        season_name = self.state.get_season_name().title()
        self.ui.heading(f"Day {self.state.day} — {season_name}")
        self.ui.echo(f"Day {self.state.day} of the year. {season_name}.\n")
        
        # Update hunger state at day start
        update_hunger_at_day_start(self.state, self._ate_proper_meal_yesterday)
        self._ate_proper_meal_yesterday = False
        
        # Reset water drinks for new day
        self.state.water_drinks_today = 0
        
        # Reset wayfinding_ready at day start (effect expires if not used)
        self.state.wayfinding_ready = False
        
        # Check for starvation game over
        if check_starvation_game_over(self.state):
            self.ui.echo(get_starvation_game_over_message())
            self.state.stage = "game_over"
            return
        
        # Show hunger status message
        hunger_msg = get_hunger_status_message(self.state.days_without_meal)
        self.ui.echo(f"{hunger_msg}\n")
        
        wake_gain = self.state.character.get_stat(
            "stamina_wake_restore",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        base_stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        # Apply combined rest and hunger caps
        stamina_max, rest_cap, hunger_cap = apply_combined_stamina_cap(
            self.state, base_stamina_max
        )
        
        # Show stamina cap message if applicable
        cap_msg = get_stamina_cap_message(
            self.state.days_without_meal, base_stamina_max, stamina_max, rest_cap, hunger_cap
        )
        if cap_msg:
            self.ui.echo(f"{cap_msg}\n")
        
        # Reset rest_type after using it (it's only for the current day's wake)
        self.state.rest_type = None
        
        if self.state.pending_stamina_floor > 0.0:
            self.state.stamina = max(
                self.state.stamina, min(stamina_max, self.state.pending_stamina_floor)
            )
            self.state.pending_stamina_floor = 0.0
        self.state.stamina = min(stamina_max, self.state.stamina + wake_gain)
        self._process_radio_return()
        self._apply_pending_brews()
        active_zone = self.state.active_zone
        depth_lookup = self.state.zone_depths.get(active_zone, 0)
        if active_zone != "glade" and depth_lookup > 0:
            zone_label = active_zone.replace("_", " ").title()
            self.ui.echo(
                f"You wake {depth_lookup} steps deep in the {zone_label} with "
                f"{self.state.stamina:.0f}/{stamina_max:.0f} stamina.\n"
            )
        else:
            self.ui.echo(
                f"You wake with {self.state.stamina:.0f}/{stamina_max:.0f} stamina, "
                "ready to face the trails again.\n"
            )
        if active_zone == "forest":
            persistent_steps = self.state.zone_steps.get("forest", 0)
            if persistent_steps > 0:
                self.ui.echo(
                    f"Trail memory lingers—{persistent_steps} steps already cut into this stretch.\n"
                )
        
        # Check for automatic Echo belly release at morning (if held overnight)
        if self.state.active_zone == "echo_belly" and self.state.belly_state:
            entry_day = self.state.belly_state.get("entry_day", self.state.day)
            entry_method = self.state.belly_state.get("entry_method", "hug")
            # Boop entries are more likely to be held till morning
            # Release if: held overnight (day changed), or boop entry at dawn
            should_release = False
            if self.state.day > entry_day:
                should_release = True
            elif entry_method == "boop" and self.state.time_of_day == "Dawn":
                # Boop entries: 80% chance to be released at dawn
                should_release = random.random() < 0.8
            
            if should_release:
                from .echo_vore import release_player_from_echo_belly
                self.ui.echo(
                    "As dawn breaks, Echo's warmth shifts around you. "
                    "Slowly, carefully, she releases you back into the Glade.\n"
                )
                release_player_from_echo_belly(self.state, self.ui)
        
        # Check for Kirin intro at Glade after Act I completion
        if active_zone == "glade" and can_trigger_kirin_intro(self.state):
            trigger_kirin_intro(self.state, self.ui, context="glade")

    def _render_glade_view(self) -> None:
        """
        Render the glade view with description and commands.
        
        Clears content and shows:
        - Zone description
        - Act I completion narrative (if applicable)
        - Rare lore events (if applicable)
        - Available commands
        """
        # Clear content and show glade description
        if hasattr(self.ui, 'clear_content'):
            self.ui.clear_content()
        self._describe_zone("glade", depth=0)
        
        # Check for Act I completion narrative when entering Glade
        from .forest_act1 import should_show_completion_narrative
        if should_show_completion_narrative(self.state):
            self.ui.echo(
                "\nAs you return to the Glade, you feel a shift in the air—a sense of calm, of stability. "
                "The forest's pulse feels steadier, the ley-lines humming with restored rhythm. "
                "You've done something important. The way forward feels clearer now.\n"
            )
            from .forest_act1 import mark_completion_acknowledged
            mark_completion_acknowledged(self.state)
        
        # Check for rare lore events when entering Glade (especially at night)
        from .time_of_day import get_time_of_day
        time_of_day = get_time_of_day(self.state)
        if time_of_day.value in ("Night", "Dusk"):
            rare_events = self._get_rare_lore_events()
            if rare_events:
                event = rare_events.check_for_event(self.state, "glade", self.landmarks)
                if event:
                    text = rare_events.trigger_event(event, self.state)
                    self.ui.echo(f"\n{text}\n")
        
        self._set_scene_highlights(zone_id="glade", depth=0, extras=())
        glade_commands = "move, look, ping, brew, camp, status, bag, save, quit, help"
        if is_echo_present_at_glade(self.state):
            glade_commands += ", approach echo"
        if can_use_kirin_travel(self.state):
            glade_commands += ", travel with kirin"
        self.ui.echo(
            f"\nThe Glade is calm. Paths stretch outward. Commands: {glade_commands}.\n"
        )

    def _glade_phase(self) -> str | None:
        self.state.stage = "glade"
        self.state.active_zone = "glade"
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        
        # Render glade view (clears content and shows description)
        self._render_glade_view()
        while True:
            self._set_scene_highlights(zone_id="glade", depth=0, extras=None)
            command = self._prompt_command("Glade command")
            if command is None:
                self._report_invalid_command("glade")
                continue
            outcome = self._dispatch_glade_command(
                command=command, stamina_max=stamina_max
            )
            if outcome == "enter_forest":
                self.explore_zone("forest")
                return
            if outcome == "leave":
                return
            if outcome == "quit":
                return "quit"
            # outcome == "stay": loop continues

    def _belly_phase(self) -> None:
        """Handle belly interaction loop (Phase 1: Non-lethal Shelter/Struggle Loop)."""
        from .belly_interaction import is_belly_active, handle_belly_action, exit_belly_state
        
        if not is_belly_active(self.state):
            # Belly state was cleared, exit
            return
        
        self.state.stage = "belly"
        belly = self.state.belly_state
        creature_id = belly["creature_id"]
        mode = belly["mode"]
        
        # Set zone based on mode
        if mode == "echo":
            self.state.active_zone = "echo_belly"
        else:
            # For predators, keep current zone but mark as in belly
            # The zone will be updated when released
            pass
        
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        
        # Show initial prompt
        creature_data = self.creatures.get(creature_id, {})
        creature_name = creature_data.get("name", creature_id.replace("_", " ").title())
        
        if mode == "echo":
            self._set_scene_highlights(zone_id="echo_belly", depth=0, extras=())
            self.ui.echo(
                "You're inside Echo's belly—warm, dark, and safe. "
                "Commands: soothe, struggle, relax, call, status, bag, help.\n"
            )
        else:
            self.ui.echo(
                f"You're inside the {creature_name}'s belly. "
                "Commands: soothe, struggle, relax, call, status, bag, help.\n"
            )
        
        while True:
            # Check if still in belly
            if not is_belly_active(self.state):
                return
            
            if mode == "echo":
                self._set_scene_highlights(zone_id="echo_belly", depth=0, extras=None)
            
            command = self._prompt_command("Belly command")
            if command is None:
                self._report_invalid_command("belly")
                continue
            
            # Handle standard commands (status, bag, help)
            verb = command.verb
            if verb == "status":
                self._show_notebook(zone_id="belly", stamina_max=stamina_max)
                continue
            elif verb == "bag":
                self._show_field_bag()
                continue
            elif verb == "help":
                self._print_belly_help(mode, creature_name)
                continue
            elif verb == "check sky":
                self.ui.echo("You can't see the sky from in here.\n")
                continue
            
            # Handle belly-specific actions
            action = verb  # soothe, struggle, relax, call
            if action not in ("soothe", "struggle", "relax", "call"):
                self.ui.echo("Unknown action. Try: soothe, struggle, relax, or call.\n")
                continue
            
            # Process action
            should_exit = handle_belly_action(
                self.state,
                action=action,
                ui=self.ui,
                creatures=self.creatures,
            )
            
            if should_exit:
                # Belly interaction ended
                return
            # Continue loop

    def _intro_sequence(self) -> str | None:
        zone_id = "charred_tree_interior"
        if self.state.stage != "intro":
            return
        self.state.active_zone = zone_id
        self.state.zone_depths.setdefault(zone_id, 0)
        self._set_scene_highlights(zone_id=zone_id, depth=0, extras=())
        self.ui.heading("Ashen Hollow")
        self.ui.echo(
            "You come to inside the hollowed heart of a charred portal tree. Commands: look, look at <thing>, leave, bag, status, help.\n"
        )
        while self.state.stage == "intro":
            self._set_scene_highlights(zone_id=zone_id, depth=0, extras=None)
            command = self._prompt_command("Hollow command")
            if command is None:
                self._report_invalid_command(zone_id)
                continue
            action = self._dispatch_intro_command(command)
            if action == "leave":
                self._transition_from_hollow()
                return
            if action == "quit":
                return "quit"
            if action == "stay":
                continue

    def _dispatch_intro_command(self, command: Command) -> str:
        verb = command.verb
        args = command.args
        zone_id = "charred_tree_interior"
        if verb == "look":
            target = self._normalize_target(args)
            if target:
                if self._examine_target(zone_id=zone_id, target=target, depth=0):
                    return "stay"
                self.ui.echo("Ash and ember hide nothing like that here.\n")
                return "stay"
            self._describe_zone(zone_id, depth=0)
            return "stay"
        if verb in {"bag", "status", "help", "check sky"}:
            if verb == "bag":
                self._show_field_bag()
            elif verb == "status":
                self._show_notebook(
                    zone_id=zone_id,
                    stamina_max=self.state.character.get_stat(
                        "stamina_max",
                        timed_modifiers=self.state.timed_modifiers,
                        current_day=self.state.day,
                    ),
                )
            elif verb == "check sky":
                from .sky import get_sky_description
                description = get_sky_description(self.state)
                self.ui.echo(f"{description}\n")
            else:
                lines = [
                    "look — survey the hollow",
                    "look at <thing> — inspect portal scars or your gear",
                    "leave — step into the Glade",
                    "status — review notebook",
                    "bag — check supplies",
                    "save — save your progress",
                    "quit — save and exit the game",
                ]
                self.ui.echo(
                    "Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n"
                )
            return "stay"
        if verb == "ping":
            self.ui.echo(
                "Your radio hisses weakly—Echo is outside, beyond the charred walls.\n"
            )
            return "stay"
        if verb == "leave":
            return "leave"
        if verb == "move":
            direction = args[0] if args else ""
            if direction in {"out", "outside", "glade", "exit"}:
                return "leave"
            self.ui.echo("The hollow only offers one exit—out into the Glade.\n")
            return "stay"
        if verb in {"camp", "return"}:
            self.ui.echo("There's no camp to make inside the burned trunk.\n")
            return "stay"
        if verb == "save":
            self.repo.save(self.state)
            self.ui.echo("Game saved.\n")
            return "stay"
        if verb in {"quit", "exit"}:
            self.repo.save(self.state)
            self.ui.echo("Game saved. See you soon.\n")
            return "quit"
        if verb == "wait":
            self.ui.echo("Ash settles as you catch your breath.\n")
            return "stay"
        self._report_invalid_command("charred_tree_interior")
        return "stay"

    def _transition_from_hollow(self) -> None:
        self.ui.echo(
            "You shoulder your pack and step through the splintered opening into the Glade. "
            "Echo watches from a sunlit stone, radio antennae flickering as they take in your arrival.\n"
        )
        self.state.stage = "wake"
        self.state.active_zone = "glade"
        self._set_scene_highlights(zone_id="glade", depth=0, extras=())

    def _dispatch_glade_command(self, *, command: Command, stamina_max: float) -> str:
        verb = command.verb
        args = command.args
        if verb == "move":
            direction = args[0] if args else ""
            if direction in {"to", "into", "toward"} and len(args) >= 2:
                direction = args[1]
            if not direction or direction in {"forest", "south", "forward", "deeper"}:
                self.ui.echo(
                    "You shoulder your pack and head toward the forest trail.\n"
                )
                return "enter_forest"
            if direction in {"north", "east", "west"}:
                self.ui.echo("That route remains blocked—another day, perhaps.\n")
                return "stay"
            if direction in {"glade", "back"}:
                self.ui.echo("You're already standing in the Glade's heart.\n")
                return "stay"
            self.ui.echo(
                "You consider wandering that way, but the Glade offers no path yet.\n"
            )
            return "stay"
        if verb == "look":
            target = self._normalize_target(args)
            if target:
                if self._examine_target(zone_id="glade", target=target, depth=0):
                    return "stay"
                self.ui.echo("You don't spot anything like that in the Glade.\n")
                return "stay"
            self._describe_zone("glade", depth=0)
            return "stay"
        if verb == "brew":
            self._brew_menu(context="glade")
            return "stay"
        if verb == "ping":
            self._handle_radio_ping()
            return "stay"
        if verb == "status":
            self._show_notebook(zone_id="glade", stamina_max=stamina_max)
            return "stay"
        if verb == "bag":
            self._show_field_bag()
            return "stay"
        if verb == "check sky":
            from .sky import get_sky_description
            description = get_sky_description(self.state)
            self.ui.echo(f"{description}\n")
            return "stay"
        if verb == "camp":
            self._camp_phase(zone_id="glade", stamina_max=stamina_max)
            return "leave"
        if verb == "return":
            self.ui.echo("The Glade is already home—for now.\n")
            return "stay"
        if verb == "wait":
            self.ui.echo("You take a quiet moment as wind combs the grasses.\n")
            return "stay"
        if verb == "eat":
            target = self._normalize_target(args)
            if target:
                self._handle_eat(target)
            else:
                self.ui.echo("Eat what?\n")
            return "stay"
        if verb == "drink":
            target = self._normalize_target(args)
            if target:
                self._handle_drink(target)
            else:
                self.ui.echo("Drink what?\n")
            return "stay"
        if verb == "fill":
            target = self._normalize_target(args)
            self._handle_fill(target if target else "")
            return "stay"
        if verb == "cook":
            self._handle_cook(at_camp=False)
            return "stay"
        if verb == "landmarks":
            self._show_landmarks()
            return "stay"
        if verb == "travel":
            target = self._normalize_target(args)
            if target and "kirin" in target.lower():
                self._handle_kirin_travel(zone_id="glade")
                return "stay"
            self.ui.echo("Travel where? Try 'travel with kirin'.\n")
            return "stay"
        if verb == "wayfind":
            self._handle_wayfind(zone_id="glade")
            return "stay"
        if verb == "approach":
            target = self._normalize_target(args)
            if target and "echo" in target.lower():
                if is_echo_present_at_glade(self.state):
                    self._handle_approach_echo()
                    return "stay"
                else:
                    self.ui.echo("Echo isn't here right now.\n")
                    return "stay"
            else:
                self.ui.echo("Approach whom? Try 'approach echo'.\n")
                return "stay"
        if verb == "hug echo":
            if is_echo_present_at_glade(self.state):
                self._handle_hug_echo()
                return "stay"
            else:
                self.ui.echo("Echo isn't here right now.\n")
                return "stay"
        if verb == "boop echo":
            if is_echo_present_at_glade(self.state):
                self._handle_boop_echo()
                return "stay"
            else:
                self.ui.echo("Echo isn't here right now.\n")
                return "stay"
        if verb == "pet echo":
            if is_echo_present_at_glade(self.state):
                self._handle_pet_echo()
                return "stay"
            else:
                self.ui.echo("Echo isn't here right now.\n")
                return "stay"
        if verb == "talk echo" or verb == "talk to echo":
            if is_echo_present_at_glade(self.state):
                self._handle_echo_dialogue()
                return "stay"
            else:
                self.ui.echo("Echo isn't here right now.\n")
                return "stay"
        if verb == "save":
            self.repo.save(self.state)
            self.ui.echo("Game saved.\n")
            return "stay"
        if verb in {"quit", "exit"}:
            self.repo.save(self.state)
            self.ui.echo("Game saved. See you soon.\n")
            return "quit"
        if verb == "help":
            self._print_help("glade")
            return "stay"
        self._report_invalid_command("glade")
        return "stay"

    def _print_belly_help(self, mode: str, creature_name: str) -> None:
        """Print help text for belly interaction commands."""
        if mode == "echo":
            lines = [
                "soothe — Echo is already calm (flavor only)",
                "struggle — Try to get out (Echo will gently hold you)",
                "relax — Rest safely and wake at Glade (recommended)",
                "call — Contact Echo via radio (flavor only)",
                "status — review notebook",
                "bag — check supplies",
            ]
        else:
            lines = [
                "soothe — Try to calm the creature and get released nearby",
                "struggle — Attempt to force an early release (costs stamina)",
                "relax — Accept being carried (transport to nearby location)",
                "call — Contact Echo via HT radio (if available)",
                "status — review notebook",
                "bag — check supplies",
            ]
        self.ui.echo(
            "Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n"
        )

    def _handle_rub_echo_belly(self) -> None:
        """Handle rubbing Echo's belly walls."""
        from .rapport import get_rapport, change_rapport
        rapport = get_rapport(self.state, "echo")
        
        # Rubbing can increase rapport slightly (once per belly visit)
        if rapport < 5 and not self.state.belly_state.get("rubbed", False):
            change_rapport(self.state, "echo", 1)
            rapport = get_rapport(self.state, "echo")
            # Mark as rubbed to prevent spam
            if self.state.belly_state:
                self.state.belly_state["rubbed"] = True
        
        if rapport < 2:
            self.ui.echo(
                "[RADIO] A soft, uncertain pulse. The warmth around you shifts slightly, "
                "as if Echo is still getting used to your presence.\n"
            )
        elif rapport < 4:
            self.ui.echo(
                "[RADIO] A warm, contented hum. Echo's presence seems to relax around you, "
                "the rhythmic breathing becoming even more steady and peaceful.\n"
            )
        else:
            self.ui.echo(
                "[RADIO] A deep, resonant pulse of pleasure. Echo's warmth presses closer, "
                "clearly enjoying the contact. The radio thrums with deep contentment.\n"
            )

    def _handle_rest_in_echo_belly(self, stamina_max: float) -> None:
        """Handle resting in Echo's belly - fully restores stamina and treats as safe camp."""
        from .time_of_day import advance_time_of_day
        from .combat import recover_condition_at_camp
        
        # Fully restore stamina
        self.state.stamina = stamina_max
        
        # Treat as safe camp rest
        self.state.rest_type = "camp"
        
        # Recover condition (safe rest)
        recover_condition_at_camp(self.state)
        
        # Advance time
        advance_time_of_day(self.state, steps=1)
        
        self.ui.echo(
            "You rest peacefully in Echo's warm embrace. "
            "Time passes in a gentle blur, and when you come to, you feel completely refreshed. "
            "Your stamina is fully restored, and you feel safe and protected.\n"
        )

    def _prompt_command(self, prompt: str) -> Command | None:
        try:
            raw = self.ui.prompt(prompt)
        except Exception:
            raw = ""
        return self._command_parser.parse(raw)

    def _dispatch_forest_command(
        self,
        *,
        command: Command,
        zone_id: str,
        stamina_max: float,
    ) -> str:
        verb = command.verb
        args = command.args
        depth = self.state.zone_depths.get(zone_id, 0)
        current_landmark = self._get_current_landmark()
        
        # Handle landmark-specific commands
        if current_landmark:
            if verb == "leave":
                self._exit_landmark()
                return "stay"
            if verb == "look":
                target = self._normalize_target(args)
                if target:
                    # Check landmark-specific examinables
                    handled = self._handle_landmark_examine(current_landmark, target)
                    if handled:
                        return "stay"
                    # Fall through to normal examine
                # No target - show landmark description
                self.ui.echo(f"{current_landmark.long_description}\n")
                return "stay"
            # Note: "examine" and "inspect" are already mapped to "look" by the parser
            if verb in {"take", "pick", "grab", "get"}:
                target = self._normalize_target(args)
                if target:
                    handled = self._handle_landmark_take(current_landmark, target)
                    if handled:
                        return "stay"
                    self.ui.echo("You can't take that.\n")
                    return "stay"
                self.ui.echo("Take what?\n")
                return "stay"
            if verb == "gather":
                target = self._normalize_target(args)
                if target:
                    handled = self._handle_landmark_gather(current_landmark, target)
                    if handled:
                        return "stay"
                    self.ui.echo("You can't gather that here.\n")
                    return "stay"
                self.ui.echo("Gather what?\n")
                return "stay"
            if verb in {"repair", "fix", "mend"}:
                target = self._normalize_target(args)
                # Check if we're at a runestone landmark
                if current_landmark.features.get("has_runestone"):
                    if (target and "runestone" in target.lower()) or not target:
                        # Handle runestone repair
                        if not can_repair_runestone(self.state, current_landmark):
                            self.ui.echo(
                                "The runestone here is already fully repaired.\n"
                            )
                            return "stay"
                        self._handle_runestone_repair(current_landmark)
                        return "stay"
                self.ui.echo(
                    "You study the damaged stone, but you don't yet know how to repair it. "
                    "The magic feels fractured, unstable—perhaps with the right materials and knowledge, "
                    "you could restore it one day.\n"
                )
                return "stay"
            if verb == "move":
                # In landmark, "move" means leave
                self._exit_landmark()
                return "stay"
            if verb == "camp":
                self._camp_phase(zone_id=zone_id, stamina_max=stamina_max)
                return "leave"
            if verb == "return":
                self._return_to_glade(zone_id=zone_id, stamina_max=stamina_max)
                return "leave"
            if verb == "status":
                self._show_notebook(zone_id=zone_id, stamina_max=stamina_max)
                return "stay"
            if verb == "bag":
                self._show_field_bag()
                return "stay"
            if verb == "check sky":
                from .sky import get_sky_description
                description = get_sky_description(self.state)
                self.ui.echo(f"{description}\n")
                return "stay"
            if verb == "help":
                self._print_landmark_help(current_landmark)
                return "stay"
            if verb == "eat":
                target = self._normalize_target(args)
                if target:
                    self._handle_eat(target)
                else:
                    self.ui.echo("Eat what?\n")
                return "stay"
            if verb == "drink":
                target = self._normalize_target(args)
                if target:
                    self._handle_drink(target)
                else:
                    self.ui.echo("Drink what?\n")
                return "stay"
            if verb == "fill":
                target = self._normalize_target(args)
                self._handle_fill(target if target else "")
                return "stay"
            if verb == "wait":
                self.ui.echo("You take a moment to observe your surroundings.\n")
                return "stay"
            if verb == "landmarks":
                self._show_landmarks()
                return "stay"
            if verb in {"talk", "speak", "chat"}:
                # Check if there's an NPC at this landmark using appearance logic
                from .npc_appearance import get_present_npcs
                present_npcs = get_present_npcs(self.npc_catalog, self.state, current_landmark.landmark_id)
                if present_npcs:
                    # If there's exactly one NPC, talk to them
                    if len(present_npcs) == 1:
                        npc = present_npcs[0]
                        self._handle_dialogue(npc)
                        return "stay"
                    else:
                        # Multiple NPCs - let player choose
                        target = self._normalize_target(args)
                        if target:
                            # Try to match NPC by name
                            for npc in present_npcs:
                                if target.lower() in npc.name.lower():
                                    self._handle_dialogue(npc)
                                    return "stay"
                            self.ui.echo("You don't see anyone by that name here.\n")
                            return "stay"
                        else:
                            # List NPCs
                            npc_names = [npc.name for npc in present_npcs]
                            choice = self.ui.menu("Who do you want to talk to?", npc_names)
                            for npc in present_npcs:
                                if npc.name == choice:
                                    self._handle_dialogue(npc)
                                    return "stay"
                else:
                    # Check if landmark has has_npc feature
                    if current_landmark.features.get("has_npc"):
                        npc_id = current_landmark.features.get("npc_id")
                        if npc_id:
                            npc = self.npc_catalog.get(npc_id)
                            if npc:
                                self._handle_dialogue(npc)
                                return "stay"
                    self.ui.echo("There's no one here to talk to.\n")
                    return "stay"
            self._report_invalid_command(zone_id)
            return "stay"
        
        # Normal forest exploration commands
        if verb == "move":
            direction = args[0] if args else ""
            if direction in {"to", "into", "toward"} and len(args) >= 2:
                direction = args[1]
            retreat_terms = {"back", "out", "return", "glade", "north", "retreat"}
            if direction in retreat_terms:
                self._return_to_glade(zone_id=zone_id, stamina_max=stamina_max)
                return "leave"
            self._perform_explore_action(zone_id=zone_id)
            return "explore"
        if verb == "camp":
            self._camp_phase(zone_id=zone_id, stamina_max=stamina_max)
            return "leave"
        if verb == "return":
            self._return_to_glade(zone_id=zone_id, stamina_max=stamina_max)
            return "leave"
        if verb == "status":
            self._show_notebook(zone_id=zone_id, stamina_max=stamina_max)
            return "stay"
        if verb == "bag":
            self._show_field_bag()
            return "stay"
        if verb == "check sky":
            from .sky import get_sky_description
            description = get_sky_description(self.state)
            self.ui.echo(f"{description}\n")
            return "stay"
        if verb == "ping":
            self.ui.echo(
                "Static sputters—Echo can't quite catch your signal this deep in the forest.\n"
            )
            return "stay"
        if verb == "look":
            target = self._normalize_target(args)
            if target:
                if self._examine_target(zone_id=zone_id, target=target, depth=depth):
                    return "stay"
                self.ui.echo("Nothing by that name catches your eye in the forest.\n")
                return "stay"
            self._describe_zone(zone_id, depth=depth)
            return "stay"
        if verb == "save":
            self.repo.save(self.state)
            self.ui.echo("Game saved.\n")
            return "stay"
        if verb in {"quit", "exit"}:
            self.repo.save(self.state)
            self.ui.echo("Game saved. See you soon.\n")
            return "quit"
        if verb == "help":
            self._print_help("forest")
            return "stay"
        if verb == "eat":
            target = self._normalize_target(args)
            if target:
                self._handle_eat(target)
            else:
                self.ui.echo("Eat what?\n")
            return "stay"
        if verb == "drink":
            target = self._normalize_target(args)
            if target:
                self._handle_drink(target)
            else:
                self.ui.echo("Drink what?\n")
            return "stay"
        if verb == "fill":
            target = self._normalize_target(args)
            self._handle_fill(target if target else "")
            return "stay"
        if verb == "cook":
            self._handle_cook(at_camp=False)
            return "stay"
        if verb == "landmarks":
            self._show_landmarks()
            return "stay"
        if verb == "wayfind":
            self._handle_wayfind(zone_id=zone_id)
            return "stay"
        if verb == "wait":
            self.ui.echo("You pause, listening for movement between the trunks.\n")
            return "stay"
        self._report_invalid_command(zone_id)
        return "stay"

    def _report_invalid_command(self, zone_id: str) -> None:
        zone_label = zone_id.replace("_", " ").title()
        self.ui.echo(f"The {zone_label.lower()} offers no response to that.\n")

    def _describe_zone(self, zone_id: str, *, depth: int) -> None:
        band = self._depth_band(depth)
        description = self.scenes.describe(zone_id, depth_band=band)
        if description:
            self.ui.echo(f"{description}\n")
            return
        if zone_id == "glade":
            self.ui.echo("Sunlight spills across soft moss and the lone portal tree.\n")
            return
        if zone_id == "forest":
            fallback = {
                "edge": "Trail markers glow faintly with fresh cuts.",
                "mid": "Understory thickets knot around you. Runes flicker on ancient trunks.",
                "deep": "The forest hushes to a heartbeat. Massive roots and unseen wings stir just beyond sight.",
            }
            self.ui.echo(
                f"{fallback.get(band, 'The forest watches from every side.')}\n"
            )
            return
        self.ui.echo("There isn't much to see here yet.\n")

    @staticmethod
    def _depth_band(depth: int) -> str:
        if depth <= 9:
            return "edge"
        if depth <= 24:
            return "mid"
        return "deep"

    @staticmethod
    def _normalize_target(args: tuple[str, ...]) -> str | None:
        if not args:
            return None
        filler = {
            "at",
            "the",
            "a",
            "an",
            "into",
            "toward",
            "to",
            "on",
            "around",
            "about",
            "in",
        }
        tokens = [token for token in args if token not in filler]
        if not tokens:
            return None
        return " ".join(tokens).lower()

    def _examine_target(self, zone_id: str, *, target: str, depth: int) -> bool:
        lower = target.lower()
        if lower in {"echo", "snake", "radio snake"}:
            description = self.scenes.examine(zone_id, lower)
            if description:
                self.ui.echo(f"{description}\n")
            self.ui.echo(self._echo_description() + "\n")
            return True
        
        # Check if target matches a creature name
        for creature_id, creature_data in self.creatures.items():
            creature_name = creature_data.get("name", "").lower()
            creature_id_lower = creature_id.replace("_", " ").lower()
            # Check if target matches creature name or ID
            if (lower == creature_name or 
                lower == creature_id_lower or 
                lower in creature_name.split() or
                creature_name in lower):
                self._examine_creature(creature_id, creature_data)
                return True
        
        description = self.scenes.examine(zone_id, target)
        if description:
            self.ui.echo(f"{description}\n")
            return True
        transient = self._transient_examinables.get(zone_id, {})
        description = transient.get(target.lower())
        if description:
            self.ui.echo(f"{description}\n")
            return True
        return False
    
    def _examine_creature(
        self, 
        creature_id: str, 
        creature_data: Dict[str, object],
        encounter = None
    ) -> None:
        """Examine a creature and show its description."""
        creature_name = creature_data.get("name", creature_id.replace("_", " ").title())
        tags = creature_data.get("tags", [])
        
        # Build description from creature data
        description_parts = [f"{creature_name}"]
        
        # Add tag-based descriptions
        if "hostile" in tags:
            description_parts.append("This creature is known to be hostile and dangerous.")
        elif "neutral" in tags:
            description_parts.append("This creature appears neutral, neither friendly nor hostile.")
        
        if "territorial" in tags:
            description_parts.append("It's territorial and may attack if you get too close.")
        elif "shy" in tags:
            description_parts.append("It seems shy and easily startled.")
        
        if "hazard" in tags:
            description_parts.append("This is a dangerous hazard of the forest.")
        
        # Add threat information if applicable
        if creature_data.get("can_threaten", False):
            threat_style = creature_data.get("threat_style", "aggressive")
            if threat_style == "pursuit":
                description_parts.append("It's a predator that will pursue prey.")
            elif threat_style == "charge":
                description_parts.append("It's territorial and will charge if threatened.")
        
        # Add rapport information if available
        from .rapport import get_rapport, get_rapport_tier
        rapport = get_rapport(self.state, creature_id)
        rapport_tier = get_rapport_tier(rapport)
        if rapport != 0:
            description_parts.append(f"Your relationship with this creature is {rapport_tier} (rapport: {rapport}).")
        
        # If we have encounter context, add encounter-specific details
        if encounter:
            # The intro text already described the situation, so we can be brief
            pass
        
        # Combine and display
        description = " ".join(description_parts)
        self.ui.echo(f"\n{description}\n")

    def _print_help(self, zone_id: str) -> None:
        if zone_id == "glade":
            lines = [
                "move south|forest — enter the forest trail",
                "look — survey the Glade",
                "ping — call Echo over the HT radio",
                "brew — steep gathered herbs into teas",
                "eat <item> — eat food from your inventory",
                "drink <item> — drink tea or water from your water bottle",
                "fill — fill your water bottle at a water source",
                "status — review notebook",
                "bag — check supplies",
                "landmarks — view known landmarks and path stability",
                "check sky — observe the sky and light conditions",
                "camp — rest the day away",
                "save — save your progress",
                "quit — save and exit the game",
                "help — list commands",
            ]
            if is_echo_present_at_glade(self.state):
                lines.insert(3, "approach echo — interact with Echo (speak, pet, hug, boop)")
            if can_use_kirin_travel(self.state):
                lines.insert(-2, "travel with kirin — fast travel to familiar landmarks")
        else:
            lines = [
                "move / continue — push deeper into the forest",
                "move back / return — walk back to the Glade",
                "look — take in your surroundings",
                "brew — prepare teas from gathered herbs",
                "eat <item> — eat food from your inventory",
                "drink <item> — drink tea or water from your water bottle",
                "fill — fill your water bottle at a water source",
                "status — open the notebook",
                "bag — check supplies",
                "landmarks — view known landmarks and path stability",
                "check sky — observe the sky and light conditions",
                "camp — make camp on the spot",
                "save — save your progress",
                "quit — save and exit the game",
                "help — list commands",
            ]
        self.ui.echo("Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n")

    def _maybe_trigger_creature_encounter(
        self, *, zone_id: str, depth: int
    ) -> bool:
        """
        Check if a creature encounter should trigger during exploration.
        
        Returns:
            True if an encounter was triggered, False otherwise
        """
        if not self.encounter_engine:
            return False
        
        # Base encounter chance (modest, so exploration is still main loop)
        # Tuned for balance: shallow safer, mid tense, deep dangerous
        base_chance = 0.10  # 10% base chance (reduced from 12%)
        
        # Modify by depth (more encounters at mid/deep depths)
        if depth <= 9:
            depth_multiplier = 0.5  # Edge: much lower chance (safer)
        elif depth <= 24:
            depth_multiplier = 1.3  # Mid: higher chance (main tension zone)
        else:
            depth_multiplier = 1.6  # Deep: highest chance (dangerous)
        
        # Modify by season (more wildlife in spring/fall)
        season = self.state.get_season_name()
        if season in ("spring", "fall"):
            season_multiplier = 1.3
        else:
            season_multiplier = 1.0
        
        # Modify by stamina (fewer encounters if exhausted)
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        stamina_ratio = self.state.stamina / stamina_max if stamina_max > 0 else 0.5
        if stamina_ratio < 0.3:
            stamina_multiplier = 0.5  # Very low stamina reduces encounters
        else:
            stamina_multiplier = 1.0
        
        # Calculate final chance
        final_chance = base_chance * depth_multiplier * season_multiplier * stamina_multiplier
        final_chance = min(0.25, final_chance)  # Cap at 25%
        
        if random.random() > final_chance:
            return False
        
        # Get time of day
        from .time_of_day import get_time_of_day
        time_of_day_enum = get_time_of_day(self.state)
        time_of_day_str = time_of_day_enum.value
        
        # Get forest stability modifier
        from .forest_act1 import get_threat_encounter_modifier
        stability_modifier = get_threat_encounter_modifier(self.state)
        
        # Determine depth band for creature preferences
        if depth <= 9:
            depth_band = "shallow"
        elif depth <= 24:
            depth_band = "mid"
        elif depth <= 30:
            depth_band = "deep"
        elif depth <= 35:
            depth_band = "mountain_edge"
        else:
            depth_band = "cave_mouth"
        
        # Get landmark biases if at a landmark
        landmark_biases = {}
        if self.state.current_landmark and self.landmarks:
            landmark = self.landmarks.get(self.state.current_landmark)
            if landmark and hasattr(landmark, 'encounter_biases'):
                landmark_biases = landmark.encounter_biases
        
        # Select a creature to encounter from creatures.json
        # Get all creatures that have forest tag
        available_creatures = []
        threat_capable = []
        creature_weights = []
        
        for creature_id, creature_data in self.creatures.items():
            tags = creature_data.get("tags", [])
            if "forest" in tags:
                # Check biome restrictions (creek, cave-mouth, night-only)
                # Creek creatures only appear at creek/river landmarks
                if "creek" in tags:
                    if not self.state.current_landmark:
                        # Skip creek creatures when not at a water landmark
                        # Could check landmark type, but for now skip if no landmark
                        continue
                    # TODO: Could add landmark type checking here for more precise control
                
                # Cave-mouth creatures prefer cave_mouth depth band
                if "cave-mouth" in tags and depth_band != "cave_mouth":
                    # Still allow, but reduce weight significantly
                    pass  # Will be handled by depth_preferences
                
                # Night-only creatures must be at night
                if "night-only" in tags:
                    if time_of_day_str not in ("Night", "Dusk"):
                        continue  # Skip entirely if not night/dusk
                
                # Night-biased creatures get reduced weight during day
                if "night-biased" in tags:
                    if time_of_day_str == "Day":
                        # Reduce weight but don't exclude
                        pass  # Will be handled by time_of_day_preferences
                
                available_creatures.append(creature_id)
                if creature_data.get("can_threaten", False):
                    threat_capable.append(creature_id)
                
                # Calculate weight based on preferences
                weight = 1.0
                
                # Depth preference
                depth_prefs = creature_data.get("depth_preferences", {})
                if depth_band in depth_prefs:
                    weight *= depth_prefs[depth_band]
                
                # Season preference
                season_prefs = creature_data.get("season_preferences", {})
                if season in season_prefs:
                    weight *= season_prefs[season]
                
                # Time-of-day preference
                time_prefs = creature_data.get("time_of_day_preferences", {})
                if time_of_day_str in time_prefs:
                    weight *= time_prefs[time_of_day_str]
                
                # Biome restrictions - apply additional penalties
                if "creek" in tags:
                    # Boost creek creatures at water landmarks, reduce elsewhere
                    if self.state.current_landmark:
                        # Assume water landmarks have certain IDs or could check landmark type
                        # For now, boost weight slightly
                        weight *= 1.2
                    else:
                        weight *= 0.3  # Much less likely away from water
                
                if "cave-mouth" in tags and depth_band != "cave_mouth":
                    weight *= 0.2  # Much less likely outside cave-mouth
                
                # Rapport modifier
                rapport = self.state.rapport.get(creature_id, 0)
                weight *= (1.0 + (rapport * 0.2))
                
                # Landmark bias (if at a landmark that biases this creature)
                if self.state.current_landmark:
                    # Check if this landmark has a bias for this creature
                    # This would need to be loaded from landmark data
                    # For now, we'll use a simple check
                    landmark_bias = landmark_biases.get(creature_id, 1.0)
                    weight *= landmark_bias
                
                # Forest stability affects mystical creatures more
                # Tuned: Moss-Treader and Glow-Elk slightly more common after stabilization
                if "mystical" in tags or "leyline-tuned" in tags:
                    # Special handling for Kirin: rare early Act I, more reliable post-stabilization
                    if creature_id == "kirin":
                        from .forest_act1 import get_forest_act1_progress_summary
                        summary = get_forest_act1_progress_summary(self.state)
                        # Kirin is very rare before Act I completion
                        if not self.state.act1_forest_stabilized or self.state.act1_repaired_runestones < 3:
                            weight *= 0.05  # 5% of base weight - very rare early
                        elif "Stabilized" in summary["status"] or "Complete" in summary["status"]:
                            weight *= 2.5  # Much more common after stabilization
                        elif "Stabilizing" in summary["status"]:
                            weight *= 1.2  # Slightly more common as stabilizing
                        else:
                            weight *= 0.1  # Still rare if not yet stabilizing
                        
                        # Bias toward appearing near major landmarks/glades
                        if self.state.current_landmark or zone_id == "glade":
                            weight *= 1.5  # More likely at landmarks
                    else:
                        # Other mystical creatures
                        from .forest_act1 import get_forest_act1_progress_summary
                        summary = get_forest_act1_progress_summary(self.state)
                        if "Stabilized" in summary["status"] or "Complete" in summary["status"]:
                            weight *= 1.7  # Increased from 1.5 to 1.7
                        elif "Stabilizing" in summary["status"]:
                            weight *= 1.3  # Increased from 1.2 to 1.3
                        else:
                            weight *= 0.6  # Reduced from 0.7 to 0.6 (rarer before stabilization)
                
                creature_weights.append(weight)
        
        # Determine if we should prefer threat encounters
        # More likely at mid/deep depths, when hungry, low stamina, or in certain seasons
        # Tuned: shallow forest should rarely have threats
        prefer_threat = False
        if depth >= 10:  # Only prefer threats at mid-depth or deeper
            # Check hunger (days without meal)
            if self.state.days_without_meal >= 2:
                prefer_threat = True
            # Check stamina
            if stamina_ratio < 0.4:
                prefer_threat = True
            # Check season (fall/winter = more aggressive)
            if season in ("fall", "winter"):
                prefer_threat = True
        
        # Adjust weights for threat preference
        for i, creature_id in enumerate(available_creatures):
            # Boost threat-capable creatures if we're preferring threats
            if prefer_threat and creature_id in threat_capable:
                creature_weights[i] *= 2.0
            # Reduce threat-capable creatures if we're not preferring threats and rapport is high
            elif not prefer_threat and creature_id in threat_capable:
                rapport = self.state.rapport.get(creature_id, 0)
                if rapport >= 2:
                    creature_weights[i] *= 0.3
            
            # Apply forest stability modifier to threat encounters
            if creature_id in threat_capable:
                creature_weights[i] *= stability_modifier
        
        if not available_creatures:
            return False
        
        selected_creature = random.choices(
            available_creatures, weights=creature_weights, k=1
        )[0]
        
        # Select encounter for this creature
        # If preferring threat and creature is threat-capable, prefer threat encounters
        encounter = None
        if prefer_threat and selected_creature in threat_capable:
            # Try to find a threat encounter first
            all_threat_encounters = [
                enc for enc in self.encounter_engine.encounters.values()
                if enc.creature_id == selected_creature and enc.encounter_type == "threat"
            ]
            if all_threat_encounters:
                # First try encounters that match trigger conditions
                valid_threat = [
                    enc for enc in all_threat_encounters
                    if self.encounter_engine._check_trigger_conditions(
                        self.state, enc, depth, season
                    )
                ]
                if valid_threat:
                    encounter = random.choice(valid_threat)
                else:
                    # Fall back to any threat encounter if none match conditions
                    encounter = random.choice(all_threat_encounters)
        
        # Fall back to normal encounter selection (includes both normal and threat encounters)
        if not encounter:
            encounter = self.encounter_engine.select_encounter_for_creature(
                self.state,
                selected_creature,
                depth,
                season,
            )
        
        if not encounter:
            return False
        
        # Run the encounter
        self._run_encounter(encounter, depth=depth)
        return True
    
    def _run_encounter(self, encounter, *, depth: int = 0) -> None:
        """Run a creature encounter with player choices."""
        from .encounters import EncounterDefinition
        from .combat import (
            calculate_flee_success,
            calculate_calm_success,
            calculate_stand_ground_success,
            change_condition,
            get_condition_label,
            should_force_retreat,
        )
        
        # Display intro text
        self.ui.echo(f"\n{encounter.intro_text}\n")
        
        # For threat encounters, show condition and stamina
        if encounter.encounter_type == "threat":
            stamina_max = self.state.character.get_stat(
                "stamina_max",
                timed_modifiers=self.state.timed_modifiers,
                current_day=self.state.day,
            )
            condition_label = get_condition_label(self.state.condition)
            self.ui.echo(
                f"Stamina: {self.state.stamina:.1f}/{stamina_max:.1f} | "
                f"Condition: {condition_label}\n"
            )
        
        # Allow player to examine the creature before choosing action
        creature_id = encounter.creature_id
        creature_data = self.creatures.get(creature_id, {})
        creature_name = creature_data.get("name", creature_id.replace("_", " ").title())
        
        # Get available choices
        available_choices = self.encounter_engine.get_available_choices(
            self.state, encounter
        )
        
        if not available_choices:
            # No valid choices, use a default outcome
            self.ui.echo("You're not sure how to respond.\n")
            return
        
        # Present choices to player, including option to examine creature
        choice_texts = [choice.text for choice in available_choices]
        # Add examine option at the beginning
        examine_option = f"Look at {creature_name}"
        choice_texts.insert(0, examine_option)
        
        # Loop until player chooses an action (not examine)
        selected_text = None
        while True:
            selected_text = self.ui.menu("What do you do?", choice_texts)
            
            # If player chose to examine, show description and loop
            if selected_text == examine_option:
                self._examine_creature(creature_id, creature_data, encounter)
                # Re-show the menu
                continue
            else:
                # Player chose an action, break out of loop
                break
        
        # Find the selected choice
        selected_choice = None
        for choice in available_choices:
            if choice.text == selected_text:
                selected_choice = choice
                break
        
        if not selected_choice:
            # Fallback (shouldn't happen)
            return
        
        # Get and apply outcome
        outcome = encounter.outcomes.get(selected_choice.outcome_key)
        if not outcome:
            # Missing outcome, use a default
            self.ui.echo("Your action has an uncertain result.\n")
            return
        
        # Handle threat encounters differently
        # Check for vore outcomes
        if outcome.text == "VORE_SWALLOWED":
            # Handle predator vore outcome (non-lethal shelter)
            from .vore import is_vore_enabled
            from .belly_interaction import enter_belly_state
            
            # Only enter belly state if vore is enabled
            if is_vore_enabled(self.state):
                # Enter belly interaction state
                creature_data = self.creatures.get(encounter.creature_id, {})
                creature_name = creature_data.get("name", encounter.creature_id.replace("_", " ").title())
                predator_size = creature_data.get("size_class", "medium")
                player_size = self.state.character.size
                
                self.ui.echo(
                    f"\nYou freeze, submitting to the {creature_name}'s dominance. "
                    "Its jaws open wide—not to tear, but to claim. "
                    "You're pulled into darkness, warmth, and a crushing pressure "
                    "that's somehow not suffocating.\n"
                )
                
                # Add Forest magic flavor if player is larger than predator
                try:
                    from .flavor_profiles import get_forest_magic_size_flavor
                    magic_flavor = get_forest_magic_size_flavor(player_size, predator_size)
                    if magic_flavor:
                        self.ui.echo(f"{magic_flavor}\n")
                except Exception:
                    pass
                
                enter_belly_state(
                    self.state,
                    creature_id=encounter.creature_id,
                    mode="predator",
                    ui=self.ui,
                )
                
                # Apply outcome effects (stamina, condition, rapport) before entering belly
                self.encounter_engine.apply_outcome(self.state, encounter, outcome)
                
                # Belly interaction loop will handle the rest
                return
            else:
                # Vore disabled: use alternate non-swallow outcome
                # Fall through to normal encounter handling or use a different outcome
                self.ui.echo(
                    "\nThe creature lunges, but you manage to evade its grasp. "
                    "You retreat, shaken but unharmed.\n"
                )
                # Apply outcome effects
                self.encounter_engine.apply_outcome(self.state, encounter, outcome)
                return
        
        if encounter.encounter_type == "threat" and outcome.threat_resolution:
            self._resolve_threat_encounter(
                encounter, outcome, selected_choice, depth=depth
            )
        else:
            # Normal encounter handling
            self.encounter_engine.apply_outcome(self.state, encounter, outcome)
            self.ui.echo(f"\n{outcome.text}\n")
    
    def _resolve_threat_encounter(
        self, encounter, outcome, selected_choice, *, depth: int
    ) -> None:
        """Resolve a threat encounter using combat mechanics."""
        from .combat import (
            calculate_flee_success,
            calculate_calm_success,
            calculate_stand_ground_success,
            change_condition,
            get_condition_label,
            should_force_retreat,
        )
        
        resolution_type = outcome.threat_resolution
        creature_id = encounter.creature_id
        
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        stamina_ratio = self.state.stamina / stamina_max if stamina_max > 0 else 0.5
        
        # Check if player has food for calm attempts
        has_food = any(
            item in self.state.inventory
            for item in ["forest_berries", "trail_nuts", "dried_berries"]
        )
        
        success = False
        result_text = ""
        stamina_loss = 0.0
        condition_increase = 0
        rapport_change = 0
        forced_retreat = False
        
        if resolution_type == "flee":
            success = calculate_flee_success(
                self.state, creature_id, depth, stamina_ratio
            )
            if success:
                result_text = (
                    "You sprint through the underbrush, branches whipping past. "
                    "After what feels like an eternity, you slow and listen—silence. "
                    "You've escaped, but your heart pounds and your legs ache."
                )
                stamina_loss = -1.5
            else:
                result_text = (
                    "You try to flee, but the creature is faster. It catches up, "
                    "snapping at your heels. You stumble, scraping yourself on roots and rocks. "
                    "You manage to break away, but you're hurt and exhausted."
                )
                stamina_loss = -2.0
                condition_increase = 1
        
        elif resolution_type == "calm":
            success = calculate_calm_success(self.state, creature_id, has_food)
            if success:
                if has_food:
                    result_text = (
                        "You slowly extend the food offering. The creature sniffs cautiously, "
                        "then takes it. The tension eases. It gives you a long look, then "
                        "turns and disappears into the forest. You've de-escalated the situation."
                    )
                    # Remove food item
                    for food_item in ["forest_berries", "trail_nuts", "dried_berries"]:
                        if food_item in self.state.inventory:
                            self.state.inventory.remove(food_item)
                            break
                else:
                    result_text = (
                        "You speak softly, making slow, non-threatening movements. "
                        "The creature watches warily, but the aggression fades. "
                        "After a tense moment, it backs away and disappears into the trees."
                    )
                rapport_change = 1
                stamina_loss = -0.5
            else:
                result_text = (
                    "You try to calm the creature, but it's not working. It lunges forward, "
                    "and you barely dodge. You're forced to retreat, shaken and bruised."
                )
                stamina_loss = -1.5
                condition_increase = 1
        
        elif resolution_type == "stand_ground":
            success = calculate_stand_ground_success(
                self.state, creature_id, stamina_ratio
            )
            if success:
                result_text = (
                    "You stand firm, meeting the creature's gaze without flinching. "
                    "The standoff lasts for what feels like minutes. Finally, it backs down, "
                    "respect in its eyes. You've earned its respect through courage."
                )
                rapport_change = 2
                stamina_loss = -1.0
            else:
                result_text = (
                    "You stand your ground, but the creature doesn't back down. It charges, "
                    "and you're forced to dodge and retreat. You're battered and exhausted, "
                    "but you've survived."
                )
                stamina_loss = -2.5
                condition_increase = 2
        
        # Apply results
        if stamina_loss != 0.0:
            self.state.stamina = max(0.0, min(stamina_max, self.state.stamina + stamina_loss))
        
        if condition_increase > 0:
            change_condition(self.state, condition_increase)
        
        if rapport_change != 0:
            from .rapport import change_rapport
            change_rapport(self.state, creature_id, rapport_change)
        
        # Display result
        self.ui.echo(f"\n{result_text}\n")
        
        # Determine outcome based on success and condition
        if should_force_retreat(self.state) or (not success and condition_increase >= 2):
            # Severe failure - collapse
            context = OutcomeContext(
                source_id=creature_id,
                collapse_severity=1.0 + (condition_increase * 0.2),  # More severe if more hurt
            )
            resolve_encounter_outcome(
                self.state,
                EncounterOutcome.COLLAPSE,
                context=context,
                ui=self.ui,
            )
        elif not success:
            # Moderate failure - retreat
            context = OutcomeContext(
                source_id=creature_id,
            )
            resolve_encounter_outcome(
                self.state,
                EncounterOutcome.RETREAT,
                context=context,
                ui=self.ui,
            )
        # Success cases use NORMAL outcome (no special handling needed)
    
    def _resolve_encounter(self, event: "Event") -> str:
        """
        Resolve an encounter event (legacy method for old event system).
        
        This is kept for backward compatibility with existing events.
        New encounters should use the encounter framework via _maybe_trigger_creature_encounter.
        """
        effects = event.effects or {}
        creature_id = effects.get("creature_id")
        creature_data = self.creatures.get(creature_id, {}) if creature_id else {}
        creature_name = (
            creature_data.get("name", creature_id.replace("_", " "))
            if creature_id
            else effects.get("creature", event.event_id.replace("_", " "))
        )
        base_text = effects.get("encounter_text")
        base_text = (
            base_text.strip()
            if base_text
            else f"{creature_name} studies you for a long heartbeat."
        )

        allows_vore = bool(creature_data.get("allows_vore", False))
        allows_combat = bool(
            creature_data.get("allows_combat", False)
            or "hostile" in creature_data.get("tags", [])
        )

        if self.state.vore_enabled and allows_vore:
            outcome = self.handle_vore_stub(
                creature_id, creature_name, creature_data, base_text
            )
        elif allows_combat:
            outcome = self.handle_combat_stub(
                creature_id, creature_name, creature_data, base_text
            )
        else:
            outcome = self.handle_normal_encounter(
                creature_id, creature_name, creature_data, base_text
            )

        self._apply_encounter_outcome(outcome, creature_id)
        flavor = outcome.flavor.strip()
        return flavor + "\n"

    def handle_normal_encounter(
        self,
        creature_id: str | None,
        creature_name: str,
        creature_data: dict[str, object],
        base_text: str,
    ) -> EncounterOutcome:
        return EncounterOutcome(flavor=base_text)

    def handle_combat_stub(
        self,
        creature_id: str | None,
        creature_name: str,
        creature_data: dict[str, object],
        base_text: str,
    ) -> EncounterOutcome:
        extra = f"{creature_name} tests your footing with a feint. You retreat, breathing hard."
        return EncounterOutcome(
            flavor=f"{base_text}\n{extra}",
            stamina_delta=-1.0,
        )

    def handle_vore_stub(
        self,
        creature_id: str | None,
        creature_name: str,
        creature_data: dict[str, object],
        base_text: str,
    ) -> EncounterOutcome:
        if self.state.player_as_pred_enabled:
            extra = f"You share a knowing smile with {creature_name}; hunts can wait until trust is deeper."
            rapport_delta = {creature_id: 1} if creature_id else {}
        else:
            extra = f"{creature_name} rumbles a promise of gentler lessons once you're ready to submit."
            rapport_delta = {}
        return EncounterOutcome(
            flavor=f"{base_text}\n{extra}",
            stamina_delta=-0.5,
            rapport_delta=rapport_delta,
        )

    def _apply_encounter_outcome(
        self, outcome: EncounterOutcome, creature_id: str | None
    ) -> None:
        if outcome.stamina_delta:
            stamina_max = self.state.character.get_stat(
                "stamina_max",
                timed_modifiers=self.state.timed_modifiers,
                current_day=self.state.day,
            )
            self.state.stamina = min(
                stamina_max, max(0.0, self.state.stamina + outcome.stamina_delta)
            )
        for target, delta in outcome.rapport_delta.items():
            key = target or creature_id
            if not key:
                continue
            self.state.rapport[key] = self.state.rapport.get(key, 0) + delta

    def _handle_glade_rescue(
        self, *, depth_clause: str, dream_text: str
    ) -> tuple[dict[str, int], dict[str, int]]:
        self.state.active_zone = "glade"
        self.state.zone_steps.clear()
        self.state.zone_depths.clear()
        zone_steps_snapshot = {"glade": 0}
        zone_depths_snapshot = {}
        message = (
            f"Echo's enormous coils lift you gently{depth_clause}, ferrying you back "
            "to the Glade before setting you down in silence.\n"
        )
        if dream_text:
            message += dream_text
        self.ui.echo(message)
        return zone_steps_snapshot, zone_depths_snapshot

    def _echo_protective_watch(
        self, depth_text: str, dream_text: str, zone_id: str
    ) -> None:
        self.ui.echo(
            "Predator eyes gleam in the underbrush, but Echo curls protectively around you, keeping them at bay.\n"
            + depth_text
            + dream_text
        )
        self.state.active_zone = zone_id

    def _process_radio_return(self) -> None:
        if not self.state.pending_radio_upgrade:
            return
        return_day = self.state.pending_radio_return_day
        if return_day is None or self.state.day < return_day:
            return
        if self.state.vore_enabled:
            text = (
                "At dawn Echo glides into the Glade, working the HT radio back up from their throat "
                "before setting it in your hands with a grateful hiss. Static resolves into words."
            )
        else:
            text = (
                "Echo coils beside you at first light, sliding the polished HT radio from their throat pouch "
                'and nudging it toward you. "Signal should reach clearer now," the static seems to say.'
            )
        self.ui.echo(text + "\n")
        self.state.pending_radio_upgrade = False
        self.state.pending_radio_return_day = None
        self.state.radio_version = 2
        from .echo import change_echo_rapport
        change_echo_rapport(self.state, 1)

    def _apply_pending_brews(self) -> None:
        # No longer auto-applying brews - teas are now persistent items
        # This method kept for backward compatibility but does nothing
        pass

    def _handle_radio_ping(self) -> None:
        if self.state.pending_radio_upgrade:
            self.ui.echo("Only static answers—Echo is still tuning the radio.\n")
            return
        if self.state.radio_version <= 1:
            impressions = [
                "Orange static blooms across the speaker—Echo sends warm gratitude and a rush of forest scents.",
                "A pulse of blue static thrums like a heartbeat, Echo's emotions washing over you without words.",
                "The radio crackles with sun-hot warmth and the distant echo of hissing laughter.",
            ]
            self.ui.echo(random.choice(impressions) + "\n")
            from .echo import get_echo_rapport
            rapport = get_echo_rapport(self.state)
            if not self.state.pending_radio_upgrade and rapport > 5:
                if self.state.vore_enabled:
                    upgrade = "Echo slides close, unhinging their jaw in a gentle swallow that spirits the HT radio into their coils."
                else:
                    upgrade = "Echo loops the HT radio into their throat pouch, promising with a soft hiss to refine its range overnight."
                self.ui.echo(upgrade + "\n")
                self.state.pending_radio_upgrade = True
                self.state.pending_radio_return_day = self.state.day + 1
                from .echo import change_echo_rapport
                change_echo_rapport(self.state, 1)
            elif rapport <= 5:
                self.ui.echo(
                    "Static pulses with expectant warmth—Echo seems to wait until your bond deepens a little more.\n"
                )
            return
        clear_messages = [
            '"Signal steady. Forest edge is quiet," Echo whispers through the static.',
            '"You breathing alright? Take water before you range," Echo crackles, concern threading the words.',
            '"Trail spirits are calm. Call if shadows crowd you," Echo\'s voice hums, almost musical.',
        ]
        self.ui.echo(random.choice(clear_messages) + "\n")
        from .echo import change_echo_rapport
        change_echo_rapport(self.state, 1)

    def _available_teas(self) -> dict[str, dict[str, object]]:
        inventory_counts = Counter(self.state.inventory)
        available: dict[str, dict[str, object]] = {}
        for tea_id, data in self.teas.items():
            requires = Counter(data.get("requires", []))
            # Check if all required items are present
            if not all(
                inventory_counts.get(item, 0) >= qty for item, qty in requires.items()
            ):
                continue
            # Check if required tool is present (if specified)
            requires_tool = data.get("requires_tool")
            if requires_tool and requires_tool not in self.state.inventory:
                continue
            available[tea_id] = data
        return available

    def _brew_tea(self, tea_id: str, data: dict[str, object]) -> None:
        requires = Counter(data.get("requires", []))
        for item, qty in requires.items():
            for _ in range(qty):
                try:
                    self.state.inventory.remove(item)
                except ValueError:
                    pass
        name = data.get("name", tea_id.replace("_", " ").title())
        description = data.get("description")
        
        # Check if this is a tea (has duration_days > 0) or a crafted item
        duration_days = int(data.get("duration_days", 0))
        inventory_slots = self.state.character.get_stat(
            "inventory_slots",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        if len(self.state.inventory) >= int(inventory_slots):
            self.ui.echo("Your bag is full. You'll need to make space first.\n")
            # Restore consumed items
            for item, qty in requires.items():
                for _ in range(qty):
                    self.state.inventory.append(item)
            return
        
        if duration_days > 0:
            # It's a tea - add as persistent item to inventory
            self.state.inventory.append(tea_id)
            if description:
                # Enhance description with race-aware flavor
                enhanced_description = enhance_tea_description(
                    description,
                    tea_id,
                    self.state.character.race_id,
                )
                self.ui.echo(f"You brew {name}. {enhanced_description}\n")
            else:
                self.ui.echo(f"You brew {name}.\n")
        else:
            # It's a crafted item - add directly to inventory
            self.state.inventory.append(tea_id)
            if description:
                self.ui.echo(f"You craft {name}. {description}\n")
            else:
                self.ui.echo(f"You craft {name}.\n")

    def _brew_menu(self, *, context: str = "glade") -> None:
        available = self._available_teas()
        if not available:
            if context == "glade":
                self.ui.echo("No gathered herbs are ready for brewing.\n")
            return
        title = "Brew at camp?" if context == "camp" else "Prepare a brew?"
        finish_label = "Finish brewing" if context == "camp" else "Stop brewing"
        while True:
            available = self._available_teas()
            if not available:
                self.ui.echo("No more herbs remain to brew right now.\n")
                break
            sorted_teas = sorted(
                available.items(),
                key=lambda item: item[1].get("name", item[0]),
            )
            options = [
                f"Brew {data.get('name', tea_id.replace('_', ' ').title())}"
                for tea_id, data in sorted_teas
            ]
            options.append(finish_label)
            choice = self.ui.menu(title, options)
            if choice.lower().startswith("finish") or choice.lower().startswith("stop"):
                break
            selected_id = None
            selected_data = None
            for tea_id, data in sorted_teas:
                expected = f"Brew {data.get('name', tea_id.replace('_', ' ').title())}"
                if choice == expected:
                    selected_id = tea_id
                    selected_data = data
                    break
            if selected_id is None or selected_data is None:
                break
            self._brew_tea(selected_id, selected_data)

    def _echo_description(self) -> str:
        if self.state.pending_radio_upgrade:
            return "Echo pats the hollow where your HT radio should be, static promising its return soon."
        if self.state.radio_version >= 2:
            return "Echo's voice threads clearer words through the radio now, hisses translating into gentle sentences."
        return "Echo communicates in pulses of static and emotion, feelings more than words flowing through the radio coil."

    def _set_scene_highlights(
        self,
        *,
        zone_id: str,
        depth: int,
        extras: Iterable[str] | None = None,
    ) -> None:
        if extras is not None:
            extras_tuple = tuple(extras)
            if extras_tuple:
                self._transient_extras[zone_id] = extras_tuple
                self._transient_examinables[zone_id] = {
                    term.lower(): self._transient_description(term)
                    for term in extras_tuple
                }
            else:
                self._transient_extras.pop(zone_id, None)
                self._transient_examinables.pop(zone_id, None)
        else:
            extras_tuple = self._transient_extras.get(zone_id, ())
        terms = list(self.scenes.highlight_terms(zone_id))
        terms.extend(extras_tuple)
        unique: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if not term:
                continue
            normalized = term.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
        self.ui.set_highlights(unique)

    @staticmethod
    def _transient_description(name: str) -> str:
        trimmed = name.strip()
        if not trimmed:
            trimmed = "The figure"
        return f"{trimmed} remains within arm's reach if you dare to study them."

    def _enter_landmark(self, landmark: Landmark, *, zone_id: str) -> None:
        """Enter a landmark context."""
        self.state.current_landmark = landmark.landmark_id
        is_first_discovery = landmark.landmark_id not in self.state.discovered_landmarks
        if is_first_discovery:
            self.state.discovered_landmarks.append(landmark.landmark_id)
            # Initialize stability to 1 for newly discovered landmarks
            if landmark.landmark_id not in self.state.landmark_stability:
                self.state.landmark_stability[landmark.landmark_id] = 1
        else:
            # Bump stability on revisit
            bump_path_stability(self.state, landmark.landmark_id)
        
        # Initialize runestone state if this landmark has one
        if landmark.features.get("has_runestone"):
            initialize_runestone_state(self.state, landmark.landmark_id, self.runestone_defs)
            was_first = not self.state.runestone_states.get(landmark.landmark_id, {}).get("is_discovered", False)
            mark_runestone_discovered(self.state, landmark.landmark_id, self.runestone_defs)
            
            # Show first runestone tip if this is the first discovery
            if was_first:
                from .forest_act1 import should_show_first_runestone_tip
                if should_show_first_runestone_tip(self.state):
                    self.ui.echo(
                        "\nYou sense this stone is part of a damaged pattern; Echo or the hermit might know more.\n"
                    )
        
        self.ui.echo(f"\n{landmark.short_description}\n")
        
        # Check for rare lore events after entering landmark
        rare_events = self._get_rare_lore_events()
        if rare_events:
            event = rare_events.check_for_event(self.state, zone_id, self.landmarks)
            if event:
                text = rare_events.trigger_event(event, self.state)
                self.ui.echo(f"\n{text}\n")
        
        # Check for NPCs at this landmark using appearance logic
        from .npc_appearance import get_present_npcs, get_npc_presence_description
        present_npcs = get_present_npcs(self.npc_catalog, self.state, landmark.landmark_id)
        if present_npcs or landmark.features.get("has_npc"):
            # Add NPC description
            if present_npcs:
                for npc in present_npcs:
                    desc = get_npc_presence_description(npc, landmark.landmark_id)
                    self.ui.echo(f"{desc}\n")
            elif landmark.features.get("has_npc"):
                npc_id = landmark.features.get("npc_id")
                if npc_id:
                    npc = self.npc_catalog.get(npc_id)
                    if npc:
                        self.ui.echo(f"{npc.description}\n")
        
        self.ui.echo(
            f"You've discovered the {landmark.name}. "
            "Commands: look, examine <thing>, leave, status, bag, help.\n"
        )
        # Set up examinables for this landmark
        extras: list[str] = []
        if landmark.features.get("has_runestone"):
            extras.append("runestone")
        if landmark.features.get("has_gold_pan"):
            flags = self.state.landmark_flags.get(landmark.landmark_id, {})
            if not flags.get("gold_pan_taken", False):
                extras.append("gold pan")
        if landmark.features.get("has_creek"):
            extras.append("sand")
            extras.append("clay")
        if landmark.features.get("has_food", False):
            flags = self.state.landmark_flags.get(landmark.landmark_id, {})
            if not flags.get("food_gathered_today", False):
                food_type = landmark.features.get("food_type", "")
                if food_type == "creek_forage":
                    extras.append("watercress")
                elif food_type == "edible_fungus":
                    extras.append("fungus")
                elif food_type == "night_mushrooms":
                    extras.append("mushrooms")
        self._set_scene_highlights(
            zone_id=zone_id,
            depth=self.state.zone_depths.get(zone_id, 0),
            extras=tuple(extras),
        )

    def _exit_landmark(self) -> None:
        """Exit landmark context and return to normal exploration."""
        self.state.current_landmark = None
        # Clear sheltered flag when leaving landmark (back to normal outdoor conditions)
        self.state.is_sheltered = False
        self.ui.echo("You step away from the landmark and continue exploring.\n")

    def _get_current_landmark(self) -> Landmark | None:
        """Get the landmark the player is currently at, if any."""
        if not self.state.current_landmark:
            return None
        return self.landmarks.get(self.state.current_landmark)

    def _handle_landmark_examine(self, landmark: Landmark, target: str) -> bool:
        """Handle examining objects at a landmark. Returns True if handled."""
        target_lower = target.lower()
        
        # Check for runestone
        if landmark.features.get("has_runestone") and target_lower in {"runestone", "stone", "rune", "plinth"}:
            from .runestones import get_runestone_state
            runestone_state = get_runestone_state(self.state, landmark.landmark_id)
            
            if runestone_state.get("is_fully_repaired", False):
                # Runestone is repaired
                if landmark.landmark_id == "split_boulder":
                    self.ui.echo(
                        "The runestone glows with steady, stable magic. The cracks have been filled with mortar, "
                        "and the runes pulse in perfect harmony. The stone's resonance is clear and strong, "
                        "its power fully restored.\n"
                    )
                elif landmark.landmark_id == "stone_lantern_clearing":
                    self.ui.echo(
                        "The runestone at the center of the plinth pulses with restored power. The glyphs glow "
                        "with steady light, and the magical resonance flows smoothly. The ritual site feels "
                        "complete once more.\n"
                    )
                elif landmark.landmark_id == "fallen_giant":
                    self.ui.echo(
                        "The runestone embedded in the ancient wood now hums steadily with a soft light. "
                        "The magical pulse is stable and strong, and the runes glow with restored power. "
                        "The hollow feels more peaceful, more complete.\n"
                    )
                else:
                    self.ui.echo(
                        "The runestone glows with steady, stable magic. It's been fully repaired and restored.\n"
                    )
            else:
                # Runestone is fractured
                if landmark.landmark_id == "split_boulder":
                    self.ui.echo(
                        "The fractured runestone pulses with unstable magic. Deep cracks spiderweb across its surface, "
                        "and the runes carved into the stone flicker erratically. The magical resonance here feels wrong— "
                        "like a song played out of tune. You sense it could be repaired with the right materials.\n"
                    )
                elif landmark.landmark_id == "stone_lantern_clearing":
                    self.ui.echo(
                        "The rune-etched plinth bears a fractured runestone at its center. The stone hums with distorted "
                        "resonance, its magical pulse erratic and broken. The runes that once guided the forest's memory "
                        "are now cracked and unstable. This was clearly a ritual site, now fallen into disrepair. "
                        "You sense it could be restored with the right materials and tools.\n"
                    )
                elif landmark.landmark_id == "fallen_giant":
                    self.ui.echo(
                        "At the heart of the hollow, a fractured runestone is embedded in the ancient wood. "
                        "The stone pulses with unstable magic, its runes flickering erratically. The magical resonance "
                        "here feels wrong—fractured and incomplete. You sense it could be repaired with the right materials.\n"
                    )
                else:
                    self.ui.echo(
                        "The fractured runestone glimmers with unstable magic. It's clearly damaged and in need of repair. "
                        "You'll need materials to fix it.\n"
                    )
                
                # Show Echo hint if available
                echo_hint = get_echo_hint_for_runestone(self.state, landmark)
                if echo_hint:
                    self.ui.echo(echo_hint)
            return True
        
        # Check for gold pan
        if landmark.features.get("has_gold_pan") and target_lower in {"gold pan", "pan", "tin pan", "goldpan"}:
            flags = self.state.landmark_flags.get(landmark.landmark_id, {})
            if flags.get("gold_pan_taken", False):
                self.ui.echo("The spot where the pan lay is now just sand and clay.\n")
            else:
                self.ui.echo(
                    "A tarnished tin pan lies half-buried in the sand, its handle rusted but still serviceable. "
                    "It looks like it could be useful for sifting materials or mixing compounds.\n"
                )
            return True
        
        # Check for food sources
        if landmark.features.get("has_food", False):
            food_type = landmark.features.get("food_type", "")
            flags = self.state.landmark_flags.get(landmark.landmark_id, {})
            if not flags.get("food_gathered_today", False):
                if food_type == "creek_forage" and target_lower in {"watercress", "tuber", "food", "forage"}:
                    self.ui.echo(
                        "Fresh watercress grows along the creek's edge, and you spot small tubers in the muddy bank. "
                        "You could gather some food here.\n"
                    )
                    return True
                elif food_type == "edible_fungus" and target_lower in {"fungus", "mushroom", "food", "forage"}:
                    self.ui.echo(
                        "Pale, spongy fungus grows in the hollow of the fallen giant. It looks safe to eat. "
                        "You could gather some here.\n"
                    )
                    return True
                elif food_type == "night_mushrooms" and target_lower in {"mushroom", "night", "food", "forage"}:
                    self.ui.echo(
                        "Dark, bioluminescent mushrooms grow in the moss around the stone lanterns. "
                        "They glow faintly in the dim light. You could gather some here.\n"
                    )
                    return True
        
        # Check for exit blockers
        if landmark.features.get("is_exit_blocker", False):
            exit_direction = landmark.features.get("exit_direction", "")
            # Check if player is examining exit-related terms
            exit_terms = {
                "plains": {"plains", "pass", "north", "exit", "way", "path", "route", "out"},
                "mountain": {"mountain", "route", "west", "exit", "way", "path", "trail", "switchback", "out"},
                "riverside": {"river", "road", "crossing", "bridge", "east", "exit", "way", "path", "out"},
                "cave": {"cave", "cavern", "entrance", "descent", "down", "exit", "way", "path", "out"}
            }
            
            relevant_terms = exit_terms.get(exit_direction, set())
            if any(term in target_lower for term in relevant_terms) or target_lower in {"exit", "way", "path", "route", "out"}:
                # Show blocker description
                if landmark.landmark_id == "plains_pass":
                    self.ui.echo(
                        "The path north toward the plains is completely blocked. Fallen oaks lie across the trail, "
                        "their massive trunks tangled with gnarled roots that have erupted from the disturbed earth. "
                        "The ground is unstable here, with deep fissures running through the soil. The forest's distortions "
                        "have made this route impassable—the roots writhe and shift, and the debris seems to move when "
                        "you're not looking directly at it. There's no safe way through without the forest's pulse being restored.\n"
                    )
                elif landmark.landmark_id == "mountain_route":
                    self.ui.echo(
                        "The switchback trail that should climb toward the mountains is buried under a massive rockslide. "
                        "Boulders the size of small houses block the trail, and loose scree covers what little of the path "
                        "remains visible. The slide looks recent—fresh scars mark the mountainside above. The way forward "
                        "is completely impassable. Without proper tools and a stable path, attempting to climb over would be suicidal.\n"
                    )
                elif landmark.landmark_id == "riverside_road":
                    self.ui.echo(
                        "The old road follows the curve of a wide, fast-moving river, but the crossing point has been "
                        "completely washed out. The banks are eroded and unstable, with deep gouges where floodwaters have "
                        "torn away the earth. The river itself runs swift and dangerous here, its current pulling at anything "
                        "that enters. The old bridge is gone—only a few broken pilings remain. Without a stable crossing and "
                        "proper gear, the river is impassable.\n"
                    )
                elif landmark.landmark_id == "hollow_echo_cavern_mouth":
                    self.ui.echo(
                        "The cave entrance opens into darkness, descending steeply into the earth. The walls are slick with "
                        "moisture, and the floor drops away into shadow. Without rope, proper lighting, or climbing gear, "
                        "attempting to descend would be incredibly dangerous. The cave seems to echo with distant sounds—water "
                        "dripping, something shifting in the dark. This route might lead somewhere important, but it's not safe "
                        "to explore without the right equipment and preparation.\n"
                    )
                else:
                    # Generic exit blocker message
                    self.ui.echo(
                        f"The way {exit_direction} is blocked. You cannot proceed in this direction.\n"
                    )
                return True
        
        # Check for sand/clay
        if landmark.features.get("has_creek"):
            if target_lower in {"sand", "sandy", "sand bank"}:
                self.ui.echo(
                    "Sandy deposits line the water's edge, perfect for sifting. You could gather sand here if needed.\n"
                )
                return True
            if target_lower in {"clay", "clay bank", "clay deposit"}:
                self.ui.echo(
                    "Rich clay deposits are exposed along the inner curve—dark, sticky earth that would be ideal "
                    "for crafting. You could gather clay here if needed.\n"
                )
                return True
        
        return False

    def _handle_landmark_take(self, landmark: Landmark, target: str) -> bool:
        """Handle taking items from a landmark. Returns True if handled."""
        target_lower = target.lower()
        
        # Check for gold pan
        if landmark.features.get("has_gold_pan") and target_lower in {"gold pan", "pan", "tin pan", "goldpan"}:
            flags = self.state.landmark_flags.get(landmark.landmark_id, {})
            if flags.get("gold_pan_taken", False):
                self.ui.echo("The gold pan is already in your bag.\n")
                return True
            
            # Check inventory space
            inventory_slots = self.state.character.get_stat(
                "inventory_slots",
                timed_modifiers=self.state.timed_modifiers,
                current_day=self.state.day,
            )
            if len(self.state.inventory) >= int(inventory_slots):
                self.ui.echo("Your bag is full. You'll need to make space first.\n")
                return True
            
            # Add to inventory
            self.state.inventory.append("gold_pan")
            if landmark.landmark_id not in self.state.landmark_flags:
                self.state.landmark_flags[landmark.landmark_id] = {}
            self.state.landmark_flags[landmark.landmark_id]["gold_pan_taken"] = True
            self.ui.echo("You pick up the tarnished tin pan and stow it in your bag.\n")
            return True
        
        return False

    def _handle_landmark_gather(self, landmark: Landmark, target: str) -> bool:
        """Handle gathering resources from a landmark. Returns True if handled."""
        target_lower = target.lower()
        
        # Check for food gathering (once per day per landmark)
        if landmark.features.get("has_food", False):
            food_type = landmark.features.get("food_type", "")
            landmark_id = landmark.landmark_id
            
            # Check if food was already gathered today
            flags = self.state.landmark_flags.get(landmark_id, {})
            if flags.get("food_gathered_today", False):
                self.ui.echo("You've already gathered what you can find here today.\n")
                return True
            
            # Check if target matches food type
            food_keywords = {
                "creek_forage": ["watercress", "tuber", "food", "forage", "creek"],
                "creek_aquatic": ["fish", "crab", "food", "forage", "creek", "water"],
                "edible_fungus": ["fungus", "mushroom", "food", "forage"],
                "night_mushrooms": ["mushroom", "night", "food", "forage"],
                "cave_forage": ["spore", "fungus", "grub", "food", "forage", "cave"],
                "mystical_herbs": ["herb", "moss", "blossom", "grass", "resin", "food", "forage", "magical"],
            }
            
            if food_type in food_keywords:
                keywords = food_keywords[food_type]
                if any(kw in target_lower for kw in keywords) or not target:
                    inventory_slots = self.state.character.get_stat(
                        "inventory_slots",
                        timed_modifiers=self.state.timed_modifiers,
                        current_day=self.state.day,
                    )
                    if len(self.state.inventory) >= int(inventory_slots):
                        self.ui.echo("Your bag is full. You'll need to make space first.\n")
                        return True
                    
                    # Add appropriate food item based on landmark type and tags
                    food_item = None
                    
                    if food_type == "creek_forage":
                        # Creek landmarks can yield watercress, tubers, or aquatic creatures
                        if landmark.features.get("has_creek", False):
                            choices = ["watercress", "creek_tuber", "creek_darter", "silt_crab"]
                            food_item = random.choice(choices)
                        else:
                            food_item = random.choice(["watercress", "creek_tuber"])
                    elif food_type == "creek_aquatic":
                        # Specifically aquatic creatures at creek/river landmarks
                        choices = ["creek_darter", "stoneback_trout", "silt_crab"]
                        weights = [0.5, 0.2, 0.3]  # Darter more common, trout rarer
                        food_item = random.choices(choices, weights=weights, k=1)[0]
                    elif food_type == "edible_fungus":
                        food_item = "edible_fungus"
                    elif food_type == "night_mushrooms":
                        food_item = "night_mushroom"
                    elif food_type == "cave_forage":
                        # Cave-mouth landmarks yield spores, grubs, and fungi
                        choices = ["burrow_puff_spores", "barkgrub", "glow_tail_larva"]
                        food_item = random.choice(choices)
                    elif food_type == "mystical_herbs":
                        # Mystical landmarks yield magical plants and fungi
                        # Only if runestones repaired
                        if self.state.act1_repaired_runestones >= 1:
                            choices = [
                                "wisp_petal_blossom", "dreammilk_moss", "veilgrass_tuft",
                                "glow_sap_resin_nodule", "starlace_fungus"
                            ]
                            food_item = random.choice(choices)
                        else:
                            # Fallback to common items if no runestones repaired yet
                            food_item = "edible_mushroom"
                    
                    if food_item is None:
                        food_item = "edible_mushroom"
                    
                    self.state.inventory.append(food_item)
                    
                    # Mark as gathered today
                    if landmark_id not in self.state.landmark_flags:
                        self.state.landmark_flags[landmark_id] = {}
                    self.state.landmark_flags[landmark_id]["food_gathered_today"] = True
                    
                    # Provide flavor text
                    messages = {
                        "creek_forage": "You gather some fresh watercress and a small tuber from the creek's edge.",
                        "creek_aquatic": "You catch some aquatic creatures from the water.",
                        "edible_fungus": "You carefully harvest some edible fungus from the hollow trunk.",
                        "night_mushrooms": "You find a few night mushrooms growing in the moss around the lanterns.",
                        "cave_forage": "You gather spores, grubs, and fungi from near the cave entrance.",
                        "mystical_herbs": "You carefully gather magical herbs and plants from this mystical place.",
                    }
                    base_message = messages.get(food_type, "You gather some food.")
                    
                    # Add optional tag-based foraging flavor
                    try:
                        from .flavor_profiles import get_foraging_flavor
                        flavor_text = get_foraging_flavor(self.state.character)
                        if flavor_text:
                            self.ui.echo(f"{base_message} {flavor_text}\n")
                        else:
                            self.ui.echo(f"{base_message}\n")
                    except Exception:
                        # If flavor fails, use base message
                        self.ui.echo(f"{base_message}\n")
                    return True
        
        # Check for sand/clay gathering at Creek Bend
        if landmark.features.get("has_creek"):
            if target_lower in {"sand", "sandy"}:
                inventory_slots = self.state.character.get_stat(
                    "inventory_slots",
                    timed_modifiers=self.state.timed_modifiers,
                    current_day=self.state.day,
                )
                if len(self.state.inventory) >= int(inventory_slots):
                    self.ui.echo("Your bag is full. You'll need to make space first.\n")
                    return True
                self.state.inventory.append("sand_handful")
                self.ui.echo(
                    "You scoop up a handful of fine sand from the creek bank, letting the water "
                    "drain through your fingers. The sand feels clean and granular—perfect for mixing.\n"
                )
                return True
            if target_lower in {"clay"}:
                inventory_slots = self.state.character.get_stat(
                    "inventory_slots",
                    timed_modifiers=self.state.timed_modifiers,
                    current_day=self.state.day,
                )
                if len(self.state.inventory) >= int(inventory_slots):
                    self.ui.echo("Your bag is full. You'll need to make space first.\n")
                    return True
                self.state.inventory.append("clay_lump")
                self.ui.echo(
                    "You dig into the exposed clay bank, working out a lump of dark, sticky earth. "
                    "It's pliable and rich—exactly what you'd need for binding materials together.\n"
                )
                return True
        
        return False

    def _handle_runestone_repair(self, landmark: Landmark) -> None:
        """Handle the runestone repair workflow."""
        landmark_id = landmark.landmark_id
        
        # Step 1: Physical repair
        success, message = apply_physical_repair(self.state, landmark_id)
        self.ui.echo(message)
        if not success:
            return
        
        # Step 2: Resonance tuning
        success, message = tune_resonance(self.state, landmark_id, self.ui)
        self.ui.echo(message)
        if not success:
            return
        
        # Step 3: Pulse alignment
        success, message = apply_pulse_alignment(self.state, landmark_id)
        self.ui.echo(message)
        if success:
            # Show Echo's reaction
            echo_reaction = get_echo_repair_reaction(self.state, landmark_id)
            self.ui.echo(echo_reaction)
            
            # Update quest state
            update_quest_state_after_repair(self.state, self.runestone_defs)
            
            # Give stability boost when runestone is repaired
            # Ensure minimum stability of 2 for repaired runestone landmarks
            ensure_minimum_stability(self.state, landmark_id, 2)
            
            # Show milestone messages
            repaired_count = self.state.act1_repaired_runestones
            if repaired_count == 1:
                self.ui.echo(
                    "\nThe forest's heartbeat steadies around you. You feel the land respond, "
                    "its magical pulse growing stronger. The first runestone is restored.\n"
                )
            elif repaired_count == 2:
                self.ui.echo(
                    "\nThe forest feels more navigable now. Minor hazards seem to bend away from you, "
                    "and the paths feel clearer. Two runestones restored.\n"
                )
            elif repaired_count >= 3:
                # Check if this is the moment of completion
                from .forest_act1 import is_forest_act1_complete, should_show_completion_narrative
                was_complete = is_forest_act1_complete(self.state)
                self.ui.echo(
                    "\nThe forest's pulse stabilizes completely. The magical grid hums with restored power, "
                    "and you sense the land is grateful. The forest is stabilized. Act I complete.\n"
                )
                # Show completion message if this is the first time
                if should_show_completion_narrative(self.state):
                    self.ui.echo(
                        "\nThe Forest steadies around you. The worst distortions have faded.\n"
                    )
                    from .forest_act1 import mark_completion_acknowledged
                    mark_completion_acknowledged(self.state)

    def _print_landmark_help(self, landmark: Landmark) -> None:
        """Print help text for landmark context."""
        lines = [
            f"At the {landmark.name}:",
            "look — view the landmark",
            "examine <thing> — inspect objects (runestone, gold pan, etc.)",
            "leave / move — return to forest exploration",
            "take <item> — pick up items",
            "gather <resource> — gather materials",
            "repair runestone — repair a fractured runestone",
            "status — review notebook",
            "bag — check supplies",
            "check sky — observe the sky and light conditions",
            "help — show this help",
        ]
        # Check if there's an NPC at this landmark
        from .npc_appearance import get_present_npcs
        present_npcs = get_present_npcs(self.npc_catalog, self.state, landmark.landmark_id)
        if present_npcs or landmark.features.get("has_npc"):
            lines.insert(-1, "talk — speak with someone here")
        self.ui.echo("Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n")
    
    def _handle_dialogue(self, npc: "NPC") -> None:
        """Handle dialogue with an NPC."""
        # Clear content at start of dialogue
        if hasattr(self.ui, 'clear_content'):
            self.ui.clear_content()
        
        from .npcs import NPC
        from .forest_act1 import should_show_completion_narrative
        
        # Determine starting node based on whether intro is done
        npc_flags = self.state.npc_flags.get(npc.npc_id, {})
        
        # Check if Act I is complete and show completion dialogue if not yet acknowledged
        starting_node_id = None
        if npc.npc_id == "forest_hermit" and should_show_completion_narrative(self.state):
            starting_node_id = "forest_hermit_act1_complete"
            session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog, starting_node_id)
            # If completion node doesn't exist or conditions aren't met, fall back to revisit
            if not session and npc_flags.get("forest_hermit_intro_done", False):
                starting_node_id = "forest_hermit_revisit"
                session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog, starting_node_id)
        elif npc_flags.get("forest_hermit_intro_done", False):
            # Use revisit node if available, otherwise use start
            starting_node_id = "forest_hermit_revisit"
            session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog, starting_node_id)
            # If revisit node doesn't exist or conditions aren't met, fall back to friendly revisit
            if not session:
                starting_node_id = "forest_hermit_friendly_revisit"
                session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog, starting_node_id)
            # If still no session, try regular start
            if not session:
                session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog)
        else:
            session = start_dialogue(self.state, npc.npc_id, self.dialogue_catalog)
        
        if not session:
            self.ui.echo(f"{npc.name} doesn't seem interested in talking right now.\n")
            return
        
        # Run dialogue loop
        while True:
            npc_text = get_current_dialogue_text(session, self.state)
            if not npc_text:
                break
            
            self.ui.echo(f"\n{npc.name}: {npc_text}\n")
            
            options = get_current_dialogue_options(session, self.state)
            if not options:
                # No valid options, end dialogue
                break
            
            choice = self.ui.menu("What do you say?", options)
            choice_index = options.index(choice)
            
            is_ended, next_text = step_dialogue(session, self.state, choice_index)
            if is_ended:
                break
            if next_text:
                # Continue to next node
                continue
        
        # Mark completion narrative as acknowledged if we just saw it
        if starting_node_id in ("echo_act1_complete", "forest_hermit_act1_complete"):
            from .forest_act1 import mark_completion_acknowledged
            mark_completion_acknowledged(self.state)
        
        self.ui.echo(f"\nYou finish your conversation with {npc.name}.\n")
        
        # If we're in the glade, return to glade view
        if self.state.active_zone == "glade":
            self._render_glade_view()

    def _handle_approach_echo(self) -> None:
        """Handle approaching Echo and opening the interaction menu."""
        # Clear content at start of interaction
        if hasattr(self.ui, 'clear_content'):
            self.ui.clear_content()
        self.ui.echo("You approach Echo. She watches you with patient, lidless eyes, her coils shifting slightly as you draw near. The radio emits a soft, welcoming pulse.\n")
        
        # Show interaction menu
        while True:
            options = ["Speak to Echo", "Pet Echo", "Hug Echo", "Boop Echo", "Back"]
            choice = self.ui.menu("What would you like to do?", options)
            
            if choice == "Back":
                # Return to glade view
                self._render_glade_view()
                break
            elif choice == "Speak to Echo":
                self._handle_echo_dialogue()
                # After dialogue, return to interaction menu
                continue
            elif choice == "Pet Echo":
                self._handle_pet_echo()
                # After petting, return to interaction menu
                continue
            elif choice == "Hug Echo":
                self._handle_hug_echo()
                # After hugging, return to interaction menu
                continue
            elif choice == "Boop Echo":
                self._handle_boop_echo()
                # After booping, return to interaction menu
                continue

    def _handle_echo_dialogue(self) -> None:
        """Handle dialogue with Echo using the dialogue system."""
        # Clear content at start of dialogue
        if hasattr(self.ui, 'clear_content'):
            self.ui.clear_content()
        
        # Check if Act I is complete and show completion dialogue if not yet acknowledged
        from .forest_act1 import should_show_completion_narrative
        starting_node_id = None
        if should_show_completion_narrative(self.state):
            starting_node_id = "echo_act1_complete"
        
        # Start dialogue with Echo
        session = start_dialogue(self.state, "echo", self.dialogue_catalog, starting_node_id)
        
        if not session:
            # Fallback if no dialogue is available
            self.ui.echo("[RADIO] Static pulses with warmth, but no clear words emerge.\n")
            return
        
        # Run dialogue loop
        while True:
            npc_text = get_current_dialogue_text(session, self.state)
            if not npc_text:
                break
            
            # Check if radio version is too low for full sentences
            # Before v2, Echo should only speak in impressionistic fragments
            if self.state.radio_version < 2 and npc_text.startswith("[RADIO]"):
                # Check if this looks like a full sentence (has multiple periods or is very long)
                # Impressionistic fragments are short and use ellipses or single fragments
                text_body = npc_text[7:].strip()  # Remove "[RADIO]" prefix
                # Count sentence-ending punctuation
                sentence_endings = text_body.count('.') + text_body.count('!') + text_body.count('?')
                # If it has multiple sentences or is very long, it's probably a full sentence
                if sentence_endings > 1 or (len(text_body) > 100 and sentence_endings > 0):
                    # Show fallback impressionistic message instead
                    import random
                    impressions = [
                        "[RADIO] Warm static. Curious pulse.",
                        "[RADIO] A rush of forest scents through the static.",
                        "[RADIO] Orange static blooms. Gratitude. Warmth.",
                        "[RADIO] Blue pulse thrums. Emotions without words.",
                        "[RADIO] Static crackles. Sun-hot warmth. Distant hissing.",
                    ]
                    npc_text = random.choice(impressions)
            
            self.ui.echo(f"\n{npc_text}\n")
            
            options = get_current_dialogue_options(session, self.state)
            if not options:
                # No valid options, end dialogue
                break
            
            choice = self.ui.menu("What do you say?", options)
            choice_index = options.index(choice)
            
            is_ended, next_text = step_dialogue(session, self.state, choice_index)
            if is_ended:
                break
            if next_text:
                # Continue to next node
                continue
        
        # Mark completion narrative as acknowledged if we just saw it
        if starting_node_id == "echo_act1_complete":
            from .forest_act1 import mark_completion_acknowledged
            mark_completion_acknowledged(self.state)
        
        self.ui.echo("\nYou finish your conversation with Echo.\n")
        
        # If we're in the glade, return to glade view
        if self.state.active_zone == "glade":
            self._render_glade_view()

    def _handle_pet_echo(self) -> None:
        """Handle petting Echo interaction."""
        description, gained_rapport = pet_echo(self.state)
        self.ui.echo(f"\n{description}\n")
        if gained_rapport:
            current_rapport = get_rapport(self.state, "echo")
            self.ui.echo(f"Echo's rapport: {current_rapport}\n")

    def _handle_hug_echo(self) -> None:
        """Handle hugging Echo interaction - a warm, heartfelt action."""
        from .echo_vore import trigger_echo_belly_shelter
        
        description, gained_rapport, vore_triggered, entry_method = hug_echo(self.state)
        
        if vore_triggered:
            # Vore triggered - move to belly area
            trigger_echo_belly_shelter(self.state, self.ui, entry_method=entry_method)
            return
        
        self.ui.echo(f"\n{description}\n")
        if gained_rapport:
            current_rapport = get_rapport(self.state, "echo")
            self.ui.echo(f"Echo's rapport: {current_rapport}\n")

    def _handle_boop_echo(self) -> None:
        """Handle booping Echo interaction - a playful action."""
        from .echo_vore import trigger_echo_belly_shelter
        
        description, gained_rapport, vore_triggered, entry_method = boop_echo(self.state)
        
        if vore_triggered:
            # Vore triggered - move to belly area
            trigger_echo_belly_shelter(self.state, self.ui, entry_method=entry_method)
            return
        
        self.ui.echo(f"\n{description}\n")
        if gained_rapport:
            current_rapport = get_rapport(self.state, "echo")
            self.ui.echo(f"Echo's rapport: {current_rapport}\n")

    def explore_zone(self, zone_id: str) -> str | None:
        """Handle repeated exploration choices within a specific zone."""
        self.state.stage = f"explore:{zone_id}"
        self.state.active_zone = zone_id
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        zone_label = zone_id.replace("_", " ").title()
        actions_taken = self.state.zone_steps.get(zone_id, 0)
        
        # Clear content and show zone description when entering
        if hasattr(self.ui, 'clear_content'):
            self.ui.clear_content()
        depth = self.state.zone_depths.get(zone_id, 0)
        self._describe_zone(zone_id, depth=depth)
        
        # Check if we're entering with a landmark already active
        current_landmark = self._get_current_landmark()
        if current_landmark:
            # Re-enter landmark context
            self._enter_landmark(current_landmark, zone_id=zone_id)
        else:
            self._set_scene_highlights(
                zone_id=zone_id,
                depth=depth,
                extras=(),
            )
            if zone_id == "forest":
                self.ui.echo(
                    "\nThe forest calls. Commands: move, look, camp, return, status, bag, help.\n"
                )
            else:
                self.ui.echo(
                    f"\nThe {zone_label} awaits. Commands: look, move, camp, return, status, bag, help.\n"
                )
        
        while True:
            # Check if we're at a landmark
            current_landmark = self._get_current_landmark()
            if current_landmark:
                # Handle landmark context
                depth = self.state.zone_depths.get(zone_id, 0)
                extras: list[str] = []
                if current_landmark.features.get("has_runestone"):
                    extras.append("runestone")
                if current_landmark.features.get("has_gold_pan"):
                    flags = self.state.landmark_flags.get(current_landmark.landmark_id, {})
                    if not flags.get("gold_pan_taken", False):
                        extras.append("gold pan")
                if current_landmark.features.get("has_creek"):
                    extras.append("sand")
                    extras.append("clay")
                self._set_scene_highlights(zone_id=zone_id, depth=depth, extras=tuple(extras))
            else:
                depth = self.state.zone_depths.get(zone_id, 0)
                self._set_scene_highlights(zone_id=zone_id, depth=depth, extras=None)
            
            # Check for collapse - condition increases risk
            if self.state.stamina <= 0:
                from .combat import get_condition_effects, should_force_retreat
                condition_effects = get_condition_effects(self.state)
                # Base collapse chance when stamina hits 0, modified by condition
                base_collapse_chance = 0.7  # 70% base chance
                collapse_risk = min(1.0, base_collapse_chance * condition_effects["collapse_risk_multiplier"])
                # If condition is high and stamina is 0, always collapse
                if should_force_retreat(self.state) or random.random() < collapse_risk:
                    self._collapse_from_exhaustion(zone_id=zone_id, stamina_max=stamina_max)
                    return
                # Otherwise, just set stamina to 0 and continue (very low stamina)
                self.state.stamina = 0.0
            command = self._prompt_command(f"{zone_label} command")
            if command is None:
                self._report_invalid_command(zone_id)
                continue
            outcome = self._dispatch_forest_command(
                command=command,
                zone_id=zone_id,
                stamina_max=stamina_max,
            )
            if outcome == "explore":
                actions_taken += 1
                self.state.zone_steps[zone_id] = actions_taken
                continue
            if outcome == "stay":
                continue
            if outcome == "leave":
                return
            if outcome == "quit":
                return "quit"

    def _camp_phase(self, *, zone_id: str, stamina_max: float) -> None:
        from .time_of_day import advance_time_of_day
        self.state.stage = "camp"
        self.state.active_zone = zone_id
        # Track that player rested at camp (best rest)
        self.state.rest_type = "camp"
        partial_rest = max(0.0, math.floor(stamina_max * 0.75))
        self.state.pending_stamina_floor = max(
            self.state.pending_stamina_floor, min(stamina_max, partial_rest)
        )
        # Advance time when making camp (camping takes time)
        advance_time_of_day(self.state, steps=1)
        self.ui.echo("You make camp and rest by the fire.\n")
        
        # Add optional tag-based resting flavor
        try:
            from .flavor_profiles import get_resting_flavor
            flavor_text = get_resting_flavor(self.state.character, context="camp")
            if flavor_text:
                self.ui.echo(f"{flavor_text}\n")
        except Exception:
            pass
        
        # Check for Blue Fireflies event (Spring night at Glade)
        if zone_id == "glade":
            from .micro_quests import check_blue_fireflies_event, trigger_blue_fireflies_event
            if check_blue_fireflies_event(self.state):
                trigger_blue_fireflies_event(self.state, self.ui)
        
        # Check for Echo check-in or favor events at Glade
        if zone_id == "glade":
            from .micro_quests import check_echo_checkin, trigger_echo_checkin, check_echo_favor, trigger_echo_favor
            if check_echo_checkin(self.state):
                trigger_echo_checkin(self.state, self.ui)
            elif check_echo_favor(self.state):
                trigger_echo_favor(self.state, self.ui)
        
        # Check for rare lore events at camp
        rare_events = self._get_rare_lore_events()
        if rare_events:
            event = rare_events.check_for_event(self.state, zone_id, self.landmarks)
            if event:
                text = rare_events.trigger_event(event, self.state)
                self.ui.echo(f"\n{text}\n")
        
        # Check for Kirin intro at landmark with high stability
        current_landmark = self._get_current_landmark()
        if current_landmark and can_trigger_kirin_intro(self.state):
            stability = get_path_stability(self.state, current_landmark.landmark_id)
            if stability >= 2:
                trigger_kirin_intro(self.state, self.ui, context=current_landmark.landmark_id)
        
        # Track if ash is available (only after cooking or brewing)
        ash_available = False
        
        # Helper to get camp actions list
        def get_camp_actions() -> str:
            actions = ["brew", "cook", "eat", "drink", "bag", "status", "sleep", "help"]
            if ash_available:
                actions.insert(4, "gather ash")
            if can_use_kirin_travel(self.state):
                actions.insert(-2, "travel with kirin")
            return ", ".join(actions)
        
        self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
        
        # Camp command loop
        while True:
            command = self._prompt_command("Camp command")
            if command is None:
                self._report_invalid_command("camp")
                continue
            verb = command.verb
            args = command.args
            
            if verb == "brew":
                self._brew_menu(context="camp")
                ash_available = True  # Ash is now available after brewing
                # Reprint camp menu to show new options
                self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
                continue
            if verb == "cook":
                self._handle_cook(at_camp=True)
                ash_available = True  # Ash is now available after cooking
                # Reprint camp menu to show new options
                self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
                continue
            if verb == "eat":
                target = self._normalize_target(args)
                if target:
                    self._handle_eat(target)
                    # Reprint camp menu to show current options
                    self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
                else:
                    self.ui.echo("Eat what?\n")
                continue
            if verb == "drink":
                target = self._normalize_target(args)
                if target:
                    self._handle_drink(target)
                    # Reprint camp menu to show current options
                    self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
                else:
                    self.ui.echo("Drink what?\n")
                continue
            if verb == "fill":
                target = self._normalize_target(args)
                self._handle_fill(target if target else "")
                continue
            if verb == "gather":
                target = self._normalize_target(args)
                if target and target.lower() in {"ash", "ashes"}:
                    if not ash_available:
                        self.ui.echo(
                            "There's no ash to gather yet. You need to cook or brew something first to create ash.\n"
                        )
                        continue
                    inventory_slots = self.state.character.get_stat(
                        "inventory_slots",
                        timed_modifiers=self.state.timed_modifiers,
                        current_day=self.state.day,
                    )
                    if len(self.state.inventory) >= int(inventory_slots):
                        self.ui.echo("Your bag is full. You'll need to make space first.\n")
                        continue
                    self.state.inventory.append("ash_scoop")
                    self.ui.echo(
                        "You scoop up a handful of fine ash from the campfire's remains. "
                        "It's cool and powdery—perfect for mixing into mortar.\n"
                    )
                    ash_available = False  # Ash has been gathered
                    continue
                self.ui.echo("You can only gather ash at camp.\n")
                continue
            if verb == "bag":
                self._show_field_bag()
                continue
            if verb == "status":
                self._show_notebook(zone_id=zone_id, stamina_max=stamina_max)
                continue
            if verb == "check sky":
                from .sky import get_sky_description
                description = get_sky_description(self.state)
                self.ui.echo(f"{description}\n")
                continue
            if verb == "help":
                help_lines = [
                    "Camp commands:",
                    "  brew — prepare teas and craft items",
                    "  cook — cook meals from ingredients",
                    "  eat <item> — eat food from your inventory",
                    "  drink <item> — drink tea or water from your water bottle",
                    "  bag — check supplies",
                    "  status — review notebook",
                    "  sleep — rest until the next day",
                    "  help — show this help",
                ]
                if ash_available:
                    help_lines.insert(5, "  gather ash — collect ash from the campfire")
                if can_use_kirin_travel(self.state):
                    help_lines.insert(-2, "  travel with kirin — fast travel to familiar landmarks")
                self.ui.echo("\n".join(help_lines) + "\n")
                continue
            if verb in {"travel"}:
                target = self._normalize_target(args)
                if target and "kirin" in target.lower():
                    self._handle_kirin_travel(zone_id=zone_id)
                    # Reprint camp menu
                    self.ui.echo(f"Camp actions: {get_camp_actions()}.\n")
                    continue
            if verb in {"sleep", "rest"}:
                # Check for Act I completion narrative before sleeping
                from .forest_act1 import should_show_completion_narrative
                if should_show_completion_narrative(self.state):
                    self.ui.echo(
                        "\nAs you settle in for the night, a dream comes to you—vivid and clear. "
                        "You see the forest's ley-lines pulsing with restored rhythm, paths remembering themselves, "
                        "the land growing calmer. The fractured runestones you've mended glow with steady light, "
                        "anchoring the magical grid. You wake with a sense of accomplishment, knowing the forest "
                        "has stabilized. The way forward feels clearer now.\n"
                    )
                    from .forest_act1 import mark_completion_acknowledged
                    mark_completion_acknowledged(self.state)
                
                # Advance time significantly when sleeping (sleep advances to next day)
                from .time_of_day import advance_time_of_day
                # Advance to Night, then the new_day() call will reset to Dawn
                advance_time_of_day(self.state, steps=2)
                break
            if verb == "wait":
                self.ui.echo("You wait by the fire. Use 'sleep' to rest until the next day.\n")
                continue
            self._report_invalid_command("camp")
        
        self._summarize_day("Camp Summary", stamina_max, zone_id=zone_id)

    def _perform_explore_action(self, *, zone_id: str) -> None:
        from .time_of_day import advance_time_of_day
        depth = self.state.zone_depths.get(zone_id, 0) + 1
        
        # Apply depth gating based on runestone repairs
        if zone_id == "forest" and not should_allow_deep_depth_roll(self.state, depth):
            # Soft gate: reduce depth increment chance
            import random
            if random.random() > 0.3:  # 70% chance to stay at current depth
                depth = self.state.zone_depths.get(zone_id, 0)
        
        self.state.zone_depths[zone_id] = depth
        
        # Check for landmark discovery (only in forest zone)
        if zone_id == "forest":
            landmark = self.landmarks.select_for_discovery(self.state, depth, discovery_chance=0.15)
            if landmark:
                self._enter_landmark(landmark, zone_id=zone_id)
                # Apply stamina cost modifier
                base_cost = 0.9  # Reduced from 1.0 to allow ~10% more exploration
                modifier = get_stamina_cost_modifier(self.state, depth)
                self.state.stamina = max(0.0, self.state.stamina - base_cost * modifier)
                return
        
        # Check for creature encounter first (before normal events)
        encounter_triggered = False
        if zone_id == "forest" and self.encounter_engine:
            encounter_triggered = self._maybe_trigger_creature_encounter(
                zone_id=zone_id,
                depth=depth,
            )
        
        # Normal event flow with forest effects (skip if encounter was triggered)
        if not encounter_triggered:
            event = self.events.draw(self.state, depth=depth)
            extras: list[str] = []
            
            # Check if this event should be handled by the new encounter system
            if event and event.event_type == "encounter":
                creature_id = event.effects.get("creature_id")
                if creature_id and self.encounter_engine:
                    # Check if we have encounters for this creature in the new system
                    creature_encounters = [
                        enc for enc in self.encounter_engine.encounters.values()
                        if enc.creature_id == creature_id
                    ]
                    if creature_encounters:
                        # Use new encounter system instead of old event system
                        season = self.state.get_season_name()
                        encounter = self.encounter_engine.select_encounter_for_creature(
                            self.state,
                            creature_id,
                            depth,
                            season,
                        )
                        if encounter:
                            # Run the new encounter system (this handles all UI and state changes)
                            self._run_encounter(encounter, depth=depth)
                            # Skip old event processing entirely
                            encounter_triggered = True
            
            # Only process old event system if new encounter system didn't handle it
            if not encounter_triggered:
                if event:
                    creature_id = event.effects.get("creature_id")
                    if creature_id:
                        creature_data = self.creatures.get(creature_id, {})
                        extras.append(creature_data.get("name", creature_id.replace("_", " ")))
                
                self._set_scene_highlights(
                    zone_id=zone_id,
                    depth=depth,
                    extras=tuple(extras),
                )
                if not event:
                    self.ui.echo("The woods are quiet.\n")
                else:
                    summary = self.events.apply(self.state, event)
                    if event.event_type == "encounter":
                        encounter_text = self._resolve_encounter(event)
                        summary = summary.rstrip("\n") + "\n" + encounter_text
                    
                    # Add optional tag-based exploration flavor (for non-encounter events)
                    if event.event_type != "encounter":
                        try:
                            from .flavor_profiles import get_exploration_flavor
                            flavor_text = get_exploration_flavor(self.state.character)
                            if flavor_text:
                                summary = summary.rstrip("\n") + f"\n{flavor_text}"
                        except Exception:
                            # If flavor fails, continue without it
                            pass
                    
                    if not summary.endswith("\n"):
                        summary = summary + "\n"
                    self.ui.echo(summary)
        
        # Apply stamina cost with modifier
        # Tuned: base cost reduced slightly to allow more exploration per day
        base_cost = 0.9  # Reduced from 1.0 to allow ~10% more exploration
        modifier = get_stamina_cost_modifier(self.state, depth)
        self.state.stamina = max(0.0, self.state.stamina - base_cost * modifier)
        
        # Advance time of day (exploration takes time)
        advance_time_of_day(self.state, steps=1)
        
        # Check for Kirin foreshadowing (small chance during exploration)
        if zone_id == "forest" and self.state.kirin_interest_level >= 1:
            self._maybe_trigger_kirin_foreshadowing()

    def _return_to_glade(self, *, zone_id: str, stamina_max: float) -> None:
        from .time_of_day import advance_time_of_day
        self.state.stage = "return"
        self.state.active_zone = "glade"
        self.state.zone_steps.pop(zone_id, None)
        self.state.current_landmark = None  # Clear landmark context
        # Clear sheltered flag when returning to glade (back to normal outdoor conditions)
        self.state.is_sheltered = False
        # Track that player returned to glade (safe rest, same as camp)
        self.state.rest_type = "camp"
        # Advance time when returning (travel takes time)
        advance_time_of_day(self.state, steps=1)
        self.ui.echo(
            "You wind back along familiar glade paths and set your gear down.\n"
        )
        self.state.stamina = stamina_max
        self._summarize_day("Glade Summary", stamina_max, zone_id=zone_id)
        self.state.zone_depths.pop(zone_id, None)

    def _collapse_from_exhaustion(self, *, zone_id: str, stamina_max: float) -> None:
        """Handle collapse from exhaustion using the unified outcome system."""
        from .time_of_day import advance_time_of_day
        self.state.stage = "collapse"
        
        # Use COLLAPSE outcome
        context = OutcomeContext(
            source_id="exhaustion",
            collapse_severity=1.0,
        )
        resolve_encounter_outcome(
            self.state,
            EncounterOutcome.COLLAPSE,
            context=context,
            ui=self.ui,
        )
        
        # Advance time significantly (collapse represents significant time passing)
        # Advance to Night, then new_day() will reset to Dawn
        advance_time_of_day(self.state, steps=2)
        
        # Advance day (collapse represents significant time passing)
        self.state.new_day(self.season_config)
        # Apply Echo vore tension decay on new day
        from .echo_vore import update_echo_vore_tension
        update_echo_vore_tension(self.state, increase=False)
        
        # Summarize the day after collapse
        zone_steps_snapshot = dict(self.state.zone_steps)
        zone_depths_snapshot = dict(self.state.zone_depths)
        summary_zone = self.state.active_zone
        
        self._summarize_day(
            "Exhaustion Recovery",
            stamina_max,
            zone_id=summary_zone,
            zone_steps_snapshot=zone_steps_snapshot,
            zone_depths_snapshot=zone_depths_snapshot,
        )
        self._set_scene_highlights(
            zone_id=summary_zone,
            depth=self.state.zone_depths.get(summary_zone, 0),
            extras=(),
        )

    def _summarize_day(
        self,
        title: str,
        stamina_max: float,
        *,
        zone_id: str | None,
        zone_steps_snapshot: dict[str, int] | None = None,
        zone_depths_snapshot: dict[str, int] | None = None,
    ) -> None:
        # Recover condition at camp (Glade rest)
        if self.state.rest_type == "camp" and self.state.condition > 0:
            from .combat import recover_condition_at_camp, get_condition_label
            old_condition = self.state.condition
            recover_condition_at_camp(self.state)
            if self.state.condition < old_condition:
                self.ui.echo(
                    f"Rest at camp helps you recover. Condition improves from "
                    f"{get_condition_label(old_condition)} to "
                    f"{get_condition_label(self.state.condition)}.\n"
                )
        
        self.ui.heading(title)
        self.ui.echo(
            f"Day {self.state.day} closes with stamina "
            f"{self.state.stamina:.0f}/{stamina_max:.0f}.\n"
        )
        self._echo_status_snapshot(
            zone_id=zone_id,
            zone_steps=zone_steps_snapshot,
            zone_depths=zone_depths_snapshot,
        )
        before_inventory = Counter(self._day_start_inventory)
        after_inventory = Counter(self.state.inventory)
        gained = after_inventory - before_inventory
        lost = before_inventory - after_inventory
        inventory_lines: list[str] = []
        for item, count in sorted(gained.items()):
            inventory_lines.append(f"  +{count} {item}")
        for item, count in sorted(lost.items()):
            inventory_lines.append(f"  -{count} {item}")
        if inventory_lines:
            self.ui.echo("Inventory shifts:\n" + "\n".join(inventory_lines) + "\n")
        else:
            self.ui.echo("Inventory holds steady.\n")

        rapport_changes: list[str] = []
        all_creatures = set(self._day_start_rapport) | set(self.state.rapport)
        for creature in sorted(all_creatures):
            before = self._day_start_rapport.get(creature, 0)
            after = self.state.rapport.get(creature, 0)
            delta = after - before
            if delta:
                sign = "+" if delta > 0 else ""
                rapport_changes.append(f"  {creature}: {sign}{delta} → {after}")
        if rapport_changes:
            self.ui.echo("Rapport shifts:\n" + "\n".join(rapport_changes) + "\n")
        else:
            self.ui.echo("No rapport shifts today.\n")
        self._echo_current_rapport()

    def _echo_current_rapport(self) -> None:
        if not self.state.rapport:
            self.ui.echo("No bonds yet tie you to the forest's denizens.\n")
            return
        lines = [
            f"  {creature}: {score}"
            for creature, score in sorted(self.state.rapport.items())
        ]
        self.ui.echo("Glade rapport:\n" + "\n".join(lines) + "\n")

    def _echo_status_snapshot(
        self,
        *,
        zone_id: str | None,
        zone_steps: dict[str, int] | None = None,
        zone_depths: dict[str, int] | None = None,
    ) -> None:
        active_zone = zone_id or self.state.active_zone
        zone_label = active_zone.replace("_", " ").title()
        steps_source = zone_steps if zone_steps is not None else self.state.zone_steps
        depths_source = (
            zone_depths if zone_depths is not None else self.state.zone_depths
        )
        depth = depths_source.get(active_zone, 0)
        persistent_steps = steps_source.get(active_zone, 0)
        hunger_status = f"{self.state.days_without_meal} day{'s' if self.state.days_without_meal != 1 else ''} without a proper meal"
        from .combat import get_condition_label
        condition_label = get_condition_label(self.state.condition)
        snapshot = [
            f"Hunger: {hunger_status}",
            f"Condition: {condition_label}",
            f"Active zone: {zone_label}",
            f"Trail depth reached: {depth}",
            f"Trail markers logged: {persistent_steps}",
        ]
        self.ui.echo(
            "Status notebook:\n" + "\n".join(f"  {line}" for line in snapshot) + "\n"
        )

    def _show_notebook(self, *, zone_id: str, stamina_max: float) -> None:
        from .time_of_day import get_time_of_day
        zone_label = zone_id.replace("_", " ").title()
        depth = self.state.zone_depths.get(zone_id, 0)
        persistent_steps = self.state.zone_steps.get(zone_id, 0)
        self.ui.heading("Notebook — Field Status")
        character = self.state.character
        name = character.name or "Wanderer"
        race = character.race_id.replace("_", " ").title()
        from .combat import get_condition_label
        condition_label = get_condition_label(self.state.condition)
        time_of_day = get_time_of_day(self.state)
        season_name = self.state.get_season_name().title()
        # Format season with early/mid/late prefix if needed
        if self.state.day_in_season <= 5:
            season_prefix = "Early "
        elif self.state.day_in_season <= 9:
            season_prefix = "Mid "
        else:
            season_prefix = "Late "
        lines = [
            f"Name: {name}",
            f"Race: {race}",
            f"Day: {self.state.day} ({season_prefix}{season_name})",
            f"Time: {time_of_day.to_display_name()}",
            f"Location: {zone_label}",
            f"Stamina: {self.state.stamina:.0f}/{stamina_max:.0f}",
            f"Hunger: {self.state.days_without_meal} day{'s' if self.state.days_without_meal != 1 else ''} without a proper meal",
            f"Condition: {condition_label}",
        ]
        # Show vore settings (read-only)
        vore_status = "Enabled" if self.state.vore_enabled else "Disabled"
        lines.append(f"Vore scenes: {vore_status}")
        pred_status = "Enabled" if self.state.player_as_pred_enabled else "Disabled"
        lines.append(f"Player as predator: {pred_status}")
        if zone_id == "forest":
            lines.append(f"Depth: {depth} ({self._depth_band(depth)})")
        else:
            lines.append(f"Depth: {depth}")
        if persistent_steps:
            lines.append(f"Trail markers: {persistent_steps}")
        
        # Act I quest progress
        from .forest_act1 import get_forest_act1_progress_summary, init_forest_act1_state
        init_forest_act1_state(self.state)
        summary = get_forest_act1_progress_summary(self.state)
        lines.append(f"\nForest Ley-Lines: {summary['status']}")
        if summary['status'] != "Stabilized":
            lines.append(f"  {summary['progress']}")
        
        if self.state.rapport:
            lines.append("\nRapport:")
            for creature, score in sorted(self.state.rapport.items()):
                lines.append(f"  {creature}: {score}")
        else:
            lines.append("\nRapport: none")
        self.ui.echo("\n".join(lines) + "\n")

    def _show_field_bag(self) -> None:
        self.ui.heading("Field Bag")
        if not self.state.inventory:
            self.ui.echo("Your bag is empty.\n")
            return
        counts = Counter(self.state.inventory)
        lines = [f"  {item}: {count}" for item, count in sorted(counts.items())]
        self.ui.echo("Supplies gathered:\n" + "\n".join(lines) + "\n")
    
    def _show_landmarks(self) -> None:
        """Show known landmarks and their path stability."""
        self.ui.heading("Known Landmarks")
        known = get_known_landmarks_with_stability(self.state, self.landmarks)
        if not known:
            self.ui.echo("You haven't discovered any landmarks yet. Explore the forest to find them.\n")
            return
        lines = []
        for landmark, stability in known:
            stability_label = get_stability_label(stability)
            lines.append(f"  {landmark.name} — {stability_label}")
        self.ui.echo("The forest remembers these places:\n" + "\n".join(lines) + "\n")
    
    def _handle_eat(self, item_name: str) -> bool:
        """
        Handle eating a food item.
        
        Args:
            item_name: Name of the item to eat
            
        Returns:
            True if item was eaten, False otherwise
        """
        # Normalize item name
        item_name_lower = item_name.lower().replace(" ", "_")
        
        # Check if item exists in inventory
        if item_name_lower not in self.state.inventory:
            # Try to find by partial match
            matching_items = [
                item for item in self.state.inventory
                if item_name.lower() in item.lower() or item.lower() in item_name.lower()
            ]
            if not matching_items:
                self.ui.echo(f"You don't have any {item_name}.\n")
                return False
            item_name_lower = matching_items[0]
        
        # Check if it's a food item
        food_data = self.food_items.get(item_name_lower)
        if not food_data:
            self.ui.echo(f"You can't eat {item_name_lower}.\n")
            return False
        
        # Remove from inventory
        try:
            self.state.inventory.remove(item_name_lower)
        except ValueError:
            self.ui.echo(f"You don't have any {item_name_lower}.\n")
            return False
        
        # Handle based on food type
        food_type = food_data.get("type", "snack")
        food_name = food_data.get("name", item_name_lower.replace("_", " ").title())
        
        if food_type == "meal":
            # Proper meal resets hunger
            self._ate_proper_meal_yesterday = True
            self.ui.echo(
                f"You eat {food_name}. {food_data.get('long_description', '')}\n"
                "The warmth of a proper meal settles in, restoring your connection to the forest's rhythm.\n"
            )
        elif food_type == "snack":
            # Snack prevents hunger from worsening
            self.state.ate_snack_today = True
            self.ui.echo(
                f"You eat {food_name}. {food_data.get('long_description', '')}\n"
                "It's enough to keep you going, but not a proper meal.\n"
            )
        else:
            self.ui.echo(f"You eat {food_name}.\n")
        
        return True
    
    def _handle_drink(self, item_name: str) -> bool:
        """
        Handle drinking a tea or water.
        
        Args:
            item_name: Name of the item to drink
            
        Returns:
            True if item was drunk, False otherwise
        """
        # Normalize item name
        item_name_lower = item_name.lower().replace(" ", "_")
        
        # Check for water bottle
        if item_name_lower in {"water", "water_bottle", "bottle"}:
            if "water_bottle" not in self.state.inventory:
                self.ui.echo("You don't have a water bottle.\n")
                return False
            
            # Check if water bottle is filled (tracked via a flag or just allow drinking)
            if self.state.water_drinks_today >= 4:
                self.ui.echo("You've already drunk enough water today. Your stomach feels full.\n")
                return False
            
            # Drink water - +1 stamina boost
            self.state.water_drinks_today += 1
            stamina_max = self.state.character.get_stat(
                "stamina_max",
                timed_modifiers=self.state.timed_modifiers,
                current_day=self.state.day,
            )
            self.state.stamina = min(stamina_max, self.state.stamina + 1.0)
            self.ui.echo(
                f"You take a refreshing drink from your water bottle. "
                f"Stamina restored. ({self.state.water_drinks_today}/4 drinks today)\n"
            )
            return True
        
        # Check if item exists in inventory
        if item_name_lower not in self.state.inventory:
            # Try to find by partial match
            matching_items = [
                item for item in self.state.inventory
                if item_name.lower() in item.lower() or item.lower() in item_name.lower()
            ]
            if not matching_items:
                self.ui.echo(f"You don't have any {item_name}.\n")
                return False
            item_name_lower = matching_items[0]
        
        # Special handling for wayfinding_tea
        if item_name_lower == "wayfinding_tea":
            # Remove tea from inventory
            try:
                self.state.inventory.remove(item_name_lower)
            except ValueError:
                self.ui.echo(f"You don't have any {item_name_lower}.\n")
                return False
            
            # Set wayfinding_ready flag
            self.state.wayfinding_ready = True
            
            # Check if player has at least 1 repaired runestone
            if self.state.act1_repaired_runestones < 1:
                self.ui.echo(
                    "You drink the Wayfinding Tea. Its warmth spreads through you, and you sense the Forest's paths "
                    "overlapping in your mind—but something blocks you from using this power fully. "
                    "Perhaps the Forest needs more stabilization first.\n"
                )
            else:
                self.ui.echo(
                    "You drink the Wayfinding Tea. Its warmth spreads through you, and the paths you've walked "
                    "seem to fold together in your mind. The Forest remembers, and so do you. "
                    "For a brief time, you can step through the space between places you know well.\n"
                )
            
            return True
        
        # Check if it's a tea
        tea_data = self.teas.get(item_name_lower)
        if not tea_data:
            self.ui.echo(f"You can't drink {item_name_lower}.\n")
            return False
        
        # Remove tea from inventory
        try:
            self.state.inventory.remove(item_name_lower)
        except ValueError:
            self.ui.echo(f"You don't have any {item_name_lower}.\n")
            return False
        
        # Apply tea effects
        duration = int(tea_data.get("duration_days", 1))
        modifiers = tea_data.get("modifiers", [])
        if modifiers:
            self.state.timed_modifiers.append(
                TimedModifier(
                    source=f"drink:{item_name_lower}:{self.state.day}",
                    modifiers=modifiers,
                    expires_on_day=self.state.day + duration,
                )
            )
        
        tea_name = tea_data.get("name", item_name_lower.replace("_", " ").title())
        description = tea_data.get("description", "")
        
        if description:
            # Enhance description with race-aware flavor
            enhanced_description = enhance_tea_description(
                description,
                item_name_lower,
                self.state.character.race_id,
            )
            self.ui.echo(f"You drink {tea_name}. {enhanced_description}\n")
        else:
            self.ui.echo(f"You drink {tea_name}.\n")
        
        if duration > 1:
            self.ui.echo(f"The effects will last for {duration} days.\n")
        
        return True
    
    def _handle_fill(self, target: str) -> bool:
        """
        Handle filling the water bottle at a water source.
        
        Args:
            target: What to fill (should be water_bottle or water)
            
        Returns:
            True if water bottle was filled, False otherwise
        """
        if "water_bottle" not in self.state.inventory:
            self.ui.echo("You don't have a water bottle.\n")
            return False
        
        target_lower = target.lower() if target else ""
        if target_lower and target_lower not in {"water", "bottle", "water_bottle"}:
            self.ui.echo("You can only fill your water bottle with water.\n")
            return False
        
        # Check if we're at a water source
        current_landmark = self._get_current_landmark()
        has_water = False
        water_source = ""
        
        if current_landmark:
            # Check landmark for water source
            if current_landmark.features.get("has_creek"):
                has_water = True
                water_source = "the creek"
        else:
            # Check if we're in a zone with water (forest has streams)
            if self.state.active_zone == "forest":
                has_water = True
                water_source = "a nearby stream"
        
        if not has_water:
            self.ui.echo("There's no fresh water source here to fill your bottle from.\n")
            return False
        
        # Water bottle is always "filled" - the limitation is on drinking, not filling
        self.ui.echo(
            f"You fill your water bottle from {water_source}. "
            "The bottle is now full and ready to drink from.\n"
        )
        return True
    
    def _maybe_trigger_kirin_foreshadowing(self) -> None:
        """
        Trigger Kirin foreshadowing events based on interest level.
        These are flavor-only hints, not full encounters.
        """
        import random
        
        # Base chance increases with interest level
        # Tuned: Kirin should be rare early, more common as Act I progresses
        base_chance = {
            1: 0.03,  # 3% chance after first repair (rare, like a rumor)
            2: 0.06,  # 6% chance after second repair (still uncommon)
            3: 0.12,  # 12% chance after third repair (more noticeable)
        }.get(self.state.kirin_interest_level, 0.0)
        
        if base_chance == 0.0:
            return
        
        if random.random() > base_chance:
            return
        
        # Select a foreshadowing hint based on interest level
        hints = []
        if self.state.kirin_interest_level >= 1:
            hints.extend([
                "A flash of light catches your eye—something large and graceful moving between the trees, too fast to identify.",
                "You catch a glimpse of antlers through the canopy, but when you look again, there's nothing there.",
                "The forest light shifts subtly, as if something is watching from the shadows.",
            ])
        if self.state.kirin_interest_level >= 2:
            hints.extend([
                "Hoofprints appear in the soft earth ahead—larger than any deer, with an unusual pattern.",
                "A soft, musical sound drifts through the trees, like wind chimes made of crystal.",
                "You sense a presence nearby, ancient and curious, but when you turn, only dappled sunlight greets you.",
            ])
        if self.state.kirin_interest_level >= 3:
            hints.extend([
                "The air shimmers briefly, and you catch the scent of something otherworldly—sweet and wild.",
                "For a moment, the forest seems to hold its breath, waiting. Then the moment passes.",
                "Something watches you from the depths—you can feel it. But there's no malice, only curiosity.",
            ])
        
        if hints:
            self.ui.echo(f"\n{random.choice(hints)}\n")
    
    def _handle_kirin_travel(self, *, zone_id: str) -> None:
        """
        Handle Kirin travel command.
        
        Args:
            zone_id: Current zone ID
        """
        if not can_use_kirin_travel(self.state):
            if not self.state.kirin_travel_unlocked:
                self.ui.echo("You haven't met the Kirin yet, or travel hasn't been unlocked.\n")
            else:
                self.ui.echo("You've already used Kirin travel today. The Kirin needs rest between journeys.\n")
            return
        
        # Get valid destinations
        current_location = self.state.current_landmark or "glade"
        valid_destinations = get_valid_kirin_destinations(
            self.state, self.landmarks, current_location=current_location
        )
        
        if not valid_destinations:
            self.ui.echo(
                "The Kirin can only take you to places you've made familiar through repeated visits. "
                "You need landmarks with well-worn paths (stability >= 2).\n"
            )
            return
        
        # Show destination menu
        options = [f"Travel to {display_name}" for _lm, display_name in valid_destinations]
        options.append("Cancel")
        
        choice = self.ui.menu("Where would you like to travel?", options)
        
        if "cancel" in choice.lower():
            return
        
        # Find selected destination
        selected_destination = None
        selected_display_name = None
        for lm, display_name in valid_destinations:
            if f"Travel to {display_name}" == choice:
                selected_destination = lm
                selected_display_name = display_name
                break
        
        if selected_destination is None and selected_display_name is None:
            return
        
        # Determine travel mode
        travel_mode = None
        if self.state.kirin_travel_mode_unlocked:
            if len(self.state.kirin_travel_mode_unlocked) > 1:
                # Multiple modes available - let player choose
                mode_options = []
                if "portal" in self.state.kirin_travel_mode_unlocked:
                    mode_options.append("Portal (horn-opened archway)")
                if "vore" in self.state.kirin_travel_mode_unlocked and self.state.vore_enabled:
                    mode_options.append("Internal (belly/trust-based)")
                mode_options.append("Cancel")
                
                if len(mode_options) > 2:  # More than just Cancel
                    mode_choice = self.ui.menu("How would you like to travel?", mode_options)
                    if "cancel" in mode_choice.lower():
                        return
                    if "portal" in mode_choice.lower():
                        travel_mode = "portal"
                    elif "internal" in mode_choice.lower() or "belly" in mode_choice.lower():
                        travel_mode = "vore"
                else:
                    travel_mode = self.state.kirin_travel_mode_unlocked[0]
            else:
                travel_mode = self.state.kirin_travel_mode_unlocked[0]
        
        # Execute travel
        execute_kirin_travel(
            self.state, selected_destination, selected_display_name, self.ui, travel_mode=travel_mode
        )
        # Advance time (long-distance travel takes time)
        from .time_of_day import advance_time_of_day
        advance_time_of_day(self.state, steps=1)
    
    def _handle_wayfind(self, *, zone_id: str) -> None:
        """
        Handle wayfinding teleport command.
        
        Args:
            zone_id: Current zone ID
        """
        if not can_use_wayfinding(self.state):
            if not self.state.wayfinding_ready:
                self.ui.echo("You haven't drunk the Wayfinding Tea yet, or its effects have expired.\n")
            elif self.state.act1_repaired_runestones < 1:
                self.ui.echo("The Forest's paths are too unstable for wayfinding. Repair at least one runestone first.\n")
            return
        
        # Only allow wayfinding in Forest zone
        if self.state.active_zone != "forest":
            self.ui.echo("Wayfinding only works within the Forest. You must be in the Forest to use this power.\n")
            return
        
        # Get valid destinations
        current_location = self.state.current_landmark
        valid_destinations = get_valid_wayfinding_destinations(
            self.state, self.landmarks, current_location=current_location
        )
        
        if not valid_destinations:
            self.ui.echo(
                "You can only wayfind to landmarks you've visited repeatedly with familiar paths (stability >= 2). "
                "The Forest must remember these places clearly for you to step between them.\n"
            )
            return
        
        # Show destination menu
        options = [f"Wayfind to {display_name}" for _lm, display_name in valid_destinations]
        options.append("Cancel")
        
        choice = self.ui.menu("Where would you like to wayfind?", options)
        
        if "cancel" in choice.lower():
            return
        
        # Find selected destination
        selected_destination = None
        selected_display_name = None
        for lm, display_name in valid_destinations:
            if f"Wayfind to {display_name}" == choice:
                selected_destination = lm
                selected_display_name = display_name
                break
        
        if selected_destination is None and selected_display_name is None:
            return
        
        # Execute wayfinding teleport
        execute_wayfinding_teleport(
            self.state, self.landmarks, selected_destination, selected_display_name, self.ui
        )
        # Advance time (wayfinding takes time)
        from .time_of_day import advance_time_of_day
        advance_time_of_day(self.state, steps=1)
    
    def _handle_cook(self, at_camp: bool = False) -> None:
        """
        Handle cooking menu at camp.
        
        Args:
            at_camp: Whether the player is at camp
        """
        if not at_camp:
            self.ui.echo("You need to be at camp to cook meals.\n")
            return
        
        available = self.cooking.get_available_recipes(self.state, at_camp=True)
        if not available:
            self.ui.echo("You don't have the ingredients to cook any meals.\n")
            return
        
        while True:
            available = self.cooking.get_available_recipes(self.state, at_camp=True)
            if not available:
                self.ui.echo("No more ingredients remain to cook with.\n")
                break
            
            sorted_recipes = sorted(
                available.items(),
                key=lambda item: item[1].name,
            )
            options = [
                f"Cook {recipe.name}"
                for _recipe_id, recipe in sorted_recipes
            ]
            options.append("Stop cooking")
            
            choice = self.ui.menu("Cook a meal?", options)
            if choice.lower().startswith("stop"):
                break
            
            selected_recipe = None
            for recipe_id, recipe in sorted_recipes:
                expected = f"Cook {recipe.name}"
                if choice == expected:
                    selected_recipe = recipe
                    break
            
            if selected_recipe is None:
                break
            
            success, message = self.cooking.cook_recipe(self.state, selected_recipe)
            self.ui.echo(message)
