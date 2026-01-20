"""
Event loading and execution for the Lost Hiker prototype.

This module handles random events that occur during forest exploration.
Events include foraging opportunities, flavor text, hazards, and encounters.

## Key Concepts:
- Event: A single occurrence (finding berries, stream crossing, wolf howl)
- EventPool: Collection of events loaded from JSON
- Weighting: Events have base_weight + depth_weight to control frequency
- Categories: "forage", "flavor", "hazard", "encounter"

## Event Selection:
Events are weighted by:
- base_weight: Base probability (higher = more common)
- depth_weight: Change per depth level (+ = more common deeper, - = less common)
- min_depth/max_depth: Depth range where event can occur
- season_weights: Seasonal modifiers (some events only in winter, etc.)

## Event Effects:
Events can modify game state through effects:
- inventory_add: Add items to inventory
- stamina_delta: Change stamina
- rapport_delta: Change NPC relationships
- timed_modifiers: Add temporary buffs/debuffs

## For Content Editors:
Events are defined in data/events_forest.json. Each event has:
- id: Unique identifier (use descriptive names like "berry_bush_patch")
- text: Description shown to player (flavor text, what they see)
- category: "forage", "flavor", "hazard", "encounter"
- effects: What happens (inventory_add, stamina changes, etc.)
- Weighting: base_weight, depth_weight, min_depth, max_depth
- season_weights: Optional seasonal modifiers (1.0 = normal, 2.0 = twice as likely)

## Example Event (from events_forest.json):
{
  "id": "berry_bush_patch",
  "category": "forage",
  "text": "Wild berry bushes cluster along the trail's edge...",
  "effects": { "inventory_add": ["forest_berries"], "inventory_add_count": [[2, 5]] },
  "base_weight": 1.4,
  "depth_weight": -0.12,  (Less common deeper in forest)
  "min_depth": 0,
  "max_depth": 15
}
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState
from .character import TimedModifier
from .seasons import get_seasonal_weight

_races_cache: Optional[Dict[str, Dict[str, object]]] = None


def _load_races_if_needed() -> Optional[Dict[str, Dict[str, object]]]:
    """Load races data if not already cached."""
    global _races_cache
    if _races_cache is not None:
        return _races_cache
    try:
        # Try to find data directory relative to this module
        from . import main
        data_dir, _ = main.resolve_paths()
        races_path = data_dir / "races.json"
        if races_path.exists():
            with races_path.open("r", encoding="utf-8") as handle:
                _races_cache = json.load(handle)
                return _races_cache
    except Exception:
        pass
    return None


def _get_exploration_race_flavor(
    race_id: str,
    event_category: str,
    races: Optional[Dict[str, Dict[str, object]]] = None,
) -> Optional[str]:
    """Get optional race-specific flavor text for exploration/foraging events."""
    races_data = races or _load_races_if_needed()
    if not races_data:
        return None
    
    race_data = races_data.get(race_id, {})
    flavor_tags = race_data.get("flavor_tags", [])
    if not flavor_tags:
        return None
    
    # Handle both old dict format (backwards compatibility) and new list format
    if isinstance(flavor_tags, dict):
        # Old format: dict with sensory_profile and magic_affinity
        sensory = flavor_tags.get("sensory_profile", "")
        magic = flavor_tags.get("magic_affinity", "")
    else:
        # New format: list of tag strings
        # Check for tags that correspond to old sensory/magic profiles
        flavor_tag_list = list(flavor_tags) if flavor_tags else []
        race_tags = list(race_data.get("tags", []))
        
        # Map new tags to old logic
        has_forest_magic = "ambient_magic" in flavor_tag_list and "forestborn" in flavor_tag_list
        has_stone_resonance = "stoneborn" in flavor_tag_list
        has_wind_affinity = "feathered" in flavor_tag_list and "ambient_magic" in flavor_tag_list
        has_sharp_scent = "keen-smell" in race_tags
        
        sensory = ""
        magic = ""
        if has_forest_magic:
            magic = "mild_forest"
        elif has_stone_resonance:
            magic = "stone_resonance"
        elif has_wind_affinity:
            sensory = "wind_affinity"
        elif has_sharp_scent:
            sensory = "sharp_scent"
    
    # Optional flavor variants for foraging events
    if event_category == "forage":
        if sensory == "forest_tuned" or magic == "mild_forest":
            # Elves notice forest hum
            return "You notice a subtle hum in the air—the forest's magic responding to your presence."
        elif sensory == "earth_tuned" or magic == "stone_resonance":
            # Dwarves sense stone warmth
            return "You feel a faint warmth from the nearby stones—the earth remembers your passage."
        elif sensory == "wind_affinity":
            # Gryphons react to wind
            return "A gentle breeze carries new scents to you, shifting with the forest's currents."
        elif sensory == "sharp_scent":
            # Wolf-kin, fox-kin, lizard-folk with sharp scent
            return "Your keen senses pick up subtle details others might miss."
    
    return None


@dataclass
class Event:
    """
    Definition for a random event during exploration.
    
    Events are loaded from JSON files (e.g., events_forest.json) and triggered
    during forest exploration based on weight calculations.
    
    ## Attributes:
    - event_id: Unique identifier (e.g., "berry_bush_patch")
    - text: Flavor text shown to player (what they see/experience)
    - event_type: Legacy field (usually matches category)
    - category: "forage", "flavor", "hazard", "encounter"
    - effects: Dict of effects to apply (inventory_add, stamina_delta, etc.)
    - checks: Dict of required conditions (currently unused)
    - base_weight: Base probability weight (1.0 = average, 2.0 = twice as likely)
    - depth_weight: Weight change per depth level (+ = more common deeper)
    - min_depth: Minimum depth for this event
    - max_depth: Maximum depth (None = no limit)
    - season_weights: Seasonal modifiers {"spring": 1.0, "winter": 0.5, ...}
    - preferred_seasons: Legacy field for seasonal preferences
    
    ## Weight Calculation:
    Final weight = base_weight + (depth * depth_weight) * season_multiplier
    
    ## Example:
    Berry bushes (base=1.4, depth=-0.12) are:
    - Common at depth 0 (weight = 1.4)
    - Less common at depth 5 (weight = 1.4 - 0.6 = 0.8)
    - Rare at depth 10 (weight = 1.4 - 1.2 = 0.2)
    """

    event_id: str  # Unique identifier for this event
    text: str  # Description shown to player
    event_type: str  # Legacy type field (usually matches category)
    effects: Dict[str, object]  # Effects dict (inventory_add, stamina_delta, rapport_delta, etc.)
    checks: Dict[str, float]  # Conditional checks (currently unused, for future conditions)
    base_weight: float  # Base probability weight (1.0 = normal, higher = more common)
    depth_weight: float  # Weight modifier per depth level (+ favors deeper, - favors shallower)
    min_depth: int  # Minimum depth where this event can occur
    max_depth: Optional[int]  # Maximum depth (None = unlimited)
    category: str  # Event category: "forage", "flavor", "hazard", "encounter"
    season_weights: Optional[Dict[str, float]] = None  # Seasonal modifiers per season
    preferred_seasons: Optional[List[str]] = None  # Legacy seasonal preferences

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Event":
        """
        Create Event from JSON dictionary.
        
        Args:
            payload: Event data from JSON file
            
        Returns:
            Event instance
        """
        # Parse optional max_depth
        max_depth = payload.get("max_depth")
        
        # Parse optional season_weights dict
        season_weights = payload.get("season_weights")
        if isinstance(season_weights, dict):
            season_weights = {k: float(v) for k, v in season_weights.items()}
        else:
            season_weights = None
        
        # Parse optional preferred_seasons list (legacy)
        preferred_seasons = payload.get("preferred_seasons")
        if isinstance(preferred_seasons, list):
            preferred_seasons = [str(s) for s in preferred_seasons]
        else:
            preferred_seasons = None
        
        return cls(
            event_id=payload["id"],
            text=payload["text"],
            event_type=payload.get("type", "flavor"),
            effects=dict(payload.get("effects", {})),
            checks=dict(payload.get("checks", {})),
            base_weight=float(payload.get("base_weight", 1.0)),
            depth_weight=float(payload.get("depth_weight", 0.0)),
            min_depth=int(payload.get("min_depth", 0)),
            max_depth=int(max_depth) if max_depth is not None else None,
            category=str(payload.get("category", payload.get("type", "flavor"))),
            season_weights=season_weights,
            preferred_seasons=preferred_seasons,
        )

    def is_available_at_depth(self, depth: int) -> bool:
        """
        Check if event can occur at given depth.
        
        Args:
            depth: Current exploration depth
            
        Returns:
            True if event is available at this depth
        """
        if depth < self.min_depth:
            return False
        if self.max_depth is not None and depth > int(self.max_depth):
            return False
        return True

    def weight_at_depth(self, depth: int, band_multiplier: float = 1.0) -> float:
        """
        Calculate event weight at specific depth.
        
        Weight determines probability of selection. Higher weight = more likely.
        Formula: (base_weight + depth_weight * depth_delta) * band_multiplier
        
        Events past max_depth have weight reduced by 75% (×0.25).
        
        Args:
            depth: Current exploration depth
            band_multiplier: Additional multiplier (from depth band or category weighting)
            
        Returns:
            Final weight (minimum 0.1)
        """
        # Calculate depth delta from minimum depth
        if depth < self.min_depth:
            depth_delta = 0
        else:
            depth_delta = depth - self.min_depth
        
        # Base weight + depth scaling
        weight = (self.base_weight + self.depth_weight * depth_delta) * band_multiplier
        
        # Penalize events past max_depth (reduce to 25% weight)
        if self.max_depth is not None and depth > int(self.max_depth):
            weight *= 0.25
        
        return max(0.1, weight)  # Never drop below 0.1


class EventPool:
    """
    Manages event selection with anti-repetition and depth weighting.
    
    Loads events from JSON and selects them based on:
    - Depth (shallow vs deep forest)
    - Category weights (forage vs flavor vs hazard at different depths)
    - Recent history (prevents same event repeating too often)
    - Seasonal modifiers
    
    ## Depth Bands:
    - edge (0-2): Safer, more forage, fewer hazards
    - mid (3-6): Balanced mix
    - deep (7-14): More hazards, fewer resources
    - depths (15+): Extreme danger zone
    
    ## Category Weights by Depth:
    Category weights change with depth to create atmosphere:
    - "forage": More common near edge, rare in depths
    - "flavor": Atmospheric text, consistent throughout
    - "hazard": Rare at edge, common in depths
    - "encounter": Predator encounters, scale with depth
    """

    # Category weights per depth band
    # Format: {depth_band: {category: weight_multiplier}}
    # Higher multiplier = category is more likely in that band
    DEFAULT_CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
        "edge": {  # Depth 0-2: Forest edge, relatively safe
            "forage": 0.8,  # Moderate foraging (player can also use forage command)
            "flavor": 1.3,  # Common atmospheric flavor
            "encounter": 0.5,  # Reduced: fewer predators in shallow
            "hazard": 0.5,  # Reduced: fewer hazards in shallow
            "boon": 1.2,
        },
        "mid": {
            "forage": 0.7,  # Reduced: less frequent auto-gather, player can use forage command
            "flavor": 1.0,
            "encounter": 1.15,  # Slightly increased: more encounters in mid
            "hazard": 1.1,
            "boon": 1.0,
        },
        "deep": {
            "forage": 0.5,  # Reduced: deep forest is leaner, and less auto-gather
            "flavor": 0.75,
            "encounter": 1.4,  # Increased: more dangerous encounters
            "hazard": 1.3,  # Increased: more hazards
            "boon": 1.15,  # Slightly increased: mystical encounters more common after stabilization
        },
    }

    def __init__(
        self,
        events: List[Event],
        history_limit: int = 3,
        category_weights: Dict[str, Dict[str, float]] | None = None,
    ):
        self.events = events
        self.history_limit = history_limit
        self.category_weights = category_weights or self.DEFAULT_CATEGORY_WEIGHTS

    def draw(self, state: GameState, *, depth: int) -> Optional[Event]:
        # Safety measure: force forage event if player hasn't found food in 7+ steps
        force_forage = state.steps_since_forage >= 7
        
        available = [
            evt
            for evt in self.events
            if evt.is_available_at_depth(depth)
            and evt.event_id not in state.recent_events
        ]
        if not available:
            available = [evt for evt in self.events if evt.is_available_at_depth(depth)]
        if not available:
            available = list(self.events)
        if not available:
            return None
        
        # Filter events that require runestone repair progress
        filtered_available = []
        for evt in available:
            # Check if event requires runestone repair
            requires_repair = evt.checks.get("requires_runestone_repair", 0)
            if requires_repair > 0:
                # Only include if player has repaired at least that many runestones
                if state.act1_repaired_runestones < requires_repair:
                    continue
            filtered_available.append(evt)
        
        # If filtering removed all events, fall back to available (don't filter)
        if filtered_available:
            available = filtered_available
        
        # If forcing forage, filter to only forage events
        if force_forage:
            forage_available = [evt for evt in available if evt.category == "forage"]
            if forage_available:
                available = forage_available
        
        band = self._band_for_depth(depth)
        band_weights = self.category_weights.get(band, {}).copy()
        
        # Apply forest effects based on runestone repairs
        try:
            from .forest_effects import get_event_category_weights
            forest_modifiers = get_event_category_weights(state, band)
            # Merge forest modifiers with base weights
            for category, modifier in forest_modifiers.items():
                if category in band_weights:
                    band_weights[category] = band_weights[category] * modifier
                else:
                    band_weights[category] = modifier
        except ImportError:
            # Forest effects not available, use base weights
            pass
        
        current_season = state.get_season_name()
        weights = []
        for evt in available:
            base_weight = evt.weight_at_depth(depth, band_weights.get(evt.category, 1.0))
            # Apply seasonal weighting if event has seasonal data
            event_dict = {
                "season_weights": evt.season_weights,
                "preferred_seasons": evt.preferred_seasons,
            }
            seasonal_mult = get_seasonal_weight(event_dict, current_season)
            weights.append(base_weight * seasonal_mult)
        return random.choices(available, weights=weights, k=1)[0]

    def apply(self, state: GameState, event: Event) -> str:
        state.recent_events.append(event.event_id)
        state.recent_events = state.recent_events[-self.history_limit :]
        text = [event.text]
        
        # Add optional race-specific flavor for foraging/exploration events
        if event.category in ("forage", "flavor") and event.event_type != "encounter":
            race_flavor = _get_exploration_race_flavor(
                state.character.race_id,
                event.category,
            )
            if race_flavor:
                text.append(race_flavor)
        
        # Track forage events for safety measure
        if event.category == "forage":
            state.steps_since_forage = 0
        else:
            state.steps_since_forage += 1
        
        if event.event_type == "forage":
            items = event.effects.get("inventory_add", [])
            counts = event.effects.get("inventory_add_count", [])
            for i, item in enumerate(items):
                # Get count for this item (default to 1 if not specified)
                if i < len(counts) and isinstance(counts[i], list) and len(counts[i]) == 2:
                    count = random.randint(counts[i][0], counts[i][1])
                else:
                    count = 1
                for _ in range(count):
                    state.inventory.append(item)
                if count > 1:
                    text.append(f"You secure {count} {item}.")
                else:
                    text.append(f"You secure {item}.")
            
            # Add optional tag-based foraging flavor
            try:
                from .flavor_profiles import get_foraging_flavor
                flavor_text = get_foraging_flavor(state.character)
                if flavor_text:
                    text.append(flavor_text)
            except Exception:
                # If flavor fails, continue without it
                pass
        if event.event_type == "encounter":
            items = event.effects.get("inventory_add", [])
            counts = event.effects.get("inventory_add_count", [])
            for i, item in enumerate(items):
                if i < len(counts) and isinstance(counts[i], list) and len(counts[i]) == 2:
                    count = random.randint(counts[i][0], counts[i][1])
                else:
                    count = 1
                for _ in range(count):
                    state.inventory.append(item)
                if count > 1:
                    text.append(f"You secure {count} {item}.")
                else:
                    text.append(f"You secure {item}.")
            for creature, amount in event.effects.get("rapport_inc", {}).items():
                state.rapport[creature] = state.rapport.get(creature, 0) + amount
                text.append(f"Rapport with {creature} shifts by {amount}.")
        if event.event_type == "tame":
            for creature, amount in event.effects.get("rapport_inc", {}).items():
                state.rapport[creature] = state.rapport.get(creature, 0) + amount
                text.append(f"Rapport with {creature} shifts by {amount}.")
        if event.event_type == "tea":
            duration = event.effects.get("duration_days", 1)
            modifiers = event.effects.get("modifiers", [])
            if modifiers:
                state.timed_modifiers.append(
                    TimedModifier(
                        source=event.event_id,
                        modifiers=modifiers,
                        expires_on_day=state.day + duration,
                    )
                )
                text.append("You feel a lingering effect settle in.")
        return "\n".join(text) + "\n"

    @staticmethod
    def _band_for_depth(depth: int) -> str:
        if depth <= 9:
            return "edge"
        if depth <= 24:
            return "mid"
        return "deep"


def load_event_pool(data_dir: Path, filename: str) -> EventPool:
    """Load an event pool from disk."""
    path = data_dir / filename
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    events = [Event.from_dict(entry) for entry in raw.get("events", [])]
    return EventPool(events)
