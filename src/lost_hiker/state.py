"""Persistence and game state management for Lost Hiker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .character import Character, TimedModifier

CURRENT_VERSION = 3
SEASONS = ("spring", "summer", "fall", "winter")


@dataclass
class GameState:
    """Mutable game state persisted between sessions."""

    schema_version: int = CURRENT_VERSION
    day: int = 1
    season_index: int = 0
    season_day: int = 0
    stage: str = "wake"
    active_zone: str = "glade"
    character: Character = field(default_factory=Character)
    stamina: float = 0.0
    inventory: List[str] = field(default_factory=list)
    meals: int = 5
    rapport: Dict[str, int] = field(default_factory=dict)
    timed_modifiers: List[TimedModifier] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    zone_steps: Dict[str, int] = field(default_factory=dict)
    zone_depths: Dict[str, int] = field(default_factory=dict)
    vore_enabled: bool = False
    player_as_pred_enabled: bool = False
    radio_version: int = 1
    pending_radio_upgrade: bool = False
    pending_radio_return_day: Optional[int] = None
    pending_brews: List[str] = field(default_factory=list)
    pending_stamina_floor: float = 0.0

    def current_season(self) -> str:
        return SEASONS[self.season_index % len(SEASONS)]

    def new_day(self) -> None:
        self.stage = "wake"
        self.day += 1
        self.season_day = (self.season_day + 1) % 14
        if self.season_day == 0:
            self.season_index = (self.season_index + 1) % len(SEASONS)

    def prune_expired_effects(self) -> None:
        self.timed_modifiers = [
            mod for mod in self.timed_modifiers if mod.is_active(self.day)
        ]

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["character"] = self.character.to_dict()
        data["timed_modifiers"] = [
            {
                "source": mod.source,
                "modifiers": list(mod.modifiers),
                "expires_on_day": mod.expires_on_day,
            }
            for mod in self.timed_modifiers
        ]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "GameState":
        character = Character.from_dict(data.get("character", {}))
        timed_mods = [
            TimedModifier(
                source=entry.get("source", "unknown"),
                modifiers=entry.get("modifiers", []),
                expires_on_day=entry.get("expires_on_day"),
            )
            for entry in data.get("timed_modifiers", [])
        ]
        return cls(
            schema_version=data.get("schema_version", CURRENT_VERSION),
            day=data.get("day", 1),
            season_index=data.get("season_index", 0),
            season_day=data.get("season_day", 0),
            stage=data.get("stage", "wake"),
            active_zone=data.get("active_zone", "glade"),
            character=character,
            stamina=data.get("stamina", 0.0),
            inventory=list(data.get("inventory", [])),
            meals=data.get("meals", 5),
            rapport=dict(data.get("rapport", {})),
            timed_modifiers=timed_mods,
            recent_events=list(data.get("recent_events", [])),
            zone_steps=dict(data.get("zone_steps", {})),
            zone_depths=dict(data.get("zone_depths", {})),
            vore_enabled=bool(data.get("vore_enabled", False)),
            player_as_pred_enabled=bool(data.get("player_as_pred_enabled", False)),
            radio_version=int(data.get("radio_version", 1)),
            pending_radio_upgrade=bool(data.get("pending_radio_upgrade", False)),
            pending_radio_return_day=data.get("pending_radio_return_day"),
            pending_brews=list(data.get("pending_brews", [])),
            pending_stamina_floor=float(data.get("pending_stamina_floor", 0.0)),
        )


class GameStateRepository:
    """Load and save the game state with migrations."""

    def __init__(self, save_path: Path):
        self.save_path = save_path
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[GameState]:
        if not self.save_path.exists():
            return None
        with self.save_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        migrated = self._migrate(raw)
        return GameState.from_dict(migrated)

    def save(self, state: GameState) -> None:
        state.schema_version = CURRENT_VERSION
        payload = state.to_dict()
        with self.save_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def create_new(self, character: Character) -> GameState:
        state = GameState(character=character)
        state.stamina = state.character.get_stat(
            "stamina_max",
            timed_modifiers=state.timed_modifiers,
            current_day=state.day,
        )
        state.stage = "intro"
        state.active_zone = "charred_tree_interior"
        state.zone_depths["charred_tree_interior"] = 0
        return state

    def _migrate(self, data: Dict[str, object]) -> Dict[str, object]:
        schema_version = data.get("schema_version", 1)
        if "character" not in data:
            data["character"] = {
                "name": data.get("name", "Wanderer"),
                "race_id": data.get("race_id", "human"),
            }
        character = data["character"]
        if not character.get("race_id"):
            character["race_id"] = "human"
        data["schema_version"] = CURRENT_VERSION
        if schema_version < 2:
            data.setdefault("recent_events", [])
        data.setdefault("active_zone", "glade")
        data.setdefault("zone_steps", {})
        data.setdefault("zone_depths", {})
        data.setdefault("vore_enabled", False)
        data.setdefault("player_as_pred_enabled", False)
        data.setdefault("radio_version", 1)
        data.setdefault("pending_radio_upgrade", False)
        data.setdefault("pending_radio_return_day", None)
        data.setdefault("pending_brews", [])
        data.setdefault("pending_stamina_floor", 0.0)
        return data
