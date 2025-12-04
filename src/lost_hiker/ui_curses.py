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

from .hunger import apply_stamina_cap

# Minimum terminal size requirements
MIN_HEIGHT = 30
MIN_WIDTH = 100

# The frame border is now 2 cells thick (previously 1); derived windows begin
# BORDER_THICKNESS cells inside frame_win so every UI pane stays aligned.
BORDER_THICKNESS = 2


@dataclass
class UIWindows:
    """Container for all curses windows in the UI layout."""

    stdscr: curses.window
    header_win: curses.window  # Top line: status/header (on stdscr row 0)
    frame_win: curses.window  # Frame window wrapping entire play area below header
    content_win: curses.window  # Main scrollable text area (inside frame)
    menu_win: curses.window  # Fixed height for menu choices
    input_win: curses.window  # Bottom line: input prompt (inside frame)


@dataclass
class MenuState:
    """State for scrolling menu navigation."""

    selected_index: int = 0
    start_index: int = 0  # First visible option index
    visible_rows: int = 0  # Number of options visible in window
    menu_start_y: int = 0  # Y position where menu starts (for partial redraws)
    scene_lines_count: int = 0  # Number of scene lines above menu


@dataclass
class BorderTheme:
    """Border theme configuration for window borders."""

    h_char: str  # Horizontal border character
    v_char: str  # Vertical border character
    tl_char: str  # Top-left corner
    tr_char: str  # Top-right corner
    bl_char: str  # Bottom-left corner
    br_char: str  # Bottom-right corner
    color_pair_id: int  # Curses color pair ID for this border


# Color pair IDs for border themes
# Note: Pairs 1-3 are already used for UI elements (highlight, status, success)
COLOR_PAIR_SPRING_SAFE = 10
COLOR_PAIR_SUMMER_SAFE = 11
COLOR_PAIR_AUTUMN_SAFE = 12
COLOR_PAIR_WINTER_SAFE = 13
COLOR_PAIR_BELLIED = 14
COLOR_PAIR_DANGER = 15


