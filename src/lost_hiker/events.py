"""Event loading and execution for the Lost Hiker prototype."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState
from .character import TimedModifier


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

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Event":
        max_depth = payload.get("max_depth")
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
        "edge": {"forage": 1.35, "flavor": 1.2, "encounter": 0.6, "hazard": 0.6, "boon": 1.1},
        "mid": {"forage": 1.0, "flavor": 1.0, "encounter": 1.1, "hazard": 1.05, "boon": 1.0},
        "deep": {"forage": 0.7, "flavor": 0.8, "encounter": 1.35, "hazard": 1.25, "boon": 1.1},
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
        available = [
            evt
            for evt in self.events
            if evt.is_available_at_depth(depth) and evt.event_id not in state.recent_events
        ]
        if not available:
            available = [
                evt
                for evt in self.events
                if evt.is_available_at_depth(depth)
            ]
        if not available:
            available = list(self.events)
        if not available:
            return None
        band = self._band_for_depth(depth)
        band_weights = self.category_weights.get(band, {})
        weights = [
            evt.weight_at_depth(depth, band_weights.get(evt.category, 1.0))
            for evt in available
        ]
        return random.choices(available, weights=weights, k=1)[0]

    def apply(self, state: GameState, event: Event) -> str:
        state.recent_events.append(event.event_id)
        state.recent_events = state.recent_events[-self.history_limit :]
        text = [event.text]
        if event.event_type == "forage":
            for item in event.effects.get("inventory_add", []):
                state.inventory.append(item)
                text.append(f"You secure {item}.")
        if event.event_type == "encounter":
            for item in event.effects.get("inventory_add", []):
                state.inventory.append(item)
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
