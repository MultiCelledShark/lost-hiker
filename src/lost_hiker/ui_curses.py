"""
Centralized curses UI module for Lost Hiker.

This module provides a structured curses interface inspired by the layout patterns
from Botany (https://github.com/jifunks/botany), adapted for Lost Hiker's needs.

Botany-inspired structural elements:
- Four-window layout (status bar, narrative, side panel, input bar)
- Dynamic window sizing based on terminal dimensions
- Text wrapping utilities
- Scrolling menu system

Botany is licensed under ISC License. See THIRD_PARTY_LICENSES.md for details.
"""

from __future__ import annotations

import curses
import textwrap
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Minimum terminal size requirements
MIN_HEIGHT = 30
MIN_WIDTH = 100


@dataclass
class UIWindows:
    """Container for all curses windows in the UI layout."""

    stdscr: curses.window
    status_win: curses.window
    narrative_win: curses.window
    side_win: Optional[curses.window]
    input_win: curses.window


@dataclass
class MenuState:
    """State for scrolling menu navigation."""

    selected_index: int = 0
    start_index: int = 0  # First visible option index
    visible_rows: int = 0  # Number of options visible in window


def check_terminal_size(stdscr: curses.window) -> None:
    """
    Enforce minimum terminal size (100×30).
    
    Blocks until terminal is large enough, displaying a message if too small.
    
    Args:
        stdscr: The main curses window
    """
    while True:
        height, width = stdscr.getmaxyx()
        if height >= MIN_HEIGHT and width >= MIN_WIDTH:
            break
        
        stdscr.clear()
        message = f"Please enlarge your terminal to at least {MIN_WIDTH}×{MIN_HEIGHT}."
        try:
            stdscr.addstr(0, 0, message)
            stdscr.addstr(1, 0, f"Current size: {width}×{height}")
            stdscr.addstr(2, 0, "Press any key to check again...")
            stdscr.refresh()
            stdscr.getch()
        except curses.error:
            # Terminal might be too small even to display message
            pass


def init_ui(stdscr: curses.window) -> UIWindows:
    """
    Initialize curses UI with proper settings and window layout.
    
    Sets up:
    - Curses mode (noecho, cbreak, keypad)
    - Color support if available
    - Four-window layout (status, narrative, side, input)
    
    Args:
        stdscr: The main curses window
        
    Returns:
        UIWindows object containing all UI windows
    """
    # Enforce minimum terminal size
    check_terminal_size(stdscr)
    
    # Basic curses setup
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.curs_set(0)  # Hide cursor initially
    
    # Initialize colors if available
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        # Define color pairs for UI elements
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # Highlight color
        curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Status color
        curses.init_pair(3, curses.COLOR_GREEN, -1)  # Success/info color
    
    # Create window layout
    windows = _create_window_layout(stdscr)
    
    return windows


def _create_window_layout(stdscr: curses.window) -> UIWindows:
    """
    Create the four-window layout inspired by Botany's structure.
    
    Layout:
    - Status bar: Top 1 line (location, time, stamina, weather)
    - Narrative window: Main content area (most of screen)
    - Side panel: Right side for context/inventory (optional, if width allows)
    - Input bar: Bottom 2 lines for prompts and input
    
    Args:
        stdscr: The main curses window
        
    Returns:
        UIWindows object with all windows created
    """
    height, width = stdscr.getmaxyx()
    
    # Status bar: top line
    status_height = 1
    status_win = stdscr.subwin(status_height, width, 0, 0)
    
    # Input bar: bottom 2 lines
    input_height = 2
    input_win = stdscr.subwin(input_height, width, height - input_height, 0)
    
    # Calculate space for narrative and side panel
    available_height = height - status_height - input_height
    available_width = width
    
    # Side panel: use right 30% of width if terminal is wide enough (>= 120 chars)
    # Otherwise, just use narrative window
    side_win = None
    if width >= 120:
        side_width = max(30, int(width * 0.3))
        narrative_width = width - side_width
        narrative_win = stdscr.subwin(
            available_height, narrative_width, status_height, 0
        )
        side_win = stdscr.subwin(
            available_height, side_width, status_height, narrative_width
        )
    else:
        narrative_width = width
        narrative_win = stdscr.subwin(
            available_height, narrative_width, status_height, 0
        )
    
    return UIWindows(
        stdscr=stdscr,
        status_win=status_win,
        narrative_win=narrative_win,
        side_win=side_win,
        input_win=input_win,
    )


