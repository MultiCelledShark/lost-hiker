"""Event loading and execution for the Lost Hiker prototype."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState
from .character import TimedModifier
from .seasons import get_seasonal_weight


@dataclass
class Event:
    """Serializable event definition."""

    event_id: str
    text: str
    event_type: str
    effects: Dict[str, object]
    checks: Dict[str, float]
    base_weight: float
    depth_weight: float
    min_depth: int
    max_depth: Optional[int]
    category: str
    season_weights: Optional[Dict[str, float]] = None
    preferred_seasons: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Event":
        max_depth = payload.get("max_depth")
        season_weights = payload.get("season_weights")
        if isinstance(season_weights, dict):
            season_weights = {k: float(v) for k, v in season_weights.items()}
        else:
            season_weights = None
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
        if depth < self.min_depth:
            return False
        if self.max_depth is not None and depth > int(self.max_depth):
            return False
        return True

    def weight_at_depth(self, depth: int, band_multiplier: float = 1.0) -> float:
        if depth < self.min_depth:
            depth_delta = 0
        else:
            depth_delta = depth - self.min_depth
        weight = (self.base_weight + self.depth_weight * depth_delta) * band_multiplier
        if self.max_depth is not None and depth > int(self.max_depth):
            weight *= 0.25
        return max(0.1, weight)


class EventPool:
    """Manages selecting events while respecting recent history."""

    DEFAULT_CATEGORY_WEIGHTS: Dict[str, Dict[str, float]] = {
        "edge": {
            "forage": 1.35,
            "flavor": 1.2,
            "encounter": 0.6,
            "hazard": 0.6,
            "boon": 1.1,
        },
        "mid": {
            "forage": 1.0,
            "flavor": 1.0,
            "encounter": 1.1,
            "hazard": 1.05,
            "boon": 1.0,
        },
        "deep": {
            "forage": 0.7,
            "flavor": 0.8,
            "encounter": 1.35,
            "hazard": 1.25,
            "boon": 1.1,
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
