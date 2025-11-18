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
from .seasons import load_season_config
from .landmarks import load_landmark_catalog
from .cooking import load_cooking_catalog, load_food_items


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
    """Curses-driven interface with rolling log and persistent prompts."""

    def __init__(self) -> None:
        import curses

        self._curses = curses
        self._screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self._screen.keypad(True)
        self._screen.scrollok(False)
        self._screen.idlok(False)
        self._highlight_terms: tuple[str, ...] = ()
        self._highlight_regex: Optional[Pattern[str]] = None
        self._highlight_attr: Optional[int] = curses.A_BOLD
        # Message log: all game output lines (capped)
        self._message_log: List[str] = []
        self._max_log_lines = 300  # Cap message log at 300 lines
        # Current prompt state (for re-rendering)
        self._current_prompt: Optional[str] = None
        self._current_options: Optional[List[str]] = None
        self._invalid_message: Optional[str] = None
        self._menu_selected: int = 0  # Currently selected menu option
        # Reserved rows at bottom for status/input (2-3 lines)
        self._reserved_bottom_rows = 3
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
        self._add_to_log(f"\n{text}\n{'-' * len(text)}\n")
        self._render()

    def echo(self, text: str) -> None:
        self._add_to_log(text if text.endswith("\n") else text + "\n")
        self._render()

    def menu(self, prompt: str, options: List[str]) -> str:
        """Display a menu with persistent prompt and options."""
        curses = self._curses
        self._current_prompt = prompt
        self._current_options = options
        self._invalid_message = None
        self._menu_selected = 0
        self._render()
        
        while True:
            key = self._screen.getch()
            
            if key in (curses.KEY_ENTER, 10, 13):
                break
            if key in (curses.KEY_UP, ord("k")):
                self._menu_selected = (self._menu_selected - 1) % len(options)
                self._render()
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                self._menu_selected = (self._menu_selected + 1) % len(options)
                self._render()
                continue
            if ord("1") <= key <= ord(str(min(len(options), 9))):
                numeric_choice = key - ord("1")
                if 0 <= numeric_choice < len(options):
                    self._menu_selected = numeric_choice
                    break
            
            # Invalid key - show message and re-render
            self._invalid_message = "Invalid choice. Use arrow keys or number keys."
            self._render()
            continue
        
        chosen = options[self._menu_selected]
        self._add_to_log(f"{prompt}\n")
        for idx, option in enumerate(options, start=1):
            self._add_to_log(f"  {idx}. {option}\n")
        self._add_to_log(f"> {chosen}\n")
        self._current_prompt = None
        self._current_options = None
        self._invalid_message = None
        self._menu_selected = 0
        self._render()
        return chosen

    def prompt(self, prompt: str) -> str:
        """Display a text input prompt persistently."""
        curses = self._curses
        self._current_prompt = prompt
        self._current_options = None
        self._invalid_message = None
        self._render()
        
        max_y, max_x = self._screen.getmaxyx()
        input_y = max_y - self._reserved_bottom_rows
        
        # Position cursor and show prompt
        try:
            # Render prompt on one line, then "> " on next line for input
            self._screen.move(input_y, 0)
            self._screen.clrtoeol()
            self._screen.addstr(prompt[:max_x-1])
            # Move to next line for input
            input_line_y = input_y + 1
            if input_line_y >= max_y:
                input_line_y = max_y - 1
            self._screen.move(input_line_y, 0)
            self._screen.clrtoeol()
            self._screen.addstr("> ")
            # Position cursor after "> "
            cursor_x = 2
            self._screen.move(input_line_y, cursor_x)
            curses.curs_set(1)  # Show cursor for input
            self._screen.refresh()
        except curses.error:
            pass
        
        curses.echo()
        try:
            # Get input at current cursor position
            raw = self._screen.getstr()
        finally:
            curses.noecho()
            curses.curs_set(0)  # Hide cursor again
        
        value = raw.decode("utf-8", errors="ignore").strip()
        self._add_to_log(f"{prompt}\n> {value}\n")
        self._current_prompt = None
        self._render()
        return value

    def _add_to_log(self, text: str) -> None:
        """Add text to the message log with word wrapping."""
        import textwrap
        
        max_y, max_x = self._screen.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            wrap_width = 80  # Default width if screen not initialized
        else:
            wrap_width = max(1, max_x - 1)
        
        # Split text into segments and wrap each
        segments = text.split("\n")
        for segment in segments:
            if not segment:
                self._message_log.append("")
            else:
                wrapped = textwrap.wrap(
                    segment, 
                    width=wrap_width, 
                    break_long_words=True, 
                    break_on_hyphens=False
                )
                if not wrapped:
                    # Very long word - truncate
                    self._message_log.append(segment[:wrap_width])
                else:
                    self._message_log.extend(wrapped)
        
        # Cap message log size
        if len(self._message_log) > self._max_log_lines:
            self._message_log = self._message_log[-self._max_log_lines:]
    
    def _render(self) -> None:
        """Render the screen: message log + current prompt/options."""
        curses = self._curses
        max_y, max_x = self._screen.getmaxyx()
        
        if max_x <= 0 or max_y <= 0:
            return
        
        # Calculate visible area
        # Reserve bottom rows for prompt/options/input
        reserved_rows = self._reserved_bottom_rows
        if self._current_options:
            # Reserve more space if menu is showing
            reserved_rows = max(reserved_rows, len(self._current_options) + 2)
        if self._current_prompt and not self._current_options:
            # Reserve space for text prompt
            reserved_rows = max(reserved_rows, 2)
        
        visible_log_rows = max(1, max_y - reserved_rows)
        
        # Determine which log lines to show (last N lines)
        if len(self._message_log) <= visible_log_rows:
            log_lines_to_show = self._message_log
            start_log_idx = 0
        else:
            start_log_idx = len(self._message_log) - visible_log_rows
            log_lines_to_show = self._message_log[start_log_idx:]
        
        # Clear screen
        self._screen.erase()
        
        # Render message log
        for i, line in enumerate(log_lines_to_show):
            if i >= visible_log_rows:
                break
            try:
                self._screen.move(i, 0)
                self._screen.clrtoeol()
                self._render_highlighted_line(line)
            except curses.error:
                pass
        
        # Render current prompt and options (if any)
        render_y = visible_log_rows
        if render_y >= max_y:
            render_y = max_y - 1
        
        if self._current_prompt:
            try:
                self._screen.move(render_y, 0)
                self._screen.clrtoeol()
                self._screen.addstr(self._current_prompt[:max_x-1])
                render_y += 1
            except curses.error:
                pass
        
        if self._current_options:
            for idx, option in enumerate(self._current_options):
                if render_y >= max_y - 1:
                    break
                try:
                    self._screen.move(render_y, 0)
                    self._screen.clrtoeol()
                    label = f"  {idx + 1}. {option}"
                    # Highlight selected option
                    attr = curses.A_REVERSE if idx == self._menu_selected else curses.A_NORMAL
                    self._screen.addstr(label[:max_x-1], attr)
                    render_y += 1
                except curses.error:
                    pass
        
        if self._invalid_message:
            if render_y < max_y - 1:
                try:
                    self._screen.move(render_y, 0)
                    self._screen.clrtoeol()
                    self._screen.addstr(
                        self._invalid_message[:max_x-1],
                        curses.A_BOLD
                    )
                except curses.error:
                    pass
        
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
    """Apply settings to state. Note: vore settings should come from character creation."""
    state.vore_enabled = bool(settings.get("vore_enabled", False))
    state.player_as_pred_enabled = bool(settings.get("player_as_pred_enabled", False))


