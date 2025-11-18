"""Calendar and season management for Lost Hiker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .state import GameState


class SeasonConfig:
    """Configuration for season definitions."""

    def __init__(self, seasons: List[Dict[str, object]]) -> None:
        self.seasons = seasons
        self._season_names = [s["name"] for s in seasons]
        self._season_lengths = {s["name"]: int(s["length"]) for s in seasons}
        self._total_days_per_year = sum(self._season_lengths.values())

    def get_season_for_day(self, day: int) -> tuple[str, int]:
        """
        Calculate season and day_in_season for a given day.

        Args:
            day: The current day (1-indexed)

        Returns:
            Tuple of (season_name, day_in_season) where day_in_season is 1-indexed
        """
        # Convert to 0-indexed for calculation
        day_zero = day - 1
        day_in_year = day_zero % self._total_days_per_year

        current_day = 0
        for season in self.seasons:
            season_name = season["name"]
            season_length = int(season["length"])
            if day_in_year < current_day + season_length:
                day_in_season = (day_in_year - current_day) + 1
                return (season_name, day_in_season)
            current_day += season_length

        # Fallback (shouldn't happen)
        return (self._season_names[0], 1)

    def get_season_length(self, season_name: str) -> int:
        """Get the length in days for a given season."""
        return self._season_lengths.get(season_name, 30)


def load_season_config(data_dir: Path) -> SeasonConfig:
    """Load season configuration from JSON file."""
    path = data_dir / "seasons.json"
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return SeasonConfig(data.get("seasons", []))


def get_current_season(state: "GameState", season_config: SeasonConfig) -> str:
    """Get the current season name from game state."""
    return state.get_season_name()


def get_day_in_season(state: "GameState", season_config: SeasonConfig) -> int:
    """Get the current day within the season (1-indexed)."""
    return state.day_in_season


def get_seasonal_weight(
    item_data: Dict[str, object], season: str
) -> float:
    """
    Get seasonal weight modifier for an item/event.

    Args:
        item_data: Data dict that may contain 'season_weights' or 'preferred_seasons'
        season: Current season name (lowercase)

    Returns:
        Weight multiplier (1.0 if no seasonal data, otherwise the configured weight)
    """
    # Check for explicit season_weights dict
    season_weights = item_data.get("season_weights")
    if isinstance(season_weights, dict):
        weight = season_weights.get(season, 1.0)
        if isinstance(weight, (int, float)):
            return float(weight)

    # Check for preferred_seasons list (boosts to 1.2 if in list, otherwise 1.0)
    preferred_seasons = item_data.get("preferred_seasons")
    if isinstance(preferred_seasons, list):
        if season in [s.lower() for s in preferred_seasons]:
            return 1.2
        return 1.0

    # No seasonal data, neutral weight
    return 1.0

