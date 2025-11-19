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
from .flavor_tags import (
    get_all_tags,
    get_all_tag_packs,
    get_tag_pack,
)
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
    """Curses-driven interface with separate output and input windows."""

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
        
        # Window setup: separate output and input windows
        self._input_height = 2  # Fixed height for input window (1-2 lines)
        self._output_win: Optional[object] = None
        self._input_win: Optional[object] = None
        self._setup_windows()
        
        # Initial screen refresh to ensure windows are visible
        self._screen.refresh()
        
        # Current scene content (cleared and redrawn for each new scene)
        self._current_scene_lines: List[str] = []
        
        # Menu state
        self._current_prompt: Optional[str] = None
        self._current_options: Optional[List[str]] = None
        self._invalid_message: Optional[str] = None
        self._menu_selected: int = 0
        self._menu_page: int = 0  # Current page for paginated menus
        self._menu_page_size: int = 0  # Number of options visible per page
        
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

    def _setup_windows(self) -> None:
        """Create separate output and input windows."""
        curses = self._curses
        max_y, max_x = self._screen.getmaxyx()
        
        # Input window: fixed at bottom (2 lines)
        input_height = min(self._input_height, max_y - 1)
        if input_height < 1:
            input_height = 1
        
        # Output window: takes up remaining space
        output_height = max(1, max_y - input_height)
        
        try:
            # Create output window (main content area)
            self._output_win = curses.newwin(output_height, max_x, 0, 0)
            self._output_win.scrollok(False)
            self._output_win.idlok(False)
            
            # Create input window (fixed at bottom)
            input_y = max_y - input_height
            self._input_win = curses.newwin(input_height, max_x, input_y, 0)
            self._input_win.scrollok(False)
            self._input_win.idlok(False)
        except curses.error:
            # Fallback: use main screen if window creation fails
            self._output_win = self._screen
            self._input_win = self._screen

    def _refresh_windows(self) -> None:
        """Refresh windows after terminal resize."""
        curses = self._curses
        max_y, max_x = self._screen.getmaxyx()
        
        input_height = min(self._input_height, max_y - 1)
        if input_height < 1:
            input_height = 1
        output_height = max(1, max_y - input_height)
        
        try:
            # Delete old windows if they exist
            if self._output_win and self._output_win != self._screen:
                del self._output_win
            if self._input_win and self._input_win != self._screen:
                del self._input_win
            
            # Create new windows
            self._output_win = curses.newwin(output_height, max_x, 0, 0)
            self._output_win.scrollok(False)
            self._output_win.idlok(False)
            
            input_y = max_y - input_height
            self._input_win = curses.newwin(input_height, max_x, input_y, 0)
            self._input_win.scrollok(False)
            self._input_win.idlok(False)
        except curses.error:
            self._output_win = self._screen
            self._input_win = self._screen

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
        """Display a heading, clearing previous scene content."""
        self._clear_scene()
        self._add_to_scene(f"\n{text}\n{'-' * len(text)}\n")
        self._render_output()

    def echo(self, text: str) -> None:
        """Add text to current scene output."""
        self._add_to_scene(text if text.endswith("\n") else text + "\n")
        self._render_output()

    def menu(self, prompt: str, options: List[str]) -> str:
        """Display a paginated menu with persistent prompt and options."""
        curses = self._curses
        self._current_prompt = prompt
        self._current_options = options
        self._invalid_message = None
        self._menu_selected = 0
        self._menu_page = 0
        
        # Calculate how many options fit per page
        self._calculate_menu_page_size()
        
        # Ensure selected option is on current page
        self._menu_page = self._menu_selected // self._menu_page_size
        
        # Per refactor: clear and redraw for new standalone menu
        # But preserve scene content if it exists (for dialogue - text should stay visible with menu)
        # Only clear if scene is empty (standalone menu like main menu)
        if not self._current_scene_lines:
            self._clear_scene()
        # Clear input window (menus don't use it)
        self._current_prompt = None  # Temporarily clear for input window
        self._render_input()
        self._current_prompt = prompt  # Restore for menu display
        self._render_output()
        # Ensure screen is refreshed so menu is visible immediately
        self._screen.refresh()
        
        while True:
            key = self._screen.getch()
            
            if key in (curses.KEY_ENTER, 10, 13):
                break
            if key in (curses.KEY_UP, ord("k")):
                if self._menu_selected > 0:
                    self._menu_selected -= 1
                    # Move to previous page if needed
                    if self._menu_selected < self._menu_page * self._menu_page_size:
                        self._menu_page = max(0, self._menu_page - 1)
                else:
                    # Wrap to last option
                    self._menu_selected = len(options) - 1
                    self._menu_page = (len(options) - 1) // self._menu_page_size
                self._render_output()
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                if self._menu_selected < len(options) - 1:
                    self._menu_selected += 1
                    # Move to next page if needed
                    if self._menu_selected >= (self._menu_page + 1) * self._menu_page_size:
                        self._menu_page = min(
                            (len(options) - 1) // self._menu_page_size,
                            self._menu_page + 1
                        )
                else:
                    # Wrap to first option
                    self._menu_selected = 0
                    self._menu_page = 0
                self._render_output()
                continue
            if key == curses.KEY_PPAGE:  # Page up
                if self._menu_page > 0:
                    self._menu_page -= 1
                    # Keep selection within page
                    self._menu_selected = min(
                        self._menu_selected,
                        (self._menu_page + 1) * self._menu_page_size - 1
                    )
                self._render_output()
                continue
            if key == curses.KEY_NPAGE:  # Page down
                max_page = (len(options) - 1) // self._menu_page_size
                if self._menu_page < max_page:
                    self._menu_page += 1
                    # Keep selection within page
                    self._menu_selected = max(
                        self._menu_selected,
                        self._menu_page * self._menu_page_size
                    )
                self._render_output()
                continue
            if ord("1") <= key <= ord(str(min(len(options), 9))):
                numeric_choice = key - ord("1")
                if 0 <= numeric_choice < len(options):
                    self._menu_selected = numeric_choice
                    self._menu_page = numeric_choice // self._menu_page_size
                    break
            
            # Invalid key - show message and re-render
            self._invalid_message = "Invalid choice. Use arrow keys, page up/down, or number keys."
            self._render_output()
            continue
        
        chosen = options[self._menu_selected]
        # Add selection to scene log for history
        self._add_to_scene(f"{prompt}\n")
        for idx, option in enumerate(options, start=1):
            self._add_to_scene(f"  {idx}. {option}\n")
        self._add_to_scene(f"> {chosen}\n")
        self._current_prompt = None
        self._current_options = None
        self._invalid_message = None
        self._menu_selected = 0
        self._menu_page = 0
        self._render_output()
        self._render_input()  # Clear input window
        return chosen

    def prompt(self, prompt: str) -> str:
        """Display a text input prompt in the input window."""
        curses = self._curses
        self._current_prompt = prompt
        self._current_options = None
        self._invalid_message = None
        self._render_input()
        
        # Show prompt and get input in input window
        try:
            self._input_win.erase()
            max_y, max_x = self._input_win.getmaxyx()
            
            # Show prompt on first line
            if max_y >= 1:
                self._input_win.move(0, 0)
                self._input_win.clrtoeol()
                self._input_win.addstr(prompt[:max_x-1])
            
            # Show "> " on second line (or first if only one line)
            input_line = 1 if max_y >= 2 else 0
            self._input_win.move(input_line, 0)
            self._input_win.clrtoeol()
            self._input_win.addstr("> ")
            
            # Position cursor after "> "
            cursor_x = 2
            self._input_win.move(input_line, cursor_x)
            curses.curs_set(1)  # Show cursor for input
            self._input_win.refresh()
        except curses.error:
            pass
        
        curses.echo()
        try:
            # Get input in input window
            raw = self._input_win.getstr(input_line, cursor_x)
        finally:
            curses.noecho()
            curses.curs_set(0)  # Hide cursor again
        
        value = raw.decode("utf-8", errors="ignore").strip()
        # Add prompt and response to scene log
        self._add_to_scene(f"{prompt}\n> {value}\n")
        self._current_prompt = None
        self._render_output()
        self._render_input()
        return value

    def _clear_scene(self) -> None:
        """Clear current scene content (called when starting a new scene)."""
        self._current_scene_lines = []

    def _add_to_scene(self, text: str) -> None:
        """Add text to current scene with word wrapping."""
        import textwrap
        
        if not self._output_win:
            return
        
        max_y, max_x = self._output_win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            wrap_width = 80  # Default width if screen not initialized
        else:
            wrap_width = max(1, max_x - 1)
        
        # Split text into segments and wrap each
        segments = text.split("\n")
        for segment in segments:
            if not segment:
                self._current_scene_lines.append("")
            else:
                wrapped = textwrap.wrap(
                    segment, 
                    width=wrap_width, 
                    break_long_words=True, 
                    break_on_hyphens=False
                )
                if not wrapped:
                    # Very long word - truncate
                    self._current_scene_lines.append(segment[:wrap_width])
                else:
                    self._current_scene_lines.extend(wrapped)

    def _calculate_menu_page_size(self) -> None:
        """Calculate how many menu options fit per page."""
        if not self._output_win or not self._current_options:
            self._menu_page_size = 10  # Default
            return
        
        max_y, max_x = self._output_win.getmaxyx()
        if max_y <= 0 or max_x <= 0:
            self._menu_page_size = 10
            return
        
        # Account for scene content that might already be displayed
        scene_lines = len(self._current_scene_lines)
        
        # Reserve space for:
        # - Prompt (1 line)
        # - Page indicator (1 line, if paginated)
        # - Invalid message (1 line, if shown)
        reserved = 3
        
        # Available lines for menu options
        available_lines = max(1, max_y - scene_lines - reserved)
        
        # Each option typically takes 1 line (may wrap, but we handle that)
        self._menu_page_size = max(1, available_lines)

    def _render_output(self) -> None:
        """Render the output window with scene content and menu."""
        curses = self._curses
        if not self._output_win:
            return
        
        max_y, max_x = self._output_win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        
        # Clear output window
        self._output_win.erase()
        
        render_y = 0
        
        # Determine how many lines we can show for scene content
        # Reserve space for menu if active
        max_scene_lines = max_y
        if self._current_options:
            # Reserve space for prompt, menu options, page indicator, and invalid message
            max_scene_lines = max(1, max_y - 5)  # Conservative estimate
        
        # Render scene content (wrapped lines)
        # If there are more lines than fit, show the most recent ones
        if self._current_scene_lines:
            scene_lines_to_show = self._current_scene_lines
            if len(self._current_scene_lines) > max_scene_lines:
                scene_lines_to_show = self._current_scene_lines[-max_scene_lines:]
            
            for line in scene_lines_to_show:
                if render_y >= max_scene_lines:
                    break
                try:
                    self._output_win.move(render_y, 0)
                    self._output_win.clrtoeol()
                    self._render_highlighted_line(line, self._output_win)
                    render_y += 1
                except curses.error:
                    pass
        
        # Render menu if active
        if self._current_options and render_y < max_y:
            # Show prompt if present (menus show prompt in output window)
            if self._current_prompt and render_y < max_y:
                try:
                    self._output_win.move(render_y, 0)
                    self._output_win.clrtoeol()
                    self._output_win.addstr(self._current_prompt[:max_x-1])
                    render_y += 1
                except curses.error:
                    pass
            
            # Calculate pagination
            start_idx = self._menu_page * self._menu_page_size
            end_idx = min(
                start_idx + self._menu_page_size,
                len(self._current_options)
            )
            
            # Render visible options for current page
            import textwrap
            for idx in range(start_idx, end_idx):
                if render_y >= max_y - 1:  # Leave space for page indicator
                    break
                option = self._current_options[idx]
                try:
                    # Wrap long options
                    prefix = f"  {idx + 1}. "
                    wrap_width = max(1, max_x - len(prefix))
                    wrapped_lines = textwrap.wrap(
                        option, 
                        width=wrap_width, 
                        break_long_words=True, 
                        break_on_hyphens=False
                    )
                    if not wrapped_lines:
                        wrapped_lines = [option[:wrap_width]]
                    
                    # Render each wrapped line
                    for line_idx, line in enumerate(wrapped_lines):
                        if render_y >= max_y - 1:
                            break
                        self._output_win.move(render_y, 0)
                        self._output_win.clrtoeol()
                        if line_idx == 0:
                            label = f"{prefix}{line}"
                        else:
                            label = f"      {line}"  # Indent continuation
                        # Highlight selected option
                        attr = curses.A_REVERSE if idx == self._menu_selected else curses.A_NORMAL
                        self._output_win.addstr(label[:max_x-1], attr)
                        render_y += 1
                except curses.error:
                    pass
            
            # Show page indicator if paginated
            if len(self._current_options) > self._menu_page_size and render_y < max_y:
                try:
                    page_info = f"Page {self._menu_page + 1}/{(len(self._current_options) - 1) // self._menu_page_size + 1}"
                    self._output_win.move(render_y, 0)
                    self._output_win.clrtoeol()
                    self._output_win.addstr(page_info[:max_x-1], curses.A_DIM)
                    render_y += 1
                except curses.error:
                    pass
            
            # Show invalid message if present
            if self._invalid_message and render_y < max_y:
                try:
                    self._output_win.move(render_y, 0)
                    self._output_win.clrtoeol()
                    self._output_win.addstr(
                        self._invalid_message[:max_x-1],
                        curses.A_BOLD
                    )
                except curses.error:
                    pass
        
        self._output_win.refresh()

    def _render_input(self) -> None:
        """Render the input window with current prompt."""
        curses = self._curses
        if not self._input_win:
            return
        
        max_y, max_x = self._input_win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        
        self._input_win.erase()
        
        if self._current_prompt:
            try:
                # Show prompt on first line
                if max_y >= 1:
                    self._input_win.move(0, 0)
                    self._input_win.clrtoeol()
                    self._input_win.addstr(self._current_prompt[:max_x-1])
            except curses.error:
                pass
        
        self._input_win.refresh()

    def _render_highlighted_line(self, segment: str, win: Optional[object] = None) -> None:
        """Render a line with syntax highlighting for matched terms."""
        curses = self._curses
        if not segment:
            return
        
        # Use provided window or default to output window
        target_win = win if win is not None else self._output_win
        if not target_win:
            return
        
        regex = self._highlight_regex
        highlight_attr = self._highlight_attr
        try:
            if not regex or highlight_attr is None:
                target_win.addstr(segment)
                return
            last_index = 0
            for match in regex.finditer(segment):
                start, end = match.span()
                if start > last_index:
                    target_win.addstr(segment[last_index:start])
                target_win.addstr(segment[start:end], highlight_attr)
                last_index = end
            if last_index < len(segment):
                target_win.addstr(segment[last_index:])
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
        races = json.load(handle)
    # Backward compatibility: map old "wolfkin" to new "wolf_kin"
    if "wolfkin" in races and "wolf_kin" not in races:
        races["wolf_kin"] = races["wolfkin"]
        del races["wolfkin"]
    return races


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


