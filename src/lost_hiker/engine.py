"""Core game loop (Wake → Explore → Camp → Return) for Lost Hiker."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from .events import EventPool
from .state import GameState, GameStateRepository


class UI(Protocol):
    """Interface for user interaction."""

    def heading(self, text: str) -> None: ...

    def echo(self, text: str) -> None: ...

    def menu(self, prompt: str, options: list[str]) -> str: ...

    def prompt(self, prompt: str) -> str: ...


@dataclass
class Engine:
    """Coordinates the daily loop."""

    state: GameState
    ui: UI
    repo: GameStateRepository
    events: EventPool
    _day_start_inventory: list[str] = field(default_factory=list, init=False)
    _day_start_rapport: dict[str, int] = field(default_factory=dict, init=False)

    def run(self) -> None:
        """Run until the player chooses to exit."""
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
        self.explore_zone("forest")

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
        self.state.stamina = min(stamina_max, self.state.stamina + wake_gain)
        self.ui.echo(
            f"You wake in the Glade with {self.state.stamina:.0f}/{stamina_max:.0f} stamina.\n"
        )
        self._echo_current_rapport()
        persistent_steps = self.state.zone_steps.get("forest", 0)
        if persistent_steps > 0:
            self.ui.echo(
                f"You recall the trail markers—{persistent_steps} steps carved into the forest.\n"
            )

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
        if zone_id == "forest":
            self.ui.echo("The forest calls. You can press deeper or fall back.\n")
        else:
            self.ui.echo(f"The {zone_label} awaits.\n")
        while True:
            if self.state.stamina <= 0:
                self._collapse_from_exhaustion()
                return
            can_explore = self.state.stamina > 0
            options: list[str] = []
            option_map: dict[str, str] = {}
            if can_explore:
                explore_label = "Explore deeper" if actions_taken > 0 else "Explore"
                options.append(explore_label)
                option_map[explore_label.lower()] = "explore"
            label_camp = "Make camp"
            options.append(label_camp)
            option_map[label_camp.lower()] = "camp"
            if self.state.stamina >= 2:
                label_return = "Return to the Glade"
                options.append(label_return)
                option_map[label_return.lower()] = "return"
            prompt = (
                f"{zone_label} — Stamina {self.state.stamina:.0f}/{stamina_max:.0f} "
                f"(steps taken {actions_taken})"
            )
            choice = self.ui.menu(prompt, options).lower()
            action = option_map.get(choice, choice)
            if action == "explore":
                self._perform_explore_action(zone_id=zone_id)
                actions_taken += 1
                self.state.zone_steps[zone_id] = actions_taken
                continue
            if action == "camp":
                self._camp_phase(zone_id=zone_id, stamina_max=stamina_max)
                return
            if action == "return":
                self._return_to_glade(zone_id=zone_id, stamina_max=stamina_max)
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
        partial_rest = stamina_max * 0.75
        self.state.stamina = min(stamina_max, max(self.state.stamina, partial_rest))
        if self.state.meals > 0:
            self.state.meals = max(0, self.state.meals - meal_cost)
            self.ui.echo(
                f"You rest and share a meal. Meals remaining: {self.state.meals}.\n"
            )
        else:
            self.ui.echo("No meals left; the rest is fitful.\n")
        self._summarize_day("Camp Summary", stamina_max)

    def _perform_explore_action(self, *, zone_id: str) -> None:
        event = self.events.draw(self.state)
        if not event:
            self.ui.echo("The woods are quiet.\n")
        else:
            summary = self.events.apply(self.state, event)
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
        self._summarize_day("Glade Summary", stamina_max)

    def _collapse_from_exhaustion(self) -> None:
        self.state.stage = "collapse"
        self.state.active_zone = "glade"
        self.state.stamina = 0.0
        self.state.zone_steps.clear()
        self.ui.echo(
            "Exhaustion engulfs you. Allies haul you back to the Glade to recover.\n"
        )
        stamina_max = self.state.character.get_stat(
            "stamina_max",
            timed_modifiers=self.state.timed_modifiers,
            current_day=self.state.day,
        )
        self._summarize_day("Exhaustion Recovery", stamina_max)

    def _summarize_day(self, title: str, stamina_max: float) -> None:
        self.ui.heading(title)
        self.ui.echo(
            f"Day {self.state.day} closes with stamina "
            f"{self.state.stamina:.0f}/{stamina_max:.0f}.\n"
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

    def _echo_current_rapport(self) -> None:
        if not self.state.rapport:
            self.ui.echo("No bonds yet tie you to the forest's denizens.\n")
            return
        lines = [
            f"  {creature}: {score}"
            for creature, score in sorted(self.state.rapport.items())
        ]
        self.ui.echo("Glade rapport:\n" + "\n".join(lines) + "\n")