def draw_frame(windows: UIWindows, game_state: Optional[object] = None) -> None:
    """
    Draw the main UI frame with status bar and layout.
    
    Args:
        windows: UIWindows object containing all windows
        game_state: Optional game state for status information
    """
    # Clear all windows
    windows.status_win.erase()
    windows.narrative_win.erase()
    if windows.side_win:
        windows.side_win.erase()
    windows.input_win.erase()
    
    # Draw status bar
    _draw_status_bar(windows.status_win, game_state)
    
    # Draw side panel if available
    if windows.side_win:
        _draw_side_panel(windows.side_win, game_state)
    
    # Refresh all windows
    windows.status_win.refresh()
    windows.narrative_win.refresh()
    if windows.side_win:
        windows.side_win.refresh()
    windows.input_win.refresh()


def _draw_status_bar(win: curses.window, game_state: Optional[object] = None) -> None:
    """Draw the top status bar with location, time, stamina, weather."""
    try:
        win.erase()
        max_y, max_x = win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        
        status_parts = []
        
        if game_state:
            # Location
            location = getattr(game_state, "active_zone", "Unknown")
            status_parts.append(f"Location: {location}")
            
            # Day/Season
            day = getattr(game_state, "day", 1)
            season = getattr(game_state, "current_season", "spring")
            status_parts.append(f"Day {day} ({season})")
            
            # Stamina
            stamina = getattr(game_state, "stamina", 0.0)
            stamina_max = getattr(
                getattr(game_state, "character", None), "stamina_max", 100.0
            )
            status_parts.append(f"Stamina: {stamina:.0f}/{stamina_max:.0f}")
            
            # Time of day
            time_of_day = getattr(game_state, "time_of_day", "Day")
            status_parts.append(f"Time: {time_of_day}")
        else:
            status_parts.append("Lost Hiker")
        
        # Join with separators
        status_text = " | ".join(status_parts)
        
        # Truncate if too long
        if len(status_text) > max_x - 1:
            status_text = status_text[: max_x - 1]
        
        win.addstr(0, 0, status_text, curses.color_pair(2) | curses.A_BOLD)
    except curses.error:
        pass


def _draw_side_panel(win: curses.window, game_state: Optional[object] = None) -> None:
    """Draw the side panel with context information (inventory, etc.)."""
    try:
        win.erase()
        max_y, max_x = win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        
        # Draw a border
        win.box()
        
        # Add content if game_state available
        if game_state:
            y = 1
            # Inventory summary
            inventory = getattr(game_state, "inventory", [])
            if inventory:
                win.addstr(y, 1, "Inventory:", curses.A_BOLD)
                y += 1
                for item in inventory[: min(5, len(inventory))]:
                    if y >= max_y - 1:
                        break
                    item_text = item[: max_x - 3]
                    win.addstr(y, 2, item_text)
                    y += 1
                if len(inventory) > 5:
                    win.addstr(y, 2, f"... and {len(inventory) - 5} more")
    except curses.error:
        pass


def print_message(text: str, windows: UIWindows) -> None:
    """
    Print a message to the narrative window.
    
    Text is automatically wrapped to fit the window width.
    
    Args:
        text: Message text to display
        windows: UIWindows object
    """
    _print_to_narrative(text, windows.narrative_win)


def print_description(text: str, windows: UIWindows) -> None:
    """
    Print a description to the narrative window.
    
    Similar to print_message but semantically for descriptions.
    
    Args:
        text: Description text to display
        windows: UIWindows object
    """
    _print_to_narrative(text, windows.narrative_win)