def choose_race(ui: UI, races: Dict[str, Dict[str, object]]) -> Optional[str]:
    """Choose a race, or return None for custom race."""
    ordered = sorted(races.items())
    display = []
    for race_id, data in ordered:
        name = data.get('name', race_id).title()
        description = data.get('description', data.get('summary', ''))
        if description:
            display.append(f"{name} - {description}")
        else:
            display.append(f"{name}")
    display.append("Custom Race - Create your own race")
    selection = ui.menu("Choose a race:", display)
    index = display.index(selection)
    if index < len(ordered):
        return ordered[index][0]
    return None  # Custom race


def choose_body_type(ui: UI, default: str = "humanoid") -> str:
    """Choose a body type."""
    options = ["humanoid", "taur", "naga", "quadruped"]
    display = [opt.title() for opt in options]
    try:
        default_idx = options.index(default.lower())
        # Highlight default if UI supports it
    except ValueError:
        default_idx = 0
    
    selection = ui.menu(f"Choose body type (default: {default}):", display)
    idx = display.index(selection)
    return options[idx]


def choose_size(ui: UI, default: str = "medium") -> str:
    """Choose a size category."""
    options = ["small", "medium", "large"]
    display = [opt.title() for opt in options]
    
    selection = ui.menu(f"Choose size (default: {default}):", display)
    idx = display.index(selection)
    return options[idx]


