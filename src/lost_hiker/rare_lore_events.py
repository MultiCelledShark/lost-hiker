"""Rare lore events system for Lost Hiker.

This module provides a data-driven system for rare, tag-driven micro-encounters
that react to the player's modular race properties (body_type, flavor_tags,
size, archetype). These events are purely narrative and never change stats,
items, or quest progress.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .state import GameState
from .character import Character
from .time_of_day import get_time_of_day
from .landmarks import LandmarkCatalog


@dataclass
class RareLoreEvent:
    """Definition for a rare lore event."""
    
    event_id: str
    name: str
    text: str
    trigger_chance: float
    max_triggers: int
    prerequisites: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RareLoreEvent":
        """Create a RareLoreEvent from JSON data."""
        return cls(
            event_id=str(data["id"]),
            name=str(data["name"]),
            text=str(data["text"]),
            trigger_chance=float(data.get("trigger_chance", 0.08)),
            max_triggers=int(data.get("max_triggers", 2)),
            prerequisites=dict(data.get("prerequisites", {})),
        )
    
    def check_prerequisites(
        self,
        character: Character,
        state: GameState,
        zone_id: str,
        landmark_catalog: Optional[LandmarkCatalog] = None,
    ) -> bool:
        """Check if all prerequisites for this event are met."""
        prereqs = self.prerequisites
        
        # Check flavor tags (any of the listed tags must be present)
        if "flavor_tags_any" in prereqs:
            required_tags = prereqs["flavor_tags_any"]
            if not isinstance(required_tags, list):
                required_tags = [required_tags]
            if not any(tag in character.flavor_tags for tag in required_tags):
                return False
        
        # Check body type
        if "body_type" in prereqs:
            if character.body_type != prereqs["body_type"]:
                return False
        
        # Check body type (any of)
        if "body_type_any" in prereqs:
            allowed_types = prereqs["body_type_any"]
            if not isinstance(allowed_types, list):
                allowed_types = [allowed_types]
            if character.body_type not in allowed_types:
                return False
        
        # Check size
        if "size" in prereqs:
            if character.size != prereqs["size"]:
                return False
        
        # Check size (any of)
        if "size_any" in prereqs:
            allowed_sizes = prereqs["size_any"]
            if not isinstance(allowed_sizes, list):
                allowed_sizes = [allowed_sizes]
            if character.size not in allowed_sizes:
                return False
        
        # Check archetype
        if "archetype" in prereqs:
            if character.archetype != prereqs["archetype"]:
                return False
        
        # Check archetype (any of)
        if "archetype_any" in prereqs:
            allowed_archetypes = prereqs["archetype_any"]
            if not isinstance(allowed_archetypes, list):
                allowed_archetypes = [allowed_archetypes]
            if character.archetype not in allowed_archetypes:
                return False
        
        # Check zones (must be in one of the listed zones)
        if "zones" in prereqs:
            allowed_zones = prereqs["zones"]
            if not isinstance(allowed_zones, list):
                allowed_zones = [allowed_zones]
            if zone_id not in allowed_zones:
                return False
        
        # Check time of day (any of)
        if "time_of_day_any" in prereqs:
            allowed_times = prereqs["time_of_day_any"]
            if not isinstance(allowed_times, list):
                allowed_times = [allowed_times]
            current_time = get_time_of_day(state)
            if current_time.value not in allowed_times:
                return False
        
        # Check season (any of)
        if "season_any" in prereqs:
            allowed_seasons = prereqs["season_any"]
            if not isinstance(allowed_seasons, list):
                allowed_seasons = [allowed_seasons]
            current_season = state.get_season_name()
            if current_season not in allowed_seasons:
                return False
        
        # Check landmark tags (any of) - requires current landmark or landmark catalog
        if "landmark_tags_any" in prereqs:
            required_tags = prereqs["landmark_tags_any"]
            if not isinstance(required_tags, list):
                required_tags = [required_tags]
            
            # Check if we have a current landmark
            if state.current_landmark and landmark_catalog:
                landmark = landmark_catalog.get(state.current_landmark)
                if landmark:
                    if not any(tag in landmark.tags for tag in required_tags):
                        return False
                else:
                    # No landmark found, but tags were required
                    return False
            else:
                # No landmark context, but tags were required
                return False
        
        return True
    
    def can_trigger(
        self,
        state: GameState,
    ) -> bool:
        """Check if this event can still trigger (hasn't exceeded max triggers)."""
        trigger_count = state.rare_event_triggers.get(self.event_id, 0)
        return trigger_count < self.max_triggers


class RareLoreEventSystem:
    """System for managing and triggering rare lore events."""
    
    def __init__(self, events: List[RareLoreEvent]):
        self.events = events
        self._by_id: Dict[str, RareLoreEvent] = {
            event.event_id: event for event in events
        }
    
    @classmethod
    def load(cls, data_dir: Path, filename: str = "rare_lore_events.json") -> "RareLoreEventSystem":
        """Load rare lore events from a JSON file."""
        path = data_dir / filename
        if not path.exists():
            return cls([])
        
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        
        events = [
            RareLoreEvent.from_dict(entry)
            for entry in data.get("events", [])
        ]
        
        return cls(events)
    
    def check_for_event(
        self,
        state: GameState,
        zone_id: str,
        landmark_catalog: Optional[LandmarkCatalog] = None,
    ) -> Optional[RareLoreEvent]:
        """
        Check if a rare lore event should trigger.
        
        Args:
            state: Current game state
            zone_id: Current zone ID
            landmark_catalog: Optional landmark catalog for landmark-based checks
            
        Returns:
            A rare lore event to trigger, or None if none should trigger
        """
        # Find eligible events
        eligible = []
        for event in self.events:
            if not event.can_trigger(state):
                continue
            
            if not event.check_prerequisites(
                state.character,
                state,
                zone_id,
                landmark_catalog,
            ):
                continue
            
            eligible.append(event)
        
        if not eligible:
            return None
        
        # Roll for each eligible event
        triggered = []
        for event in eligible:
            if random.random() < event.trigger_chance:
                triggered.append(event)
        
        # If multiple events triggered, pick one randomly
        if not triggered:
            return None
        
        return random.choice(triggered)
    
    def trigger_event(
        self,
        event: RareLoreEvent,
        state: GameState,
    ) -> str:
        """
        Trigger a rare lore event and record the trigger.
        
        Args:
            event: The event to trigger
            state: Current game state
            
        Returns:
            The event text to display
        """
        # Record the trigger
        current_count = state.rare_event_triggers.get(event.event_id, 0)
        state.rare_event_triggers[event.event_id] = current_count + 1
        
        # Return the event text
        return event.text