def _print_to_narrative(text: str, win: curses.window) -> None:
    """Internal helper to print wrapped text to narrative window."""
    try:
        max_y, max_x = win.getmaxyx()
        if max_x <= 0 or max_y <= 0:
            return
        
        # Get current cursor position
        cur_y, cur_x = win.getyx()
        
        # Wrap text
        wrap_width = max(1, max_x - 1)
        lines = []
        for paragraph in text.split("\n"):
            if paragraph.strip():
                wrapped = textwrap.wrap(
                    paragraph,
                    width=wrap_width,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                lines.extend(wrapped if wrapped else [paragraph[:wrap_width]])
            else:
                lines.append("")
        
        # Print lines, scrolling if necessary
        for line in lines:
            if cur_y >= max_y - 1:
                # Scroll the window
                win.scroll()
                cur_y = max_y - 2
            try:
                win.addstr(cur_y, 0, line[: max_x - 1])
                cur_y += 1
            except curses.error:
                break
        
        win.move(cur_y, 0)
        win.refresh()
    except curses.error:
        pass


def draw_menu(
    prompt: str,
    options: List[str],
    selected_index: int,
    windows: UIWindows,
    menu_state: Optional[MenuState] = None,
    existing_lines: Optional[List[str]] = None,
) -> MenuState:
    """
    Draw a scrolling menu with multiple visible options.
    
    Implements scrolling behavior:
    - Up/Down: Move selection within full list, auto-scroll window
    - Left/Right: Page up/down by visible_rows
    - Always shows multiple options when available
    
    Args:
        prompt: Menu prompt text
        options: List of option strings
        selected_index: Currently selected option index
        windows: UIWindows object
        menu_state: Optional existing menu state for continuity
        existing_lines: Optional list of existing scene lines to preserve above menu
        
    Returns:
        Updated MenuState
    """
    if not options:
        return MenuState()
    
    # Clamp selected_index
    selected_index = max(0, min(selected_index, len(options) - 1))
    
    # Initialize or update menu state
    if menu_state is None:
        menu_state = MenuState(selected_index=selected_index)
    else:
        menu_state.selected_index = selected_index
    
    # Calculate visible rows
    max_y, max_x = windows.narrative_win.getmaxyx()
    
    # Calculate space used by existing lines
    scene_lines_used = len(existing_lines) if existing_lines else 0
    
    # Reserve space for prompt (2 lines), page indicator (1 line), and padding
    reserved_lines = 3
    available_lines = max(1, max_y - scene_lines_used - reserved_lines)
    
    # Calculate how many options can fit (accounting for wrapping)
    # Estimate: each option might wrap to 2-3 lines, so be conservative
    estimated_lines_per_option = 2
    menu_state.visible_rows = max(3, available_lines // estimated_lines_per_option)
    
    # Ensure we show at least 3 options, but as many as fit
    menu_state.visible_rows = min(menu_state.visible_rows, len(options))
    menu_state.visible_rows = max(3, menu_state.visible_rows)
    
    # Calculate start_index to keep selected_index visible
    if selected_index < menu_state.start_index:
        # Scroll up to show selected option
        menu_state.start_index = selected_index
    elif selected_index >= menu_state.start_index + menu_state.visible_rows:
        # Scroll down to show selected option
        menu_state.start_index = selected_index - menu_state.visible_rows + 1
    
    # Clamp start_index
    menu_state.start_index = max(
        0, min(menu_state.start_index, len(options) - menu_state.visible_rows)
    )
    
    # Calculate end_index
    end_index = min(menu_state.start_index + menu_state.visible_rows, len(options))
    
    # Draw menu
    try:
        # Clear or preserve existing content
        if existing_lines is None:
            windows.narrative_win.erase()
            y = 0
        else:
            # Preserve existing scene content, but clear menu area
            # First, render existing scene lines (limit to leave room for menu)
            max_scene_lines = max(1, max_y - reserved_lines - menu_state.visible_rows - 2)
            scene_lines_to_show = existing_lines[-max_scene_lines:] if len(existing_lines) > max_scene_lines else existing_lines
            
            y = 0
            for line in scene_lines_to_show:
                if y >= max_scene_lines:
                    break
                try:
                    windows.narrative_win.move(y, 0)
                    windows.narrative_win.clrtoeol()
                    windows.narrative_win.addstr(line[: max_x - 1])
                    y += 1
                except curses.error:
                    break
            
            # Clear the menu area (from y to end)
            menu_start_y = y + 1  # One blank line after scene
            for clear_y in range(menu_start_y, max_y):
                try:
                    windows.narrative_win.move(clear_y, 0)
                    windows.narrative_win.clrtoeol()
                except curses.error:
                    break
            
            y = menu_start_y
        
        # Draw prompt
        prompt_lines = _wrap_text(prompt, max_x - 1)
        for line in prompt_lines:
            if y >= max_y - 1:
                break
            windows.narrative_win.addstr(y, 0, line[: max_x - 1], curses.A_BOLD)
            y += 1
        
        # Draw options
        option_prefix_width = len(f"  {len(options)}. ")
        wrap_width = max(1, max_x - option_prefix_width - 1)
        
        for idx in range(menu_state.start_index, end_index):
            if y >= max_y - 2:  # Leave space for page indicator
                break
            
            option = options[idx]
            is_selected = idx == selected_index
            
            # Wrap option text
            wrapped_lines = _wrap_text(option, wrap_width)
            if not wrapped_lines:
                wrapped_lines = [option[:wrap_width]]
            
            # Draw each wrapped line
            for line_idx, line in enumerate(wrapped_lines):
                if y >= max_y - 2:
                    break
                
                if line_idx == 0:
                    prefix = f"  {idx + 1}. "
                else:
                    prefix = "      "  # Indent continuation lines
                
                full_line = f"{prefix}{line}"
                
                # Highlight selected option
                attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
                if is_selected:
                    attr |= curses.color_pair(1)
                
                try:
                    windows.narrative_win.addstr(y, 0, full_line[: max_x - 1], attr)
                    y += 1
                except curses.error:
                    break
        
        # Draw page indicator if needed
        if len(options) > menu_state.visible_rows and y < max_y - 1:
            start_display = menu_state.start_index + 1
            end_display = end_index
            indicator = f"Options {start_display}-{end_display} of {len(options)}"
            windows.narrative_win.addstr(
                max_y - 1, 0, indicator[: max_x - 1], curses.A_DIM
            )
        
        windows.narrative_win.refresh()
    except curses.error:
        pass
    
    return menu_state


def _wrap_text(text: str, width: int) -> List[str]:
    """Wrap text to specified width, returning list of lines."""
    if width <= 0:
        return [text]
    wrapped = textwrap.wrap(
        text, width=width, break_long_words=True, break_on_hyphens=False
    )
    return wrapped if wrapped else [text[:width]]


def read_input(prompt: str, windows: UIWindows) -> str:
    """
    Read user input with a prompt displayed in the input window.
    
    Args:
        prompt: Prompt text to display
        windows: UIWindows object
        
    Returns:
        User input string
    """
    try:
        windows.input_win.erase()
        max_y, max_x = windows.input_win.getmaxyx()
        
        # Show prompt on first line
        if max_y >= 1:
            windows.input_win.addstr(0, 0, prompt[: max_x - 1])
        
        # Show "> " on second line (or first if only one line)
        input_line = 1 if max_y >= 2 else 0
        windows.input_win.addstr(input_line, 0, "> ")
        
        # Position cursor after "> "
        cursor_x = 2
        windows.input_win.move(input_line, cursor_x)
        curses.curs_set(1)  # Show cursor for input
        windows.input_win.refresh()
        
        # Get input
        curses.echo()
        try:
            raw = windows.input_win.getstr(input_line, cursor_x)
        finally:
            curses.noecho()
            curses.curs_set(0)  # Hide cursor again
        
        value = raw.decode("utf-8", errors="ignore").strip()
        return value
    except curses.error:
        return ""


def handle_menu_navigation(
    key: int,
    options: List[str],
    menu_state: MenuState,
    windows: UIWindows,
) -> Tuple[Optional[int], bool]:
    """
    Handle menu navigation keys and return updated selection and whether to confirm.
    
    Args:
        key: Curses key code
        options: List of menu options
        menu_state: Current menu state
        windows: UIWindows object
        
    Returns:
        Tuple of (new_selected_index or None, should_confirm)
        If should_confirm is True, the menu selection should be confirmed
    """
    if not options:
        return None, False
    
    max_y, max_x = windows.narrative_win.getmaxyx()
    visible_rows = menu_state.visible_rows
    
    # Enter/Return: confirm selection
    if key in (curses.KEY_ENTER, 10, 13):
        return menu_state.selected_index, True
    
    # Up arrow: move selection up
    if key in (curses.KEY_UP, ord("k")):
        if menu_state.selected_index > 0:
            menu_state.selected_index -= 1
        else:
            # Wrap to last option
            menu_state.selected_index = len(options) - 1
        return menu_state.selected_index, False
    
    # Down arrow: move selection down
    if key in (curses.KEY_DOWN, ord("j")):
        if menu_state.selected_index < len(options) - 1:
            menu_state.selected_index += 1
        else:
            # Wrap to first option
            menu_state.selected_index = 0
        return menu_state.selected_index, False
    
    # Left arrow: page up
    if key == curses.KEY_LEFT:
        new_start = max(0, menu_state.start_index - visible_rows)
        menu_state.start_index = new_start
        
        # Adjust selected_index to stay within visible range
        if menu_state.selected_index < menu_state.start_index:
            menu_state.selected_index = menu_state.start_index
        elif menu_state.selected_index >= menu_state.start_index + visible_rows:
            menu_state.selected_index = menu_state.start_index + visible_rows - 1
        
        # Clamp selected_index
        menu_state.selected_index = max(
            0, min(menu_state.selected_index, len(options) - 1)
        )
        return menu_state.selected_index, False
    
    # Right arrow: page down
    if key == curses.KEY_RIGHT:
        new_start = min(
            len(options) - visible_rows, menu_state.start_index + visible_rows
        )
        menu_state.start_index = max(0, new_start)
        
        # Adjust selected_index to stay within visible range
        if menu_state.selected_index < menu_state.start_index:
            menu_state.selected_index = menu_state.start_index
        elif menu_state.selected_index >= menu_state.start_index + visible_rows:
            menu_state.selected_index = menu_state.start_index + visible_rows - 1
        
        # Clamp selected_index
        menu_state.selected_index = max(
            0, min(menu_state.selected_index, len(options) - 1)
        )
        return menu_state.selected_index, False
    
    # Number keys (1-9): direct selection
    if ord("1") <= key <= ord("9"):
        numeric_choice = key - ord("1")
        if 0 <= numeric_choice < len(options):
            menu_state.selected_index = numeric_choice
            return menu_state.selected_index, False
    
    # Unknown key
    return None, False