def settings_menu(ui: UI, state: GameState) -> None:
    """
    Show read-only settings view for vore preferences.
    
    Note: Vore settings are set during character creation and cannot be changed mid-run.
    """
    vore_status = "Enabled" if state.vore_enabled else "Disabled"
    pred_status = "Enabled" if state.player_as_pred_enabled else "Disabled"
    
    ui.heading("Run Settings (Read-Only)")
    ui.echo(f"Vore scenes: {vore_status}\n")
    ui.echo(f"Player as predator: {pred_status}\n")
    ui.echo(
        "\nNote: These settings are set during character creation and cannot be changed mid-run.\n"
    )
    ui.prompt("Press Enter to return to main menu")


def choose_race(ui: UI, races: Dict[str, Dict[str, object]]) -> str:
    ordered = sorted(races.items())
    display = [
        f"{race_id} - {data.get('name', race_id).title()}" for race_id, data in ordered
    ]
    selection = ui.menu("Choose a race:", display)
    index = display.index(selection)
    return ordered[index][0]


def ask_vore_preferences(ui: UI) -> tuple[bool, bool]:
    """
    Ask the player about vore preferences during character creation.
    
    Args:
        ui: UI interface
        
    Returns:
        Tuple of (vore_enabled, player_as_pred_enabled)
    """
    # First question: Enable vore?
    vore_enabled = False
    while True:
        response = ui.prompt(
            "Do you want to enable swallowing-based shelter and travel scenes in this playthrough? (y/n)"
        ).strip().lower()
        if response in ("y", "yes"):
            vore_enabled = True
            break
        elif response in ("n", "no"):
            vore_enabled = False
            break
        else:
            ui.echo("Please answer 'y' or 'n'.\n")
    
    # Second question: Player as predator? (only if vore is enabled)
    player_as_pred_enabled = False
    if vore_enabled:
        ui.echo("\n")
        while True:
            response = ui.prompt(
                "Do you want your character to be able to act as a predator in these scenes? (y/n)"
            ).strip().lower()
            if response in ("y", "yes"):
                player_as_pred_enabled = True
                break
            elif response in ("n", "no"):
                player_as_pred_enabled = False
                break
            else:
                ui.echo("Please answer 'y' or 'n'.\n")
    
    return vore_enabled, player_as_pred_enabled


