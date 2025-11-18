"""Persistence and game state management for Lost Hiker."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .character import Character, TimedModifier
from .seasons import SeasonConfig

CURRENT_VERSION = 5
SEASONS = ("spring", "summer", "fall", "winter")


@dataclass
class GameState:
    """Mutable game state persisted between sessions."""

    schema_version: int = CURRENT_VERSION
    day: int = 1
    current_season: str = "spring"
    day_in_season: int = 1
    # Legacy fields for migration compatibility
    season_index: int = 0
    season_day: int = 0
    stage: str = "wake"
    active_zone: str = "glade"
    character: Character = field(default_factory=Character)
    stamina: float = 0.0
    inventory: List[str] = field(default_factory=list)
    days_without_meal: int = 0
    ate_snack_today: bool = False
    water_drinks_today: int = 0  # Track water drinks per day (max 4)
    rest_type: Optional[str] = None  # "camp", "collapse", or None (defaults to camp)
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
    discovered_landmarks: List[str] = field(default_factory=list)
    current_landmark: Optional[str] = None
    landmark_flags: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    landmark_stability: Dict[str, int] = field(default_factory=dict)  # Path stability per landmark (0-3)
    runestone_states: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    steps_since_forage: int = 0  # Track steps without forage for safety measure
    # Act I quest state: "Mend the Forest's Pulse"
    act1_quest_stage: int = 0  # 0=unaware, 1=discovered, 2=repaired one, 3=completed
    act1_repaired_runestones: int = 0  # Count of fully repaired runestones
    act1_total_runestones: int = 0  # Total fractured runestones in Forest
    act1_forest_stabilized: bool = False  # Flag for Act I completion
    kirin_interest_level: int = 0  # 0=unaware, 1=noticed, 2=watching, 3=ready
    # Kirin state
    kirin_known: bool = False
    kirin_trust_level: int = 0  # 0-3, starts at 1 after intro
    kirin_travel_unlocked: bool = False
    kirin_travel_mode_unlocked: List[str] = field(default_factory=list)  # "vore", "portal", or both
    kirin_last_travel_day: Optional[int] = None  # Track last day Kirin travel was used
    # Wayfinding tea state
    wayfinding_ready: bool = False  # Set to True after drinking wayfinding_tea, cleared after teleport or day end
    # NPC dialogue state
    npc_flags: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # NPC-specific flags (e.g., "forest_hermit_met", "intro_done")
    # Echo state
    echo_present_at_glade: bool = True  # Echo is present at Glade unless story logic removes her
    echo_radio_connection_hint_shown: bool = False  # Flag for HT radio connection hint
    echo_last_pet_day: Optional[int] = None  # Last day Echo was petted (for diminishing returns)
    # Echo vore state (Phase 1: Safe Belly Shelter)
    echo_vore_tension: float = 0.0  # Tension level for vore escalation (increases with hugs/boops, decays over days)
    echo_last_vore_tension_day: Optional[int] = None  # Last day tension was increased (for decay tracking)
    belly_state: Optional[Dict[str, str]] = None  # Current belly shelter state, e.g. {"predator_id": "echo", "mode": "shelter"}
    # Condition/strain track (0-3): 0=fine, 1=bruised/rattled, 2=battered/hurting, 3=close to collapse
    condition: int = 0
    # Time-of-day tracking (Dawn, Day, Dusk, Night)
    time_of_day: Optional[str] = "Day"  # Stored as string for JSON serialization
    # Sheltered/enclosed state flag (for SHELTERED outcomes)
    is_sheltered: bool = False

    def get_season_name(self) -> str:
        """Get the current season name."""
        return self.current_season

    def recalculate_calendar(self, season_config: SeasonConfig) -> None:
        """
        Recalculate calendar fields from current day.

        Args:
            season_config: Season configuration to use for calendar calculations
        """
        self.current_season, self.day_in_season = season_config.get_season_for_day(
            self.day
        )

    def new_day(self, season_config: SeasonConfig) -> None:
        """
        Advance to the next day and update calendar fields.

        Args:
            season_config: Season configuration to use for calendar calculations
        """
        self.stage = "wake"
        self.day += 1
        self.recalculate_calendar(season_config)
        # Reset time of day to Dawn at start of new day
        self.time_of_day = "Dawn"

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
        # Handle calendar fields with migration support
        day = data.get("day", 1)
        current_season = data.get("current_season")
        day_in_season = data.get("day_in_season")
        
        # Migrate from old format if needed
        if current_season is None:
            season_index = data.get("season_index", 0)
            season_day = data.get("season_day", 0)
            # Convert old format to new (approximate, will be recalculated on next new_day)
            current_season = SEASONS[season_index % len(SEASONS)]
            day_in_season = season_day + 1 if season_day >= 0 else 1
        
        if day_in_season is None:
            day_in_season = 1
        
        return cls(
            schema_version=data.get("schema_version", CURRENT_VERSION),
            day=day,
            current_season=str(current_season) if current_season else "spring",
            day_in_season=int(day_in_season) if day_in_season else 1,
            season_index=data.get("season_index", 0),
            season_day=data.get("season_day", 0),
            stage=data.get("stage", "wake"),
            active_zone=data.get("active_zone", "glade"),
            character=character,
            stamina=data.get("stamina", 0.0),
            inventory=list(data.get("inventory", [])),
            days_without_meal=int(data.get("days_without_meal", 0)),
            ate_snack_today=bool(data.get("ate_snack_today", False)),
            water_drinks_today=int(data.get("water_drinks_today", 0)),
            rest_type=data.get("rest_type"),
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
            discovered_landmarks=list(data.get("discovered_landmarks", [])),
            current_landmark=data.get("current_landmark"),
            landmark_flags=dict(data.get("landmark_flags", {})),
            landmark_stability=dict(data.get("landmark_stability", {})),
            runestone_states=dict(data.get("runestone_states", {})),
            steps_since_forage=int(data.get("steps_since_forage", 0)),
            act1_quest_stage=int(data.get("act1_quest_stage", 0)),
            act1_repaired_runestones=int(data.get("act1_repaired_runestones", 0)),
            act1_total_runestones=int(data.get("act1_total_runestones", 0)),
            act1_forest_stabilized=bool(data.get("act1_forest_stabilized", False)),
            kirin_interest_level=int(data.get("kirin_interest_level", 0)),
            kirin_known=bool(data.get("kirin_known", False)),
            kirin_trust_level=int(data.get("kirin_trust_level", 0)),
            kirin_travel_unlocked=bool(data.get("kirin_travel_unlocked", False)),
            kirin_travel_mode_unlocked=list(data.get("kirin_travel_mode_unlocked", [])),
            kirin_last_travel_day=data.get("kirin_last_travel_day"),
            wayfinding_ready=bool(data.get("wayfinding_ready", False)),
            npc_flags=dict(data.get("npc_flags", {})),
            echo_present_at_glade=bool(data.get("echo_present_at_glade", True)),
            echo_radio_connection_hint_shown=bool(data.get("echo_radio_connection_hint_shown", False)),
            echo_last_pet_day=data.get("echo_last_pet_day"),
            echo_vore_tension=float(data.get("echo_vore_tension", 0.0)),
            echo_last_vore_tension_day=data.get("echo_last_vore_tension_day"),
            belly_state=dict(data.get("belly_state", {})) if data.get("belly_state") else None,
            condition=int(data.get("condition", 0)),
            time_of_day=data.get("time_of_day", "Day"),
            is_sheltered=bool(data.get("is_sheltered", False)),
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
        # Add starting items
        state.inventory.append("water_bottle")
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
        # Migrate calendar fields if missing
        if "current_season" not in data:
            day = data.get("day", 1)
            season_index = data.get("season_index", 0)
            season_day = data.get("season_day", 0)
            # Approximate conversion (will be recalculated properly on next new_day)
            data["current_season"] = SEASONS[season_index % len(SEASONS)]
            data["day_in_season"] = season_day + 1 if season_day >= 0 else 1
        data.setdefault("current_season", "spring")
        data.setdefault("day_in_season", 1)
        data.setdefault("discovered_landmarks", [])
        data.setdefault("current_landmark", None)
        data.setdefault("landmark_flags", {})
        # Initialize landmark_stability: if missing, set discovered landmarks to stability 1
        if "landmark_stability" not in data:
            data["landmark_stability"] = {}
            # For old saves, initialize discovered landmarks to stability 1
            for landmark_id in data.get("discovered_landmarks", []):
                data["landmark_stability"][landmark_id] = 1
        data.setdefault("landmark_stability", {})
        data.setdefault("runestone_states", {})
        # Migrate from old meals system to hunger system
        if "days_without_meal" not in data:
            # Old saves had meals count, migrate to safe default
            data["days_without_meal"] = 0
        data.setdefault("days_without_meal", 0)
        data.setdefault("ate_snack_today", False)
        data.setdefault("water_drinks_today", 0)
        data.setdefault("rest_type", None)
        # Ensure water_bottle is in inventory for old saves
        if "water_bottle" not in data.get("inventory", []):
            data.setdefault("inventory", []).append("water_bottle")
        data.setdefault("steps_since_forage", 0)
        # Act I quest state (Phase 2)
        data.setdefault("act1_quest_stage", 0)
        data.setdefault("act1_repaired_runestones", 0)
        data.setdefault("act1_total_runestones", 0)
        data.setdefault("act1_forest_stabilized", False)
        data.setdefault("kirin_interest_level", 0)
        # Kirin state defaults
        data.setdefault("kirin_known", False)
        data.setdefault("kirin_trust_level", 0)
        data.setdefault("kirin_travel_unlocked", False)
        data.setdefault("kirin_travel_mode_unlocked", [])
        data.setdefault("kirin_last_travel_day", None)
        # Wayfinding tea state
        data.setdefault("wayfinding_ready", False)
        # NPC dialogue state
        data.setdefault("npc_flags", {})
        # Echo state defaults
        data.setdefault("echo_present_at_glade", True)
        data.setdefault("echo_radio_connection_hint_shown", False)
        data.setdefault("echo_last_pet_day", None)
        # Echo vore state defaults (Phase 1: Safe Belly Shelter)
        data.setdefault("echo_vore_tension", 0.0)
        data.setdefault("echo_last_vore_tension_day", None)
        data.setdefault("belly_state", None)
        # Condition/strain defaults (0 = fine)
        data.setdefault("condition", 0)
        # Time-of-day defaults
        data.setdefault("time_of_day", "Day")
        data.setdefault("is_sheltered", False)
        return data
