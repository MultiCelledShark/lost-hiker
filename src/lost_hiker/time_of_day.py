"""Time-of-day tracking and advancement for Lost Hiker."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState


class TimeOfDay(Enum):
    """Coarse-grained time-of-day slots."""
    
    DAWN = "Dawn"
    DAY = "Day"
    DUSK = "Dusk"
    NIGHT = "Night"
    
    def next(self) -> "TimeOfDay":
        """Get the next time-of-day slot, wrapping around."""
        members = list(TimeOfDay)
        current_index = members.index(self)
        next_index = (current_index + 1) % len(members)
        return members[next_index]
    
    def to_display_name(self) -> str:
        """Get a display-friendly name for this time of day."""
        return self.value


def get_time_of_day(state: "GameState") -> TimeOfDay:
    """
    Get the current time of day from game state.
    
    Args:
        state: Current game state
        
    Returns:
        Current time of day, defaulting to DAY if not set
    """
    if not hasattr(state, "time_of_day") or state.time_of_day is None:
        return TimeOfDay.DAY
    
    # Handle string values (state stores as string for JSON serialization)
    if isinstance(state.time_of_day, str):
        try:
            return TimeOfDay(state.time_of_day)
        except ValueError:
            return TimeOfDay.DAY
    
    # If it's already a TimeOfDay enum, return it
    if isinstance(state.time_of_day, TimeOfDay):
        return state.time_of_day
    
    return TimeOfDay.DAY


def advance_time_of_day(state: "GameState", steps: int = 1) -> None:
    """
    Advance time of day by the specified number of steps.
    
    This advances intra-day time (Dawn -> Day -> Dusk -> Night -> Dawn).
    It does NOT advance the day counter; that's handled separately.
    
    Args:
        state: Current game state
        steps: Number of time slots to advance (default 1)
    """
    current = get_time_of_day(state)
    for _ in range(steps):
        current = current.next()
    # Store as string for JSON serialization
    state.time_of_day = current.value


def is_player_sheltered(state: "GameState") -> bool:
    """
    Check if the player is in a sheltered/enclosed state.
    
    Args:
        state: Current game state
        
    Returns:
        True if player is sheltered, False otherwise
    """
    return getattr(state, "is_sheltered", False)


def is_time_at_least(state: "GameState", target: TimeOfDay) -> bool:
    """
    Check if current time of day is at least the target time.
    
    Time progression: Dawn -> Day -> Dusk -> Night -> Dawn
    
    Args:
        state: Current game state
        target: Target time of day to check against
        
    Returns:
        True if current time is at or past the target, False otherwise
    """
    current = get_time_of_day(state)
    time_order = [TimeOfDay.DAWN, TimeOfDay.DAY, TimeOfDay.DUSK, TimeOfDay.NIGHT]
    
    current_idx = time_order.index(current) if current in time_order else 0
    target_idx = time_order.index(target) if target in time_order else 0
    
    return current_idx >= target_idx


def set_time_of_day(state: "GameState", target: TimeOfDay) -> None:
    """
    Set time of day to a specific value.
    
    Args:
        state: Current game state
        target: Target time of day to set
    """
    state.time_of_day = target.value