def choose_archetype(ui: UI, default: str = "forest_creature") -> str:
    """Choose an ecology archetype."""
    options = [
        "forest_creature",
        "cave_creature",
        "river_creature",
        "spiritborn",
        "leyline_touched",
        "beastfolk",
    ]
    display = [opt.replace("_", " ").title() for opt in options]
    
    selection = ui.menu(f"Choose archetype (default: {default.replace('_', ' ').title()}):", display)
    idx = display.index(selection)
    return options[idx]


def choose_flavor_tags(
    ui: UI, min_tags: int = 2, max_tags: int = 4
) -> List[str]:
    """Choose flavor tags with optional tag pack preselection."""
    available_tags = get_all_tags()
    display = [tag.replace("_", " ").title() for tag in available_tags]
    selected_tags: List[str] = []
    
    # Ask if they want to use a tag pack
    ui.echo(f"\nChoose {min_tags}-{max_tags} flavor tags:\n")
    ui.echo("Would you like to start with a tag pack?\n")
    
    tag_packs = get_all_tag_packs()
    pack_options = []
    pack_ids = []
    for pack_id, pack_data in tag_packs.items():
        pack_options.append(f"{pack_data['name']} - {pack_data['description']}")
        pack_ids.append(pack_id)
    
    pack_selection = ui.menu("Select a tag pack (or None for manual selection):", pack_options)
    pack_idx = pack_options.index(pack_selection)
    selected_pack_id = pack_ids[pack_idx]
    
    # If a pack was selected (not "none"), prefill tags
    if selected_pack_id != "none":
        pack = get_tag_pack(selected_pack_id)
        if pack:
            selected_tags = list(pack["tags"])
            ui.echo(f"\nSelected pack: {pack['name']}\n")
            ui.echo(f"Prefilled tags: {', '.join([t.replace('_', ' ').title() for t in selected_tags])}\n")
            ui.echo("You can add or remove tags to reach 2-4 total.\n")
    
    # Manual tag selection/adjustment
    while len(selected_tags) < min_tags or (
        len(selected_tags) < max_tags and len(selected_tags) < len(available_tags)
    ):
        # Show current selection
        if selected_tags:
            ui.echo(f"\nSelected: {', '.join([t.replace('_', ' ').title() for t in selected_tags])} ({len(selected_tags)}/{max_tags})\n")
        
        # Build available options
        available_display = []
        available_indices = []
        for i, tag in enumerate(available_tags):
            if tag not in selected_tags:
                available_display.append(display[i])
                available_indices.append(i)
        
        # Add option to remove tags if we have any
        if selected_tags:
            available_display.append("Remove a tag")
        
        if len(selected_tags) >= min_tags:
            available_display.append("Done")
        
        prompt = f"Select tag ({len(selected_tags)}/{max_tags}):"
        selection = ui.menu(prompt, available_display)
        
        if selection == "Done":
            break
        
        if selection == "Remove a tag":
            # Show tags to remove
            remove_options = [t.replace("_", " ").title() for t in selected_tags]
            remove_selection = ui.menu("Remove which tag?", remove_options)
            remove_idx = remove_options.index(remove_selection)
            removed_tag = selected_tags.pop(remove_idx)
            ui.echo(f"Removed: {removed_tag.replace('_', ' ').title()}\n")
            continue
        
        idx = available_display.index(selection)
        if idx < len(available_indices):
            tag_idx = available_indices[idx]
            selected_tags.append(available_tags[tag_idx])
            ui.echo(f"Added: {display[tag_idx]}\n")
    
    # Ensure we have at least min_tags
    if len(selected_tags) < min_tags:
        ui.echo(f"\nWarning: You have {len(selected_tags)} tags, minimum is {min_tags}.\n")
        # Force selection of remaining tags
        while len(selected_tags) < min_tags:
            available_display = []
            available_indices = []
            for i, tag in enumerate(available_tags):
                if tag not in selected_tags:
                    available_display.append(display[i])
                    available_indices.append(i)
            
            selection = ui.menu(f"Select tag ({len(selected_tags) + 1}/{min_tags}):", available_display)
            idx = available_display.index(selection)
            if idx < len(available_indices):
                tag_idx = available_indices[idx]
                selected_tags.append(available_tags[tag_idx])
                ui.echo(f"Added: {display[tag_idx]}\n")
    
    return selected_tags


