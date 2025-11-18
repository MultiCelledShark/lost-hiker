"""Character models and stat modifier pipeline for Lost Hiker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

ModifierSpec = Dict[str, Dict[str, float]]


DEFAULT_BASE_STATS: Dict[str, float] = {
    "stamina_max": 4.0,
    "stamina_wake_restore": 1.0,
    "stamina_camp_restore": 3.0,
    "explore_slots": 1.0,
    "camp_meal_cost": 1.0,
    "inventory_slots": 20.0,
}


@dataclass
class TimedModifier:
    """Modifier bundle that expires on a given in-game day."""

    source: str
    modifiers: Sequence[ModifierSpec]
    expires_on_day: Optional[int] = None

    def is_active(self, current_day: int) -> bool:
        if self.expires_on_day is None:
            return True
        return current_day <= self.expires_on_day


@dataclass
class Character:
    """Player character details and stat computations."""

    name: str = ""
    race_id: str = "human"
    tags: List[str] = field(default_factory=list)
    base_stats: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_BASE_STATS)
    )
    race_modifiers: Sequence[ModifierSpec] = field(default_factory=tuple)
    permanent_modifiers: List[ModifierSpec] = field(default_factory=list)

    def active_modifiers(
        self,
        timed_modifiers: Iterable[TimedModifier],
        current_day: int,
    ) -> Iterator[Tuple[str, ModifierSpec]]:
        """Yield modifier specs in the order they should be applied."""
        for spec in self.race_modifiers:
            yield ("race", spec)
        for spec in self.permanent_modifiers:
            yield ("permanent", spec)
        for mod in timed_modifiers:
            if mod.is_active(current_day):
                for spec in mod.modifiers:
                    yield (mod.source, spec)

    def get_stat(
        self,
        key: str,
        *,
        timed_modifiers: Iterable[TimedModifier],
        current_day: int,
    ) -> float:
        """Compute the current value of a derived stat."""
        value = float(self.base_stats.get(key, 0.0))
        for _source, spec in self.active_modifiers(timed_modifiers, current_day):
            if "add" in spec:
                value += spec["add"].get(key, 0.0)
            if "mul" in spec:
                value *= spec["mul"].get(key, 1.0)
        return value

    def to_dict(self) -> Dict[str, object]:
        """Serialize this character to a plain dictionary."""
        return {
            "name": self.name,
            "race_id": self.race_id,
            "tags": list(self.tags),
            "base_stats": dict(self.base_stats),
            "race_modifiers": list(self.race_modifiers),
            "permanent_modifiers": list(self.permanent_modifiers),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Character":
        """Create a character from serialized data."""
        return cls(
            name=str(data.get("name", "")),
            race_id=str(data.get("race_id", "human")),
            tags=list(data.get("tags", [])),
            base_stats=dict(data.get("base_stats", DEFAULT_BASE_STATS)),
            race_modifiers=tuple(data.get("race_modifiers", [])),
            permanent_modifiers=list(data.get("permanent_modifiers", [])),
        )


def build_character_from_race(
    race_id: str,
    race_data: Dict[str, object],
    name: str,
) -> Character:
    """Construct a character using race-driven modifiers."""
    tags = list(race_data.get("tags", []))
    modifiers = tuple(race_data.get("modifiers", []))
    return Character(
        name=name,
        race_id=race_id,
        tags=tags,
        race_modifiers=modifiers,
    )


def sync_character_with_race(
    character: Character, race_data: Dict[str, object]
) -> None:
    """Update an existing character with race-derived details."""
    character.tags = list(race_data.get("tags", []))
    character.race_modifiers = tuple(race_data.get("modifiers", []))
    if not character.base_stats:
        character.base_stats = dict(DEFAULT_BASE_STATS)
    for key, value in DEFAULT_BASE_STATS.items():
        character.base_stats.setdefault(key, value)