class ContentRenderer:
    """
    Renders text content to a curses window with automatic wrapping and scrolling.
    
    Uses a buffer-based approach: all text is stored in a lines buffer,
    and when the buffer exceeds window height, only the most recent lines
    are kept and displayed. This creates a scrolling log effect.
    """
    
    def __init__(self, win: curses.window) -> None:
        """
        Initialize renderer with target window.
        
        Args:
            win: Curses window to render content to
        """
        self.win = win
        self.lines: List[str] = []  # Buffer storing all wrapped lines
    
    def _redraw(self) -> None:
        """
        Redraw the entire window from the lines buffer.
        
        Erases the window and draws all lines from the buffer,
        starting at row 0.
        """
        try:
            # Erase the window
            self.win.erase()
            
            # Get window dimensions
            visible_height, visible_width = self.win.getmaxyx()
            
            # Draw each line from the buffer starting at row 0
            for y, line in enumerate(self.lines):
                if y >= visible_height:
                    break
                try:
                    # Truncate line to fit width
                    display_line = line[:visible_width]
                    self.win.addstr(y, 0, display_line)
                except curses.error:
                    break
            
            # Refresh the window
            self.win.refresh()
        except curses.error:
            pass
    
    def write_block(self, text: str) -> None:
        """
        Write a block of text, adding it to the buffer and redrawing.
        
        This is the core method that handles buffer management:
        - Splits text into paragraphs by newline
        - Wraps each paragraph to window width using textwrap.wrap
        - Appends wrapped lines to self.lines
        - Gets visible_height from getmaxyx()
        - If len(self.lines) > visible_height, keeps only last visible_height lines
        - Calls _redraw()
        
        Args:
            text: Text block to write (may contain newlines)
        """
        # Get window dimensions for wrapping
        visible_height, visible_width = self.win.getmaxyx()
        wrap_width = max(1, visible_width)
        
        # Split text into paragraphs by newline
        paragraphs = text.split("\n")
        
        # Process each paragraph
        for para in paragraphs:
            if not para.strip():
                # Empty line - add as empty string
                self.lines.append("")
            else:
                # Wrap paragraph to window width
                wrapped_lines = textwrap.wrap(
                    para,
                    width=wrap_width,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                
                if not wrapped_lines:
                    # Very long word - truncate
                    wrapped_lines = [para[:wrap_width]]
                
                # Add wrapped lines to buffer
                self.lines.extend(wrapped_lines)
        
        # Trim buffer to keep only the most recent lines that fit
        if len(self.lines) > visible_height:
            self.lines = self.lines[-visible_height:]
        
        # Redraw the window
        self._redraw()
    
    def write(self, text: str) -> None:
        """
        Write text to the window with automatic wrapping.
        
        Delegates to write_block() for buffer-based rendering.
        
        Args:
            text: Text to write (may contain newlines)
        """
        self.write_block(text)
    
    def write_line(self, text: str) -> None:
        """
        Write a single line of text (adds newline automatically).
        
        Delegates to write_block() for buffer-based rendering.
        
        Args:
            text: Text to write
        """
        self.write_block(text + "\n")
    
    def clear(self) -> None:
        """Clear all content and reset buffer."""
        self.lines.clear()
        try:
            self.win.erase()
            self.win.refresh()
        except curses.error:
            pass
    
    def reset_position(self) -> None:
        """Reset is a no-op for buffer-based renderer (kept for compatibility)."""
        pass


def get_border_theme(game_state: Optional[object] = None) -> BorderTheme:
    """
    Determine border theme based on game state (season, bellied state, danger).
    
    Theme selection priority:
    1. Bellied state (overrides season)
    2. Danger/low stamina (overrides color only)
    3. Season (spring, summer, fall/autumn, winter)
    
    Args:
        game_state: Optional game state object
        
    Returns:
        BorderTheme instance with appropriate characters and color
    """
    # Default safe spring theme
    season = "spring"
    bellied = False
    in_danger = False
    
    if game_state:
        # Get season (handle both "fall" and "autumn")
        season_raw = getattr(game_state, "current_season", "spring")
        season = season_raw.lower()
        if season == "fall":
            season = "autumn"
        
        # Check bellied state
        belly_state = getattr(game_state, "belly_state", None)
        if belly_state and isinstance(belly_state, dict):
            bellied = belly_state.get("active", False)
        
        # Check danger state (low stamina or in combat)
        stamina = getattr(game_state, "stamina", 100.0)
        character = getattr(game_state, "character", None)
        if character:
            # Get base stamina_max with timed modifiers
            base_stamina_max = character.get_stat(
                "stamina_max",
                timed_modifiers=getattr(game_state, "timed_modifiers", []),
                current_day=getattr(game_state, "day", 1),
            )
            # Apply caps (rest, hunger, condition) to get actual maximum
            stamina_max = apply_stamina_cap(game_state, base_stamina_max)
        else:
            stamina_max = 100.0  # Fallback
        critical_threshold = stamina_max * 0.25  # 25% of max stamina
        
        in_danger = stamina <= critical_threshold
        # Could also check for combat state if available:
        # in_combat = getattr(game_state, "in_combat", False)
        # in_danger = in_danger or in_combat
    
    # Bellied state overrides everything
    if bellied:
        return BorderTheme(
            h_char="~",
            v_char="~",
            tl_char="o",
            tr_char="o",
            bl_char="o",
            br_char="o",
            color_pair_id=COLOR_PAIR_BELLIED,
        )
    
    # Base seasonal themes
    if season == "spring":
        theme = BorderTheme(
            h_char="-",
            v_char="|",
            tl_char="+",
            tr_char="+",
            bl_char="+",
            br_char="+",
            color_pair_id=COLOR_PAIR_SPRING_SAFE,
        )
    elif season == "summer":
        theme = BorderTheme(
            h_char="=",
            v_char="|",
            tl_char="+",
            tr_char="+",
            bl_char="+",
            br_char="+",
            color_pair_id=COLOR_PAIR_SUMMER_SAFE,
        )
    elif season == "autumn":
        theme = BorderTheme(
            h_char="~",
            v_char=":",
            tl_char="*",
            tr_char="*",
            bl_char="*",
            br_char="*",
            color_pair_id=COLOR_PAIR_AUTUMN_SAFE,
        )
    elif season == "winter":
        theme = BorderTheme(
            h_char="#",
            v_char="|",
            tl_char="#",
            tr_char="#",
            bl_char="#",
            br_char="#",
            color_pair_id=COLOR_PAIR_WINTER_SAFE,
        )
    else:
        # Fallback to spring
        theme = BorderTheme(
            h_char="-",
            v_char="|",
            tl_char="+",
            tr_char="+",
            bl_char="+",
            br_char="+",
            color_pair_id=COLOR_PAIR_SPRING_SAFE,
        )
    
    # Override color for danger (keep seasonal characters)
    if in_danger:
        theme.color_pair_id = COLOR_PAIR_DANGER
    
    return theme


def draw_window_border(win: curses.window, border_theme: BorderTheme) -> None:
    """
    Draw a border around a window using the specified theme.
    
    Args:
        win: Curses window to draw border on
        border_theme: BorderTheme instance with characters and color
    """
    try:
        max_y, max_x = win.getmaxyx()
        if max_x < BORDER_THICKNESS * 2 or max_y < BORDER_THICKNESS * 2:
            return
        
        # Apply color attribute if colors are available
        attr = 0
        if curses.has_colors():
            try:
                attr = curses.color_pair(border_theme.color_pair_id)
            except (curses.error, ValueError):
                attr = 0
        
        # Border occupies BORDER_THICKNESS rows/cols; content windows start at that offset.

        # Draw horizontal bands (top and bottom) BORDER_THICKNESS rows thick
        for offset in range(BORDER_THICKNESS):
            y_top = offset
            y_bottom = max_y - 1 - offset
            if y_top >= max_y or y_bottom < 0:
                break
            for x in range(0, max_x):
                try:
                    win.addch(y_top, x, border_theme.h_char, attr)
                    if y_bottom != y_top:
                        win.addch(y_bottom, x, border_theme.h_char, attr)
                except curses.error:
                    break
        
        # Draw vertical bands (left and right) BORDER_THICKNESS columns thick,
        # skipping the horizontal bands to reduce redraw churn.
        vertical_start = BORDER_THICKNESS
        vertical_end = max_y - BORDER_THICKNESS
        if vertical_start < vertical_end:
            for offset in range(BORDER_THICKNESS):
                x_left = offset
                x_right = max_x - 1 - offset
                if x_left >= max_x or x_right < 0:
                    break
                for y in range(vertical_start, vertical_end):
                    try:
                        win.addch(y, x_left, border_theme.v_char, attr)
                        if x_right != x_left:
                            win.addch(y, x_right, border_theme.v_char, attr)
                    except curses.error:
                        break
        
        # Draw corners
        try:
            win.addch(0, 0, border_theme.tl_char, attr)  # Top-left
        except curses.error:
            pass
        try:
            win.addch(0, max_x - 1, border_theme.tr_char, attr)  # Top-right
        except curses.error:
            pass
        try:
            win.addch(max_y - 1, 0, border_theme.bl_char, attr)  # Bottom-left
        except curses.error:
            pass
        try:
            win.addch(max_y - 1, max_x - 1, border_theme.br_char, attr)  # Bottom-right
        except curses.error:
            pass
    except (curses.error, ValueError, AttributeError):
        pass


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
        
        # Define color pairs for border themes
        curses.init_pair(COLOR_PAIR_SPRING_SAFE, curses.COLOR_GREEN, -1)  # Soft green
        curses.init_pair(COLOR_PAIR_SUMMER_SAFE, curses.COLOR_YELLOW, -1)  # Bright yellow-green
        curses.init_pair(COLOR_PAIR_AUTUMN_SAFE, curses.COLOR_YELLOW, -1)  # Orange/brown (using yellow as fallback)
        curses.init_pair(COLOR_PAIR_WINTER_SAFE, curses.COLOR_CYAN, -1)  # Cold blue/cyan
        curses.init_pair(COLOR_PAIR_BELLIED, curses.COLOR_MAGENTA, -1)  # Muted purple/magenta
        curses.init_pair(COLOR_PAIR_DANGER, curses.COLOR_RED, -1)  # Warning red
    
    # Create window layout
    windows = _create_window_layout(stdscr)
    
    # Note: Don't clear/refresh stdscr here - let the first draw_frame() call handle it
    # Clearing stdscr here might interfere with the windows we just created
    
    return windows


def _create_window_layout(stdscr: curses.window) -> UIWindows:
    """
    Create the window layout with frame wrapping play area.
    
    Layout:
    - header_win: Top 1 line on stdscr row 0 (status/header, never scrolls)
    - frame_win: Frame window covering entire play area below header (has border)
    - content_win: Main scrollable text area (inside frame, at top)
    - input_win: Bottom 1 line (input prompt, inside frame at bottom)
    - menu_win: Fixed height for menu choices (10 lines, only visible during menus)
    
    Args:
        stdscr: The main curses window
        
    Returns:
        UIWindows object with all windows created
    """
    max_y, max_x = stdscr.getmaxyx()
    
    # Header: top 1 line on stdscr row 0
    header_height = 1
    header_win = stdscr.subwin(header_height, max_x, 0, 0)
    
    # Frame: covers entire play area below header
    frame_top = header_height
    frame_height = max_y - header_height
    frame_width = max_x
    frame_win = curses.newwin(frame_height, frame_width, frame_top, 0)
    
    # Inside frame: calculate inner dimensions (minus borders)
    inner_height = frame_height - (2 * BORDER_THICKNESS)
    inner_width = frame_width - (2 * BORDER_THICKNESS)
    
    # Window heights (from bottom to top)
    input_height = 1
    menu_height = 6  # Small fixed size for menu choices
    content_height = inner_height - input_height - menu_height
    
    # Position windows inside frame (relative to frame_win, accounting for border)
    # All positions are relative to frame_win's interior starting BORDER_THICKNESS cells in
    content_y = BORDER_THICKNESS  # First row inside frame after top border band
    menu_y = content_y + content_height
    input_y = menu_y + menu_height
    
    # Create derived windows inside frame_win
    # Note: derwin positions are relative to parent window (frame_win)
    content_win = frame_win.derwin(content_height, inner_width, content_y, BORDER_THICKNESS)
    menu_win = frame_win.derwin(menu_height, inner_width, menu_y, BORDER_THICKNESS)
    input_win = frame_win.derwin(input_height, inner_width, input_y, BORDER_THICKNESS)
    
    return UIWindows(
        stdscr=stdscr,
        header_win=header_win,
        frame_win=frame_win,
        content_win=content_win,
        menu_win=menu_win,
        input_win=input_win,
    )


def draw_frame(windows: UIWindows, game_state: Optional[object] = None, clear_content: bool = False) -> None:
    """
    Draw the main UI frame with header and borders.
    
    Draw order:
    1. Draw header on stdscr row 0
    2. Draw border on frame_win and refresh it
    3. Draw/refresh content_win via ContentRenderer (caller handles this)
    4. Draw/refresh input_win for current prompt (caller handles this)
    
    Args:
        windows: UIWindows object containing all windows
        game_state: Optional game state for status information
        clear_content: If True, clear the content window. Default False to preserve content.
    """
    # Clear header (always clear)
    windows.header_win.erase()
    
    # Clear input window (always clear)
    windows.input_win.erase()
    
    # Only clear content if explicitly requested
    if clear_content:
        windows.content_win.erase()
    
    # Clear menu (it's only shown during menus)
    windows.menu_win.erase()
    
    # Get border theme once per frame
    border_theme = get_border_theme(game_state)
    
    # Draw header on stdscr row 0
    _draw_header(windows.header_win, game_state)
    windows.header_win.refresh()
    
    # Draw border on frame_win (wraps entire play area)
    draw_window_border(windows.frame_win, border_theme)
    
    # Refresh frame_win (this shows the border)
    windows.frame_win.refresh()
    
    # Note: content_win and input_win are refreshed by their respective renderers/callers
    # We don't refresh them here to allow for efficient partial updates


def _draw_header(win: curses.window, game_state: Optional[object] = None) -> None:
    """Draw the header with location, time, stamina, weather."""
    try:
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
            character = getattr(game_state, "character", None)
            if character:
                # Get base stamina_max with timed modifiers
                base_stamina_max = character.get_stat(
                    "stamina_max",
                    timed_modifiers=getattr(game_state, "timed_modifiers", []),
                    current_day=getattr(game_state, "day", 1),
                )
                # Apply caps (rest, hunger, condition) to get actual maximum
                stamina_max = apply_stamina_cap(game_state, base_stamina_max)
            else:
                stamina_max = 100.0  # Fallback
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
        win.refresh()
    except curses.error:
        pass


# Old print functions removed - use ContentRenderer instead


def draw_menu(
    prompt: str,
    options: List[str],
    selected_index: int,
    windows: UIWindows,
    menu_state: Optional[MenuState] = None,
    existing_lines: Optional[List[str]] = None,
    partial_update: bool = False,
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
        partial_update: If True, only redraw menu content (for navigation). If False, full redraw.
        
    Returns:
        Updated MenuState
    """
    if not options:
        return MenuState()
    
    # Clamp selected_index
    selected_index = max(0, min(selected_index, len(options) - 1))
    
    # Calculate visible rows
    max_y, max_x = windows.content_win.getmaxyx()
    
    # Initialize or update menu state
    if menu_state is None or not partial_update:
        # Full redraw: calculate layout from scratch
        if menu_state is None:
            menu_state = MenuState(selected_index=selected_index)
        else:
            menu_state.selected_index = selected_index
        
        # Calculate space used by existing lines
        scene_lines_used = len(existing_lines) if existing_lines else 0
        menu_state.scene_lines_count = scene_lines_used
        
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
        
        # Calculate menu start position
        if existing_lines is None:
            menu_state.menu_start_y = 0
        else:
            # Limit scene lines to leave room for menu
            max_scene_lines = max(1, max_y - reserved_lines - menu_state.visible_rows - 2)
            scene_lines_to_show = existing_lines[-max_scene_lines:] if len(existing_lines) > max_scene_lines else existing_lines
            menu_state.menu_start_y = len(scene_lines_to_show) + 1  # One blank line after scene
    else:
        # Partial update: only update selection and scrolling
        menu_state.selected_index = selected_index
    
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
    
    # No borders - content_win is inside the frame
    content_start_x = 0
    content_start_y = 0
    content_end_y = max_y - 1
    content_wrap_width = max(1, max_x)
    
    # Draw menu
    try:
        if not partial_update:
            # Full redraw: draw scene content and menu
            if existing_lines is None:
                windows.content_win.erase()
                y = content_start_y
            else:
                # Render existing scene lines (limit to leave room for menu)
                max_scene_lines = max(1, max_y - reserved_lines - menu_state.visible_rows - 2)
                scene_lines_to_show = existing_lines[-max_scene_lines:] if len(existing_lines) > max_scene_lines else existing_lines
                
                y = content_start_y
                content_end_x = max_x - 1  # No borders - content_win is inside frame
                for line in scene_lines_to_show:
                    if y >= max_scene_lines:
                        break
                    try:
                        windows.content_win.move(y, content_start_x)
                        # Clear content area
                        for clear_x in range(content_start_x, content_end_x + 1):
                            try:
                                windows.content_win.addch(y, clear_x, " ")
                            except curses.error:
                                break
                        windows.content_win.move(y, content_start_x)
                        windows.content_win.addstr(line[: content_wrap_width])
                        y += 1
                    except curses.error:
                        break
                
                # Clear the menu area (from menu_start_y to end)
                for clear_y in range(menu_state.menu_start_y, max_y):
                    try:
                        windows.content_win.move(clear_y, content_start_x)
                        # Clear content area
                        for clear_x in range(content_start_x, content_end_x + 1):
                            try:
                                windows.content_win.addch(clear_y, clear_x, " ")
                            except curses.error:
                                break
                    except curses.error:
                        break
                
                y = menu_state.menu_start_y
        else:
            # Partial update: only clear and redraw menu area
            # Clear menu area from menu_start_y to end
            content_end_x = max_x - 1  # No borders - content_win is inside frame
            for clear_y in range(menu_state.menu_start_y, max_y):
                try:
                    windows.content_win.move(clear_y, content_start_x)
                    # Clear content area
                    for clear_x in range(content_start_x, content_end_x + 1):
                        try:
                            windows.content_win.addch(clear_y, clear_x, " ")
                        except curses.error:
                            break
                except curses.error:
                    break
            y = menu_state.menu_start_y
        
        # Draw prompt
        prompt_lines = _wrap_text(prompt, content_wrap_width)
        for line in prompt_lines:
            if y >= content_end_y:
                break
            windows.content_win.addstr(y, content_start_x, line[: content_wrap_width], curses.A_BOLD)
            y += 1
        
        # Draw options
        option_prefix_width = len(f"  {len(options)}. ")
        wrap_width = max(1, content_wrap_width - option_prefix_width)
        
        for idx in range(menu_state.start_index, end_index):
            if y >= content_end_y:  # Leave space for page indicator and border
                break
            
            option = options[idx]
            is_selected = idx == selected_index
            
            # Wrap option text
            wrapped_lines = _wrap_text(option, wrap_width)
            if not wrapped_lines:
                wrapped_lines = [option[:wrap_width]]
            
            # Draw each wrapped line
            for line_idx, line in enumerate(wrapped_lines):
                if y >= content_end_y:
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
                    windows.content_win.addstr(y, content_start_x, full_line[: content_wrap_width], attr)
                    y += 1
                except curses.error:
                    break
        
        # Draw page indicator if needed
        if len(options) > menu_state.visible_rows and y < content_end_y:
            start_display = menu_state.start_index + 1
            end_display = end_index
            indicator = f"Options {start_display}-{end_display} of {len(options)}"
            windows.content_win.addstr(
                content_end_y, content_start_x, indicator[: content_wrap_width], curses.A_DIM
            )
        
        # Use noutrefresh for efficient partial updates
        if partial_update:
            windows.content_win.noutrefresh()
            curses.doupdate()
        else:
            windows.content_win.refresh()
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
        
        # Input window is 1 line, show prompt and input on same line
        prompt_text = f"{prompt} > "
        
        # Truncate if too long
        if len(prompt_text) > max_x - 1:
            prompt_text = prompt_text[: max_x - 1]
        
        windows.input_win.addstr(0, 0, prompt_text)
        
        # Position cursor after prompt
        cursor_x = len(prompt_text)
        windows.input_win.move(0, cursor_x)
        curses.curs_set(1)  # Show cursor for input
        windows.input_win.refresh()
        
        # Get input
        curses.echo()
        try:
            raw = windows.input_win.getstr(0, cursor_x)
        finally:
            curses.noecho()
            curses.curs_set(0)  # Hide cursor again
        
        value = raw.decode("utf-8", errors="ignore").strip()
        return value
    except curses.error:
        return ""


def draw_menu_simple(
    prompt: str,
    options: List[str],
    selected_index: int,
    windows: UIWindows,
) -> int:
    """
    Draw a simple menu in the dedicated menu window.
    
    Args:
        prompt: Menu prompt text (displayed in content_win)
        options: List of option strings
        selected_index: Currently selected option index
        windows: UIWindows object
        
    Returns:
        Selected option index
    """
    if not options:
        return 0
    
    # Clamp selected_index
    selected_index = max(0, min(selected_index, len(options) - 1))
    
    # Show prompt in content window (via ContentRenderer - will be handled by caller)
    # Here we just draw the menu options in menu_win
    
    try:
        windows.menu_win.erase()
        max_y, max_x = windows.menu_win.getmaxyx()
        
        # No borders - menu_win is inside the frame
        start_x = 0
        start_y = 0
        end_y = max_y - 1
        wrap_width = max(1, max_x)
        
        y = start_y
        
        # Draw options (no wrapping - keep it simple)
        for idx, option in enumerate(options):
            if y > end_y:
                break
            
            is_selected = idx == selected_index
            option_text = f"  {idx + 1}. {option}"
            
            # Truncate if too long
            if len(option_text) > wrap_width:
                option_text = option_text[:wrap_width]
            
            # Highlight selected option
            attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
            if is_selected:
                try:
                    attr |= curses.color_pair(1)
                except curses.error:
                    pass
            
            try:
                windows.menu_win.addstr(y, start_x, option_text, attr)
                y += 1
            except curses.error:
                break
        
        windows.menu_win.refresh()
    except curses.error:
        pass
    
    return selected_index


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
    
    max_y, max_x = windows.content_win.getmaxyx()
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

