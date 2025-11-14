"""Entry point and UI plumbing for the Lost Hiker prototype."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
import re
from typing import Callable, Dict, Iterable, List, Optional, Pattern

from .character import Character, build_character_from_race, sync_character_with_race
from .engine import Engine, UI
from .events import load_event_pool
from .scenes import load_scene_catalog
from .state import GameState, GameStateRepository


class ConsoleUI(UI):
    """Simple stdin/stdout user interface."""

    def __init__(self) -> None:
        self._highlight_terms: tuple[str, ...] = ()

    def heading(self, text: str) -> None:
        print()
        print(text)
        print("-" * len(text))

    def echo(self, text: str) -> None:
        print(text, end="" if text.endswith("\n") else "\n")

    def menu(self, prompt: str, options: List[str]) -> str:
        print(prompt)
        for idx, option in enumerate(options, start=1):
            print(f"  {idx}. {option}")
        while True:
            choice = input("> ").strip().lower()
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(options):
                    return options[index]
            for option in options:
                if choice == option.lower():
                    return option
            print("Please choose by number or name.")

    def prompt(self, prompt: str) -> str:
        return input(f"{prompt}\n> ").strip()

    def set_highlights(self, terms: Iterable[str]) -> None:
        self._highlight_terms = tuple(terms)


class CursesUI(UI):
    """Minimal curses-driven interface."""

    def __init__(self) -> None:
        import curses

        self._curses = curses
        self._screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self._screen.keypad(True)
        self._screen.scrollok(True)
        self._screen.idlok(True)
        self._highlight_terms: tuple[str, ...] = ()
        self._highlight_regex: Optional[Pattern[str]] = None
        self._highlight_attr: Optional[int] = curses.A_BOLD
        try:
            if curses.has_colors():
                curses.start_color()
                try:
                    curses.use_default_colors()
                except curses.error:
                    pass
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                self._highlight_attr = curses.color_pair(1) | curses.A_BOLD
        except curses.error:
            self._highlight_attr = curses.A_BOLD
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    def close(self) -> None:
        curses = self._curses
        curses.nocbreak()
        self._screen.keypad(False)
        curses.echo()
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        curses.endwin()

    def heading(self, text: str) -> None:
        self._write(f"\n{text}\n{'-' * len(text)}\n")

    def echo(self, text: str) -> None:
        self._write(text if text.endswith("\n") else text + "\n")

    def menu(self, prompt: str, options: List[str]) -> str:
        curses = self._curses
        self._write(f"{prompt}\n")
        max_y, max_x = self._screen.getmaxyx()
        menu_height = len(options)
        # ensure there is space to render the menu
        current_y, _ = self._screen.getyx()
        required_space = current_y + menu_height
        if required_space >= max_y:
            scroll_amount = required_space - max_y + 1
            for _ in range(scroll_amount):
                self._screen.scroll(1)
            current_y = max_y - menu_height - 1
            if current_y < 0:
                current_y = 0
            self._screen.move(current_y, 0)
        menu_win = curses.newwin(menu_height, max_x, current_y, 0)
        menu_win.keypad(True)
        selected = 0
        while True:
            menu_win.erase()
            for idx, option in enumerate(options):
                label = f"  {idx + 1}. {option}"
                attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
                try:
                    menu_win.addnstr(idx, 0, label, max_x - 1, attr)
                except curses.error:
                    continue
            menu_win.refresh()
            key = menu_win.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                break
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(options)
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(options)
                continue
            if ord("1") <= key <= ord(str(min(len(options), 9))):
                numeric_choice = key - ord("1")
                if 0 <= numeric_choice < len(options):
                    selected = numeric_choice
                    break
        chosen = options[selected]
        menu_win.erase()
        menu_win.refresh()
        del menu_win
        self._screen.move(current_y, 0)
        self._write(f"> {chosen}\n")
        return chosen

    def prompt(self, prompt: str) -> str:
        self._write(f"{prompt}\n> ")
        self._screen.refresh()
        curses = self._curses
        curses.echo()
        try:
            raw = self._screen.getstr()
        finally:
            curses.noecho()
        value = raw.decode("utf-8", errors="ignore").strip()
        return value

    def _write(self, text: str) -> None:
        curses = self._curses
        max_y, max_x = self._screen.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        segments = text.split("\n")
        for idx, segment in enumerate(segments):
            truncated = segment[: max_x - 1] if max_x > 1 else segment
            self._render_highlighted_line(truncated)
            if idx < len(segments) - 1:
                y, _ = self._screen.getyx()
                if y >= max_y - 1:
                    self._screen.scroll(1)
                    self._screen.move(max_y - 1, 0)
                else:
                    self._screen.move(y + 1, 0)
            else:
                # ensure we do not leave the cursor beyond screen bounds
                y, _ = self._screen.getyx()
                if y >= max_y:
                    self._screen.move(max_y - 1, 0)
        self._screen.refresh()

    def _render_highlighted_line(self, segment: str) -> None:
        curses = self._curses
        if not segment:
            return
        regex = self._highlight_regex
        highlight_attr = self._highlight_attr
        try:
            if not regex or highlight_attr is None:
                self._screen.addstr(segment)
                return
            last_index = 0
            for match in regex.finditer(segment):
                start, end = match.span()
                if start > last_index:
                    self._screen.addstr(segment[last_index:start])
                self._screen.addstr(segment[start:end], highlight_attr)
                last_index = end
            if last_index < len(segment):
                self._screen.addstr(segment[last_index:])
        except curses.error:
            pass

    def set_highlights(self, terms: Iterable[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for term in terms:
            if not term:
                continue
            trimmed = term.strip()
            if not trimmed:
                continue
            key = trimmed.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(trimmed)
        self._highlight_terms = tuple(normalized)
        if not self._highlight_terms:
            self._highlight_regex = None
            return
        try:
            pattern = "|".join(
                re.escape(term)
                for term in sorted(self._highlight_terms, key=len, reverse=True)
            )
            self._highlight_regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            self._highlight_regex = None


def load_races(data_dir: Path) -> Dict[str, Dict[str, object]]:
    path = data_dir / "races.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_creatures(data_dir: Path) -> Dict[str, Dict[str, object]]:
    path = data_dir / "creatures.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_teas(data_dir: Path) -> Dict[str, Dict[str, object]]:
    path = data_dir / "teas.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def apply_settings_to_state(state: GameState, settings: Dict[str, bool]) -> None:
    state.vore_enabled = bool(settings.get("vore_enabled", False))
    state.player_as_pred_enabled = bool(settings.get("player_as_pred_enabled", False))


def settings_menu(ui: UI, settings: Dict[str, bool]) -> None:
    while True:
        vore_status = "on" if settings.get("vore_enabled") else "off"
        pred_status = "on" if settings.get("player_as_pred_enabled") else "off"
        choice = ui.menu(
            "Settings",
            [
                f"Toggle vore (currently {vore_status})",
                f"Toggle player-as-pred (currently {pred_status})",
                "Back",
            ],
        ).lower()
        if "toggle vore" in choice:
            settings["vore_enabled"] = not settings.get("vore_enabled", False)
            if not settings["vore_enabled"]:
                settings["player_as_pred_enabled"] = False
            ui.echo(f"Vore encounters now {'enabled' if settings['vore_enabled'] else 'disabled'}.\n")
            continue
        if "toggle player-as-pred" in choice:
            if not settings.get("vore_enabled", False):
                ui.echo("Enable vore encounters first to access predator options.\n")
                continue
            settings["player_as_pred_enabled"] = not settings.get("player_as_pred_enabled", False)
            ui.echo(
                "Player-as-pred scenes now "
                f"{'enabled' if settings['player_as_pred_enabled'] else 'disabled'}.\n"
            )
            continue
        if "back" in choice:
            return


def choose_race(ui: UI, races: Dict[str, Dict[str, object]]) -> str:
    ordered = sorted(races.items())
    display = [
        f"{race_id} - {data.get('name', race_id).title()}" for race_id, data in ordered
    ]
    selection = ui.menu("Choose a race:", display)
    index = display.index(selection)
    return ordered[index][0]


def create_character(ui: UI, races: Dict[str, Dict[str, object]]) -> Character:
    race_id = choose_race(ui, races)
    name = ui.prompt("Enter your name")
    character = build_character_from_race(race_id, races[race_id], name or "Wanderer")
    return character


def show_character_summary(ui: UI, character: Character, race_data: Dict[str, object]) -> None:
    stamina = character.get_stat("stamina_max", timed_modifiers=[], current_day=1)
    slots = character.get_stat("inventory_slots", timed_modifiers=[], current_day=1)
    race_name = race_data.get("name", character.race_id).title()
    summary = race_data.get("summary", "")
    ui.heading("Character Summary")
    ui.echo(
        f"Name: {character.name or 'Wanderer'}\n"
        f"Race: {race_name}\n"
        f"Stamina Max: {stamina:.0f}\n"
        f"Inventory Slots: {slots:.0f}\n"
    )
    if summary:
        ui.echo(summary + "\n")


def build_ui() -> tuple[UI, Optional[Callable[[], None]]]:
    if os.environ.get("LOST_HIKER_NO_CURSES", "").lower() == "1":
        return ConsoleUI(), None
    try:
        ui = CursesUI()
        return ui, getattr(ui, "close")
    except Exception:
        print("Curses UI unavailable; falling back to console.")
        return ConsoleUI(), None


def resolve_paths() -> tuple[Path, Path]:
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent.parent
    data_dir = package_dir / "data"
    save_path = project_root / "save" / "save.json"
    return data_dir, save_path


def main() -> None:
    seed = os.environ.get("LOST_HIKER_SEED")
    if seed is not None:
        random.seed(seed)
    data_dir, save_path = resolve_paths()
    repo = GameStateRepository(save_path)
    ui, closer = build_ui()
    settings_snapshot: Dict[str, bool] = {
        "vore_enabled": False,
        "player_as_pred_enabled": False,
    }
    try:
        event_pool = load_event_pool(data_dir, "events_forest.json")
        scenes = load_scene_catalog(data_dir)
        creatures = load_creatures(data_dir)
        teas = load_teas(data_dir)
        races = load_races(data_dir)
        menu_options = ["New Game", "Continue", "Settings", "Quit"]
        while True:
            choice = ui.menu("Main Menu", menu_options)
            choice_lower = choice.lower()
            if choice_lower == "quit":
                break
            if choice_lower == "new game":
                character = create_character(ui, races)
                show_character_summary(ui, character, races[character.race_id])
                state = repo.create_new(character)
                apply_settings_to_state(state, settings_snapshot)
            else:
                if choice_lower == "settings":
                    settings_menu(ui, settings_snapshot)
                    continue
                state = repo.load()
                if state is None:
                    ui.echo("No save file found.\n")
                    continue
                race = races.get(state.character.race_id)
                if race:
                    sync_character_with_race(state.character, race)
                settings_snapshot["vore_enabled"] = state.vore_enabled
                settings_snapshot["player_as_pred_enabled"] = state.player_as_pred_enabled
                adjust = ui.menu(
                    "Loaded save. Adjust settings before resuming?",
                    ["Start", "Settings"],
                ).lower()
                if adjust == "settings":
                    settings_menu(ui, settings_snapshot)
                apply_settings_to_state(state, settings_snapshot)
            engine = Engine(
                state=state,
                ui=ui,
                repo=repo,
                events=event_pool,
                scenes=scenes,
                creatures=creatures,
                teas=teas,
            )
            engine.run()
    finally:
        if closer:
            closer()


if __name__ == "__main__":
    main()