def create_custom_race(ui: UI, races: Dict[str, Dict[str, object]]) -> tuple[str, Dict[str, object]]:
    """Create a custom race through UI prompts."""
    ui.heading("Create Custom Race")
    ui.echo("You will now create your own custom race.\n")
    
    # Get race name
    name = ""
    while not name:
        name = ui.prompt("Enter your race name:").strip()
        if not name:
            ui.echo("Race name cannot be empty.\n")
    
    # Generate race_id from name
    race_id = "custom_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    
    # Ensure unique race_id
    base_race_id = race_id
    counter = 1
    while race_id in races:
        race_id = f"{base_race_id}_{counter}"
        counter += 1
    
    # Choose attributes
    body_type = choose_body_type(ui, "humanoid")
    ui.echo("\n")
    size = choose_size(ui, "medium")
    ui.echo("\n")
    archetype = choose_archetype(ui, "forest_creature")
    ui.echo("\n")
    flavor_tags = choose_flavor_tags(ui, min_tags=2, max_tags=4)
    
    # Create race data
    race_data = {
        "race_id": race_id,
        "display_name": name,
        "name": name,
        "description": f"A custom race: {name}",
        "body_type_default": body_type,
        "size_default": size,
        "archetype_default": archetype,
        "tags": [],
        "modifiers": [],
        "flavor": {},
        "summary": f"A custom race: {name}",
        "flavor_tags": flavor_tags,
    }
    
    ui.echo(f"\nCustom race '{name}' created with ID: {race_id}\n")
    return race_id, race_data


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
    # Choose or create race
    race_id = choose_race(ui, races)
    
    # Handle custom race creation
    if race_id is None:
        race_id, custom_race_data = create_custom_race(ui, races)
        # Add custom race to races dict for this session
        races[race_id] = custom_race_data
    
    race_data = races[race_id]
    
    # Get character name
    name = ui.prompt("Enter your name") or "Wanderer"
    ui.echo("\n")
    
    # Choose body type, size, and archetype
    body_type_default = str(race_data.get("body_type_default", "humanoid"))
    body_type = choose_body_type(ui, body_type_default)
    ui.echo("\n")
    
    size_default = str(race_data.get("size_default", "medium"))
    size = choose_size(ui, size_default)
    ui.echo("\n")
    
    archetype_default = str(race_data.get("archetype_default", "forest_creature"))
    archetype = choose_archetype(ui, archetype_default)
    ui.echo("\n")
    
    # Use race's flavor_tags as default, but player can override if needed
    flavor_tags = list(race_data.get("flavor_tags", []))
    
    # Build character with selected attributes
    character = build_character_from_race(
        race_id=race_id,
        race_data=race_data,
        name=name,
        body_type=body_type,
        size=size,
        archetype=archetype,
        flavor_tags=flavor_tags,
    )
    
    # Ask vore preferences after character setup
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
        naiad_dialogue = load_dialogue_catalog(data_dir, "dialogue_naiad.json")
        druid_dialogue = load_dialogue_catalog(data_dir, "dialogue_druid.json")
        fisher_dialogue = load_dialogue_catalog(data_dir, "dialogue_fisher.json")
        astrin_dialogue = load_dialogue_catalog(data_dir, "dialogue_astrin.json")
        # Merge dialogue nodes from all catalogs
        from .dialogue import DialogueCatalog
        all_nodes = (
            list(forest_dialogue.nodes)
            + list(echo_dialogue.nodes)
            + list(naiad_dialogue.nodes)
            + list(druid_dialogue.nodes)
            + list(fisher_dialogue.nodes)
            + list(astrin_dialogue.nodes)
        )
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
                # Backward compatibility: migrate old race_id "wolfkin" to "wolf_kin"
                if state.character.race_id == "wolfkin":
                    state.character.race_id = "wolf_kin"
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
