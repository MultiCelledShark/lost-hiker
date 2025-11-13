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

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "Event":
        return cls(
            event_id=payload["id"],
            text=payload["text"],
            event_type=payload.get("type", "flavor"),
            effects=dict(payload.get("effects", {})),
            checks=dict(payload.get("checks", {})),
        )


class EventPool:
    """Manages selecting events while respecting recent history."""

    def __init__(self, events: List[Event], history_limit: int = 3):
        self.events = events
        self.history_limit = history_limit

    def draw(self, state: GameState) -> Optional[Event]:
        choices = [
            evt for evt in self.events if evt.event_id not in state.recent_events
        ]
        if not choices:
            choices = list(self.events)
        if not choices:
            return None
        return random.choice(choices)

    def apply(self, state: GameState, event: Event) -> str:
        state.recent_events.append(event.event_id)
        state.recent_events = state.recent_events[-self.history_limit :]
        text = [event.text]
        if event.event_type == "forage":
            for item in event.effects.get("inventory_add", []):
                state.inventory.append(item)
                text.append(f"You secure {item}.")
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


def load_event_pool(data_dir: Path, filename: str) -> EventPool:
    """Load an event pool from disk."""
    path = data_dir / filename
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    events = [Event.from_dict(entry) for entry in raw.get("events", [])]
    return EventPool(events)