def create_character(ui: UI, races: Dict[str, Dict[str, object]]) -> tuple[Character, bool, bool]:
    """
    Create a new character and ask for vore preferences.
    
    Args:
        ui: UI interface
        races: Dictionary of race definitions
        
    Returns:
        Tuple of (character, vore_enabled, player_as_pred_enabled)
    """
    race_id = choose_race(ui, races)
    name = ui.prompt("Enter your name")
    character = build_character_from_race(race_id, races[race_id], name or "Wanderer")
    
    # Ask vore preferences after name entry
    ui.echo("\n")
    vore_enabled, player_as_pred_enabled = ask_vore_preferences(ui)
    
    return character, vore_enabled, player_as_pred_enabled


def show_character_summary(
    ui: UI, character: Character, race_data: Dict[str, object]
) -> None:
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
        season_config = load_season_config(data_dir)
        landmarks = load_landmark_catalog(data_dir, "landmarks_forest.json")
        cooking = load_cooking_catalog(data_dir)
        food_items = load_food_items(data_dir)
        from .runestones import load_runestone_definitions
        from .encounters import load_encounter_definitions, EncounterEngine
        from .npcs import load_npc_catalog
        from .dialogue import load_dialogue_catalog
        runestone_defs = load_runestone_definitions(data_dir, "runestones_forest.json")
        encounter_defs = load_encounter_definitions(data_dir, "encounters_forest.json")
        encounter_engine = EncounterEngine(encounter_defs) if encounter_defs else None
        npc_catalog = load_npc_catalog(data_dir, "npcs_forest.json")
        # Load dialogue catalogs and merge them
        forest_dialogue = load_dialogue_catalog(data_dir, "dialogue_forest.json")
        echo_dialogue = load_dialogue_catalog(data_dir, "dialogue_echo.json")
        # Merge dialogue nodes from both catalogs
        from .dialogue import DialogueCatalog
        all_nodes = list(forest_dialogue.nodes) + list(echo_dialogue.nodes)
        dialogue_catalog = DialogueCatalog(all_nodes)
        menu_options = ["New Game", "Continue", "Settings", "Quit"]
        while True:
            choice = ui.menu("Main Menu", menu_options)
            choice_lower = choice.lower()
            if choice_lower == "quit":
                break
            if choice_lower == "new game":
                character, vore_enabled, player_as_pred_enabled = create_character(ui, races)
                show_character_summary(ui, character, races[character.race_id])
                state = repo.create_new(character)
                # Ensure calendar is properly initialized
                state.recalculate_calendar(season_config)
                # Set vore preferences from character creation
                state.vore_enabled = vore_enabled
                state.player_as_pred_enabled = player_as_pred_enabled
                # Update settings snapshot for consistency
                settings_snapshot["vore_enabled"] = vore_enabled
                settings_snapshot["player_as_pred_enabled"] = player_as_pred_enabled
            else:
                if choice_lower == "settings":
                    # For settings menu, we need a state to show current settings
                    # Load existing save if available, otherwise show defaults
                    temp_state = repo.load()
                    if temp_state is None:
                        # Create a temporary state to show default settings
                        temp_state = GameState()
                    settings_menu(ui, temp_state)
                    continue
                state = repo.load()
                if state is None:
                    ui.echo("No save file found.\n")
                    continue
                # Recalculate calendar to ensure it's correct after migration
                state.recalculate_calendar(season_config)
                race = races.get(state.character.race_id)
                if race:
                    sync_character_with_race(state.character, race)
                # Load vore settings from save (already in state)
                settings_snapshot["vore_enabled"] = state.vore_enabled
                settings_snapshot["player_as_pred_enabled"] = state.player_as_pred_enabled
            engine = Engine(
                state=state,
                ui=ui,
                runestone_defs=runestone_defs,
                repo=repo,
                events=event_pool,
                scenes=scenes,
                creatures=creatures,
                teas=teas,
                season_config=season_config,
                landmarks=landmarks,
                cooking=cooking,
                food_items=food_items,
                encounter_engine=encounter_engine,
                npc_catalog=npc_catalog,
                dialogue_catalog=dialogue_catalog,
            )
            engine.run()
    finally:
        if closer:
            closer()


if __name__ == "__main__":
    main()
