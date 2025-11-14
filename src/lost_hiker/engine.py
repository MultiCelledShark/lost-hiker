"""Core game loop (Wake → Explore → Camp → Return) for Lost Hiker."""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol

from .character import TimedModifier
from .events import EventPool
from .state import GameState, GameStateRepository
from .scenes import SceneCatalog
from .commands import Command, CommandParser


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
    _day_start_inventory: list[str] = field(default_factory=list, init=False)
    _day_start_rapport: dict[str, int] = field(default_factory=dict, init=False)
    _transient_extras: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    _transient_examinables: dict[str, dict[str, str]] = field(default_factory=dict, init=False)
    _command_parser: CommandParser = field(init=False)

    def __post_init__(self) -> None:
        self._command_parser = CommandParser()

    def run(self) -> None:
        """Run until the player chooses to exit."""
        while self.state.stage == "intro":
            self._intro_sequence()
        keep_playing = True
        while keep_playing:
            self._run_day()
            self.repo.save(self.state)
            choice = self.ui.menu("Continue into the next day?", ["yes", "save & quit"])
            if choice == "yes":
                self.state.new_day()
            else:
                keep_playing = False
                self.ui.echo("Game saved. See you soon.\n")

    def _run_day(self) -> None:
        self.state.prune_expired_effects()
        self._day_start_inventory = list(self.state.inventory)
        self._day_start_rapport = dict(self.state.rapport)
        self._wake_phase()
        active_zone = self.state.active_zone or "glade"
        if active_zone == "glade":
            self._glade_phase()
        else:
            self.explore_zone(active_zone)

    def _wake_phase(self) -> None:
        self.state.stage = "wake"
        self.ui.heading(
            f"Day {self.state.day} — Season: {self.state.current_season().title()}"
        )
        wake_gain = self.state.character.get_stat(
            "stamina_wake_restore",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
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

    def _glade_phase(self) -> None:
        self.state.stage = "glade"
        self.state.active_zone = "glade"
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        self._set_scene_highlights(zone_id="glade", depth=0, extras=())
        self.ui.echo(
            "The Glade is calm. Paths stretch outward. Commands: move, look, ping, brew, camp, status, bag, help.\n"
        )
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
            # outcome == "stay": loop continues

    def _intro_sequence(self) -> None:
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
        if verb in {"bag", "status", "help"}:
            if verb == "bag":
                self._show_field_bag()
            elif verb == "status":
                self._show_notebook(zone_id=zone_id, stamina_max=self.state.character.get_stat(
                    "stamina_max",
                    timed_modifiers=self.state.timed_modifiers,
                    current_day=self.state.day,
                ))
            else:
                lines = [
                    "look — survey the hollow",
                    "look at <thing> — inspect portal scars or your gear",
                    "leave — step into the Glade",
                    "status — review notebook",
                    "bag — check supplies",
                ]
                self.ui.echo("Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n")
            return "stay"
        if verb == "ping":
            self.ui.echo("Your radio hisses weakly—Echo is outside, beyond the charred walls.\n")
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

    def _dispatch_glade_command(
        self, *, command: Command, stamina_max: float
    ) -> str:
        verb = command.verb
        args = command.args
        if verb == "move":
            direction = args[0] if args else ""
            if direction in {"to", "into", "toward"} and len(args) >= 2:
                direction = args[1]
            if not direction or direction in {"forest", "south", "forward", "deeper"}:
                self.ui.echo("You shoulder your pack and head toward the forest trail.\n")
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
        if verb == "camp":
            self._camp_phase(zone_id="glade", stamina_max=stamina_max)
            return "leave"
        if verb == "return":
            self.ui.echo("The Glade is already home—for now.\n")
            return "stay"
        if verb == "wait":
            self.ui.echo("You take a quiet moment as wind combs the grasses.\n")
            return "stay"
        if verb == "help":
            self._print_help("glade")
            return "stay"
        self._report_invalid_command("glade")
        return "stay"

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
        if verb == "ping":
            self.ui.echo("Static sputters—Echo can't quite catch your signal this deep in the forest.\n")
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
        if verb == "help":
            self._print_help("forest")
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
            self.ui.echo(
                "Sunlight spills across soft moss and the lone portal tree.\n"
            )
            return
        if zone_id == "forest":
            fallback = {
                "edge": "Trail markers glow faintly with fresh cuts.",
                "mid": "Understory thickets knot around you. Runes flicker on ancient trunks.",
                "deep": "The forest hushes to a heartbeat. Massive roots and unseen wings stir just beyond sight.",
            }
            self.ui.echo(f"{fallback.get(band, 'The forest watches from every side.')}\n")
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
        filler = {"at", "the", "a", "an", "into", "toward", "to", "on", "around", "about", "in"}
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

    def _print_help(self, zone_id: str) -> None:
        if zone_id == "glade":
            lines = [
                "move south|forest — enter the forest trail",
                "look — survey the Glade",
                "ping — call Echo over the HT radio",
                "brew — steep gathered herbs into teas",
                "status — review notebook",
                "bag — check supplies",
                "camp — rest the day away",
                "help — list commands",
            ]
        else:
            lines = [
                "move / continue — push deeper into the forest",
                "move back / return — walk back to the Glade",
                "look — take in your surroundings",
                "brew — prepare teas from gathered herbs",
                "status — open the notebook",
                "bag — check supplies",
                "camp — make camp on the spot",
                "help — list commands",
            ]
        self.ui.echo("Commands:\n" + "\n".join(f"  {line}" for line in lines) + "\n")

    def _resolve_encounter(self, event: "Event") -> str:
        effects = event.effects or {}
        creature_id = effects.get("creature_id")
        creature_data = self.creatures.get(creature_id, {}) if creature_id else {}
        creature_name = creature_data.get("name", creature_id.replace("_", " ")) if creature_id else effects.get("creature", event.event_id.replace("_", " "))
        base_text = effects.get("encounter_text")
        base_text = base_text.strip() if base_text else f"{creature_name} studies you for a long heartbeat."

        allows_vore = bool(creature_data.get("allows_vore", False))
        allows_combat = bool(
            creature_data.get("allows_combat", False)
            or "hostile" in creature_data.get("tags", [])
        )

        if self.state.vore_enabled and allows_vore:
            outcome = self.handle_vore_stub(creature_id, creature_name, creature_data, base_text)
        elif allows_combat:
            outcome = self.handle_combat_stub(creature_id, creature_name, creature_data, base_text)
        else:
            outcome = self.handle_normal_encounter(creature_id, creature_name, creature_data, base_text)

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
        extra = (
            f"{creature_name} tests your footing with a feint. You retreat, breathing hard."
        )
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
            extra = (
                f"You share a knowing smile with {creature_name}; hunts can wait until trust is deeper."
            )
            rapport_delta = {creature_id: 1} if creature_id else {}
        else:
            extra = (
                f"{creature_name} rumbles a promise of gentler lessons once you're ready to submit."
            )
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
                "and nudging it toward you. \"Signal should reach clearer now,\" the static seems to say."
            )
        self.ui.echo(text + "\n")
        self.state.pending_radio_upgrade = False
        self.state.pending_radio_return_day = None
        self.state.radio_version = 2
        self.state.rapport["Echo"] = self.state.rapport.get("Echo", 0) + 1

    def _apply_pending_brews(self) -> None:
        if not self.state.pending_brews:
            return
        messages: list[str] = []
        for tea_id in list(self.state.pending_brews):
            tea = self.teas.get(tea_id)
            if not tea:
                continue
            duration = int(tea.get("duration_days", 1))
            modifiers = tea.get("modifiers", [])
            if modifiers:
                self.state.timed_modifiers.append(
                    TimedModifier(
                        source=f"brew:{tea_id}:{self.state.day}",
                        modifiers=modifiers,
                        expires_on_day=self.state.day + duration,
                    )
                )
            name = tea.get("name", tea_id.replace("_", " ").title())
            messages.append(
                f"{name} will linger for {duration} day{'s' if duration != 1 else ''}."
            )
        self.state.pending_brews.clear()
        if messages:
            self.ui.echo(
                "Brewed effects settle into your veins:\n"
                + "\n".join(f"  {line}" for line in messages)
                + "\n"
            )

    def _handle_radio_ping(self) -> None:
        if self.state.pending_radio_upgrade:
            self.ui.echo("Only static answers—Echo is still tuning the radio.\n")
            return
        if self.state.radio_version <= 1:
            impressions = [
                "Orange static blooms across the speaker—Echo sends warm gratitude and a rush of forest scents.",
                "A pulse of blue static thrums like a heartbeat, Echo's emotions washing over you without words.",
                "The radio crackles with sun-hot warmth and the distant echo of hissing laughter."
            ]
            self.ui.echo(random.choice(impressions) + "\n")
            rapport = self.state.rapport.get("Echo", 0)
            if not self.state.pending_radio_upgrade and rapport > 5:
                if self.state.vore_enabled:
                    upgrade = (
                        "Echo slides close, unhinging their jaw in a gentle swallow that spirits the HT radio into their coils."
                    )
                else:
                    upgrade = (
                        "Echo loops the HT radio into their throat pouch, promising with a soft hiss to refine its range overnight."
                    )
                self.ui.echo(upgrade + "\n")
                self.state.pending_radio_upgrade = True
                self.state.pending_radio_return_day = self.state.day + 1
                self.state.rapport["Echo"] = self.state.rapport.get("Echo", 0) + 1
            elif rapport <= 5:
                self.ui.echo(
                    "Static pulses with expectant warmth—Echo seems to wait until your bond deepens a little more.\n"
                )
            return
        clear_messages = [
            "\"Signal steady. Forest edge is quiet,\" Echo whispers through the static.",
            "\"You breathing alright? Take water before you range,\" Echo crackles, concern threading the words.",
            "\"Trail spirits are calm. Call if shadows crowd you,\" Echo's voice hums, almost musical."
        ]
        self.ui.echo(random.choice(clear_messages) + "\n")
        self.state.rapport["Echo"] = self.state.rapport.get("Echo", 0) + 1

    def _available_teas(self) -> dict[str, dict[str, object]]:
        inventory_counts = Counter(self.state.inventory)
        available: dict[str, dict[str, object]] = {}
        for tea_id, data in self.teas.items():
            requires = Counter(data.get("requires", []))
            if all(inventory_counts.get(item, 0) >= qty for item, qty in requires.items()):
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
        self.state.pending_brews.append(tea_id)
        name = data.get("name", tea_id.replace("_", " ").title())
        description = data.get("description")
        if description:
            self.ui.echo(f"You brew {name}. {description}\n")
        else:
            self.ui.echo(f"You brew {name}.\n")

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

    def explore_zone(self, zone_id: str) -> None:
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
        self._set_scene_highlights(
            zone_id=zone_id,
            depth=self.state.zone_depths.get(zone_id, 0),
            extras=(),
        )
        if zone_id == "forest":
            self.ui.echo(
                "The forest calls. Commands: move, look, camp, return, status, bag, help.\n"
            )
        else:
            self.ui.echo(
                f"The {zone_label} awaits. Commands: look, move, camp, return, status, bag, help.\n"
            )
        while True:
            depth = self.state.zone_depths.get(zone_id, 0)
            self._set_scene_highlights(zone_id=zone_id, depth=depth, extras=None)
            if self.state.stamina <= 0:
                self._collapse_from_exhaustion(zone_id=zone_id, stamina_max=stamina_max)
                return
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

    def _camp_phase(self, *, zone_id: str, stamina_max: float) -> None:
        self.state.stage = "camp"
        self.state.active_zone = zone_id
        meal_cost = int(
            self.state.character.get_stat(
                "camp_meal_cost",
                timed_modifiers=self.state.timed_modifiers,
                current_day=self.state.day,
            )
        )
        partial_rest = max(0.0, math.floor(stamina_max * 0.75))
        self.state.pending_stamina_floor = max(
            self.state.pending_stamina_floor, min(stamina_max, partial_rest)
        )
        if self.state.meals > 0:
            self.state.meals = max(0, self.state.meals - meal_cost)
            self.ui.echo(
                f"You rest and share a meal. Meals remaining: {self.state.meals}.\n"
            )
        else:
            self.ui.echo("No meals left; the rest is fitful.\n")
        self.ui.echo("Camp actions: brew, bag, status, help.\n")
        self._brew_menu(context="camp")
        self._summarize_day("Camp Summary", stamina_max, zone_id=zone_id)

    def _perform_explore_action(self, *, zone_id: str) -> None:
        depth = self.state.zone_depths.get(zone_id, 0) + 1
        self.state.zone_depths[zone_id] = depth
        event = self.events.draw(self.state, depth=depth)
        extras: list[str] = []
        if event:
            creature_id = event.effects.get("creature_id")
            if creature_id:
                creature_data = self.creatures.get(creature_id, {})
                extras.append(
                    creature_data.get("name", creature_id.replace("_", " "))
                )
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
            if not summary.endswith("\n"):
                summary = summary + "\n"
            self.ui.echo(summary)
        self.state.stamina = max(0.0, self.state.stamina - 1.0)

    def _return_to_glade(self, *, zone_id: str, stamina_max: float) -> None:
        self.state.stage = "return"
        self.state.active_zone = "glade"
        self.state.zone_steps.pop(zone_id, None)
        self.ui.echo(
            "You wind back along familiar glade paths and set your gear down.\n"
        )
        self.state.stamina = stamina_max
        self._summarize_day("Glade Summary", stamina_max, zone_id=zone_id)
        self.state.zone_depths.pop(zone_id, None)

    def _collapse_from_exhaustion(self, *, zone_id: str, stamina_max: float) -> None:
        self.state.stage = "collapse"
        self.state.active_zone = zone_id
        stamina_restored = max(0.0, math.floor(stamina_max * 0.5))
        self.state.stamina = stamina_restored
        zone_steps_snapshot = dict(self.state.zone_steps)
        zone_depths_snapshot = dict(self.state.zone_depths)
        roll = random.random()
        summary_zone = zone_id
        depth_here = zone_depths_snapshot.get(
            zone_id, self.state.zone_depths.get(zone_id, 0)
        )
        zone_label = zone_id.replace("_", " ").title()
        if depth_here > 0:
            depth_text = f"You are {depth_here} steps deep in the {zone_label.lower()}.\n"
            depth_clause = f" from {depth_here} steps deep in the {zone_label.lower()}"
        else:
            depth_text = ""
            depth_clause = ""
        dream_roll = random.random()
        dream_text = ""
        if dream_roll < 0.2:
            dream_text = "A strange dream of winding roots and distant hissing clings to your thoughts.\n"
        if roll < 0.25:
            zone_steps_snapshot, zone_depths_snapshot = self._handle_glade_rescue(
                depth_clause=depth_clause,
                dream_text=dream_text,
            )
            summary_zone = "glade"
        elif roll < 0.35:
            self.ui.echo(
                "Echo's silent shape loops around you, warding off the dark while you recover where you fell.\n"
                + depth_text
                + dream_text
            )
            self.state.active_zone = zone_id
        elif roll < 0.75:
            self.ui.echo(
                "The forest stays hushed; nothing stirs while you catch your breath.\n"
                + depth_text
                + dream_text
            )
            self.state.active_zone = zone_id
        else:
            self._echo_protective_watch(depth_text, dream_text, zone_id)
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
        snapshot = [
            f"Meals remaining: {self.state.meals}",
            f"Active zone: {zone_label}",
            f"Trail depth reached: {depth}",
            f"Trail markers logged: {persistent_steps}",
        ]
        self.ui.echo("Status notebook:\n" + "\n".join(f"  {line}" for line in snapshot) + "\n")

    def _show_notebook(self, *, zone_id: str, stamina_max: float) -> None:
        zone_label = zone_id.replace("_", " ").title()
        depth = self.state.zone_depths.get(zone_id, 0)
        persistent_steps = self.state.zone_steps.get(zone_id, 0)
        self.ui.heading("Notebook — Field Status")
        character = self.state.character
        name = character.name or "Wanderer"
        race = character.race_id.replace("_", " ").title()
        lines = [
            f"Name: {name}",
            f"Race: {race}",
            f"Day {self.state.day} — {self.state.current_season().title()}",
            f"Location: {zone_label}",
            f"Stamina: {self.state.stamina:.0f}/{stamina_max:.0f}",
            f"Meals: {self.state.meals}",
        ]
        if zone_id == "forest":
            lines.append(f"Depth: {depth} ({self._depth_band(depth)})")
        else:
            lines.append(f"Depth: {depth}")
        if persistent_steps:
            lines.append(f"Trail markers: {persistent_steps}")
        if self.state.rapport:
            lines.append("Rapport:")
            for creature, score in sorted(self.state.rapport.items()):
                lines.append(f"  {creature}: {score}")
        else:
            lines.append("Rapport: none")
        self.ui.echo("\n".join(lines) + "\n")

    def _show_field_bag(self) -> None:
        self.ui.heading("Field Bag")
        if not self.state.inventory:
            self.ui.echo("Your bag is empty.\n")
            return
        counts = Counter(self.state.inventory)
        lines = [f"  {item}: {count}" for item, count in sorted(counts.items())]
        self.ui.echo("Supplies gathered:\n" + "\n".join(lines) + "\n")
