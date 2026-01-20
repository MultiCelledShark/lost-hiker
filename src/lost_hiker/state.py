"""
Persistence and game state management for Lost Hiker.

This module defines the game's core data structures and save/load functionality.
It handles all persistent state including character progress, inventory, quest flags,
and world state.

## Key Concepts:
- GameState: The complete game state (saved between sessions)
- GameStateRepository: Handles loading/saving with automatic migrations
- Schema versioning: Ensures old saves work with new game versions

## For Content Editors:
Most story/dialogue content is stored in JSON files, but quest flags and
progression state lives here. When adding new quests, you'll need to add
corresponding state fields to GameState.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from .character import Character, TimedModifier
from .seasons import SeasonConfig

# Save file version - increment when making breaking changes to GameState
CURRENT_VERSION = 5

# Season names used for calendar calculations
SEASONS = ("spring", "summer", "fall", "winter")


@dataclass
class GameState:
    """
    Complete game state persisted between sessions.
    
    This class holds ALL mutable game data. Every field here gets saved to disk
    when the player saves, and restored when they load.
    
    ## Field Categories:
    
    ### Time & Calendar
    - day: Current in-game day number (starts at 1)
    - current_season: "spring", "summer", "fall", or "winter"
    - day_in_season: Day within current season (1-14)
    - time_of_day: "Dawn", "Day", "Dusk", or "Night"
    - stage: Current game phase ("intro", "wake", "explore", "camp", "game_over")
    
    ### Character & Stats
    - character: Player character data (race, name, stats, modifiers)
    - stamina: Current stamina (max determined by character stats)
    - condition: Physical strain level (0=fine, 1=bruised, 2=battered, 3=near collapse)
    - days_without_meal: Hunger tracker (game over at 7 days)
    - ate_snack_today: Whether player ate a snack today
    - water_drinks_today: Number of water bottle refills today (max 4)
    
    ### Inventory & Items
    - inventory: List of item IDs (strings like "forest_berries", "primitive_mortar")
    - pending_brews: Teas/potions brewing overnight at camp
    
    ### Location & Exploration
    - active_zone: Current zone ID ("glade", "forest", "charred_tree_interior", etc.)
    - zone_steps: Steps taken in each zone (for buffer reduction)
    - zone_depths: Current depth in each explorable zone
    - discovered_landmarks: List of landmark IDs player has found
    - current_landmark: Landmark ID player is currently at (if any)
    - landmark_flags: Per-landmark flags for events/interactions
    - landmark_stability: Path stability to each landmark (0-3, higher = easier to reach)
    
    ### NPCs & Relationships
    - rapport: Dict of NPC ID -> rapport points (positive or negative)
    - npc_state: Centralized NPC quest/interaction flags
    - npc_flags: Legacy NPC flags (being phased out)
    
    ### Echo (Serpent Companion) State
    - echo_present_at_glade: Whether Echo is currently at the Glade
    - echo_radio_connection_hint_shown: Tutorial flag for radio interaction
    - echo_last_pet_day: Last day player petted Echo (for cooldown)
    - echo_last_*_variant: Rotation tracking for interaction flavor text
    - echo_vore_tension: Escalation tracker for belly shelter mechanic (if vore enabled)
    - echo_last_vore_tension_day: Last day tension increased (for decay)
    
    ### Radio & Communication
    - radio_version: 1=fragmentary, 2=coherent after Echo attunement
    - pending_radio_upgrade: Flag for pending overnight radio upgrade
    - pending_radio_return_day: Day when radio will be returned after Echo eats it
    
    ### Quest State - Act I: "Breath of the Forest"
    - forest_act1: Centralized Act I quest data (preferred)
    - act1_quest_stage: Legacy quest stage (0-3)
    - act1_repaired_runestones: Count of repaired runestones
    - act1_total_runestones: Total runestones in forest (usually 3)
    - act1_forest_stabilized: Whether Act I is complete
    - runestone_states: Per-runestone repair flags
    
    ### Kirin (Mystical Guide) State
    - kirin_known: Whether player has met the Kirin
    - kirin_trust_level: Trust level (0-3, unlocks travel at higher levels)
    - kirin_travel_unlocked: Whether Kirin fast travel is available
    - kirin_travel_mode_unlocked: List of travel modes ("vore", "portal")
    - kirin_last_travel_day: Last day Kirin travel was used
    - kirin_interest_level: Kirin's attention level (0=unaware to 3=ready to meet)
    
    ### Special Mechanics
    - vore_enabled: Player-chosen toggle for belly shelter/interaction scenes
    - player_as_pred_enabled: Player-chosen toggle for predator role
    - belly_state: Active belly interaction data (creature, mode, turns, etc.)
    - wayfinding_ready: Whether wayfinding tea effect is active
    - is_sheltered: Whether player is in sheltered location
    
    ### Persistence & Tracking
    - schema_version: Save file version for migrations
    - timed_modifiers: Temporary stat buffs/debuffs with expiration
    - recent_events: Event IDs recently triggered (for anti-repeat)
    - steps_since_forage: Safety counter to ensure player gets food
    - rare_event_triggers: Count of rare event triggers (for rarity enforcement)
    - hollow_turns: Turns spent in Charred Hollow (triggers Echo rescue)
    - rest_type: Type of last rest ("camp", "collapse", or None)
    - flags: Generic feature flags (town_path_known, etc.)
    - lost_bag_predator_id: ID of creature that took player's bag
    - lost_bag_den_location_id: Location to recover lost bag
    
    ## For Content Editors:
    When adding new quests or mechanics:
    1. Add state fields here
    2. Add defaults in __post_init__ or field(default=...)
    3. Add migration logic in GameStateRepository._migrate()
    4. Document what triggers changes to these fields
    """

    # ============================================================================
    # PERSISTENCE METADATA
    # ============================================================================
    
    schema_version: int = CURRENT_VERSION
    
    # Legacy fields for migration compatibility (deprecated, use current_season/day_in_season)
    season_index: int = 0
    season_day: int = 0
    
    # ============================================================================
    # TIME & CALENDAR
    # ============================================================================
    
    day: int = 1  # Current in-game day (1, 2, 3, ...)
    current_season: str = "spring"  # "spring", "summer", "fall", "winter"
    day_in_season: int = 1  # Day within current season (1-14 typically)
    time_of_day: Optional[str] = "Day"  # "Dawn", "Day", "Dusk", "Night"
    stage: str = "wake"  # Game phase: "intro", "wake", "explore", "camp", "game_over"
    
    # ============================================================================
    # LOCATION & EXPLORATION
    # ============================================================================
    
    active_zone: str = "glade"  # Current zone ID (see zones in design doc)
    zone_steps: Dict[str, int] = field(default_factory=dict)  # Steps taken per zone (reduces travel buffer)
    zone_depths: Dict[str, int] = field(default_factory=dict)  # Current depth in explorable zones
    
    # Landmark discovery and navigation
    discovered_landmarks: List[str] = field(default_factory=list)  # IDs of discovered landmarks
    current_landmark: Optional[str] = None  # ID of landmark player is at (if any)
    landmark_flags: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # Per-landmark event flags
    landmark_stability: Dict[str, int] = field(default_factory=dict)  # Path stability (0-3, higher=easier to reach)
    
    steps_since_forage: int = 0  # Safety counter ensures player gets food opportunities
    
    # ============================================================================
    # CHARACTER & SURVIVAL
    # ============================================================================
    
    character: Character = field(default_factory=Character)  # Player character (race, stats, modifiers)
    stamina: float = 0.0  # Current stamina (0 to stamina_max)
    condition: int = 0  # Physical strain (0=fine, 1=bruised, 2=battered, 3=near collapse)
    
    # Hunger system (replaces old meals system)
    days_without_meal: int = 0  # Days since last meal (game over at 7)
    ate_snack_today: bool = False  # Whether player ate a snack today (for full meal tracking)
    water_drinks_today: int = 0  # Water refills today (max 4 per day)
    rest_type: Optional[str] = None  # Last rest type: "camp", "collapse", or None
    
    # ============================================================================
    # INVENTORY & CRAFTING
    # ============================================================================
    
    inventory: List[str] = field(default_factory=list)  # Item IDs (e.g., "forest_berries", "primitive_mortar")
    pending_brews: List[str] = field(default_factory=list)  # Teas brewing overnight
    pending_stamina_floor: float = 0.0  # Minimum stamina after overnight effects
    
    # ============================================================================
    # NPCS & RELATIONSHIPS
    # ============================================================================
    
    rapport: Dict[str, int] = field(default_factory=dict)  # NPC ID -> rapport points (can be negative)
    npc_state: Dict[str, Any] = field(default_factory=dict)  # Centralized NPC quest/interaction flags
    npc_flags: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # Legacy per-NPC flags (deprecated)
    
    # ============================================================================
    # ECHO (SERPENT COMPANION) STATE
    # ============================================================================
    
    echo_present_at_glade: bool = True  # Whether Echo is at Glade (story can move her)
    echo_radio_connection_hint_shown: bool = False  # Tutorial flag for radio ping
    echo_last_pet_day: Optional[int] = None  # Last day petted (for diminishing returns)
    
    # Interaction flavor rotation (cycles through different descriptions)
    echo_last_pet_variant: int = 0
    echo_last_boop_variant: int = 0
    echo_last_hug_variant: int = 0
    
    # Vore/belly shelter mechanics (if enabled)
    echo_vore_tension: float = 0.0  # Escalation toward belly shelter offer (0.0-1.0+)
    echo_last_vore_tension_day: Optional[int] = None  # For tension decay tracking
    
    # ============================================================================
    # RADIO & COMMUNICATION
    # ============================================================================
    
    radio_version: int = 1  # 1=fragmentary broadcasts, 2=coherent after Echo attunes it
    pending_radio_upgrade: bool = False  # Whether Echo is attuning radio overnight
    pending_radio_return_day: Optional[int] = None  # Day Echo returns attuned radio
    
    # ============================================================================
    # ACT I QUEST: "BREATH OF THE FOREST"
    # Repair fractured runestones to stabilize the forest's ley-lines
    # ============================================================================
    
    # New centralized structure (preferred)
    forest_act1: Optional[Dict[str, Any]] = None  # Contains: runestones_total, runestones_repaired, first_repair_done, completed
    
    # Legacy fields (kept for backward compatibility with old saves)
    act1_quest_stage: int = 0  # 0=unaware, 1=discovered, 2=repaired one, 3=completed
    act1_repaired_runestones: int = 0  # Count of repaired runestones
    act1_total_runestones: int = 0  # Total fractured runestones in forest (usually 3)
    act1_forest_stabilized: bool = False  # Whether Act I is complete
    
    runestone_states: Dict[str, Dict[str, bool]] = field(default_factory=dict)  # Per-runestone repair flags
    
    # ============================================================================
    # KIRIN (MYSTICAL GUIDE) STATE
    # The Kirin is a mystical creature that appears when player proves worthy
    # ============================================================================
    
    kirin_known: bool = False  # Whether player has met the Kirin
    kirin_trust_level: int = 0  # 0-3, increases through positive interactions
    kirin_travel_unlocked: bool = False  # Whether fast travel is available
    kirin_travel_mode_unlocked: List[str] = field(default_factory=list)  # Available modes: "vore", "portal"
    kirin_last_travel_day: Optional[int] = None  # Last day Kirin travel was used (for cooldown)
    kirin_interest_level: int = 0  # 0=unaware, 1=noticed, 2=watching, 3=ready to meet
    
    # ============================================================================
    # SPECIAL MECHANICS & PLAYER PREFERENCES
    # ============================================================================
    
    # Player-chosen content toggles (set during character creation)
    vore_enabled: bool = False  # Enable belly shelter/interaction scenes
    player_as_pred_enabled: bool = False  # Enable player-as-predator scenes
    
    # Belly interaction state (if vore_enabled)
    belly_state: Optional[Dict[str, Any]] = None  # Active interaction: {active, creature_id, mode, depth_before, landmark_before, turns_inside}
    
    # Wayfinding tea teleportation
    wayfinding_ready: bool = False  # Active wayfinding tea effect (cleared after use or day end)
    
    # Environmental state
    is_sheltered: bool = False  # Whether player is in sheltered location (for weather effects)
    
    # ============================================================================
    # BUFFS, MODIFIERS, & TRACKING
    # ============================================================================
    
    timed_modifiers: List[TimedModifier] = field(default_factory=list)  # Temporary stat modifiers (teas, etc.)
    recent_events: List[str] = field(default_factory=list)  # Recently triggered events (anti-repeat)
    rare_event_triggers: Dict[str, int] = field(default_factory=dict)  # Count per rare event (enforces rarity)
    
    # ============================================================================
    # SPECIAL TRACKING
    # ============================================================================
    
    hollow_turns: int = 0  # Turns spent in Charred Hollow (triggers Echo rescue)
    
    # Lost bag recovery (when predator takes player's backpack)
    lost_bag_predator_id: Optional[str] = None  # Creature that took the bag
    lost_bag_den_location_id: Optional[str] = None  # Where to recover it
    
    # Generic feature flags
    flags: Dict[str, bool] = field(default_factory=dict)  # General purpose flags (town_path_known, etc.)

    def get_season_name(self) -> str:
        """
        Get the current season name.
        
        Returns:
            Season name: "spring", "summer", "fall", or "winter"
        """
        return self.current_season

    def recalculate_calendar(self, season_config: SeasonConfig) -> None:
        """
        Recalculate season and day-in-season from absolute day number.
        
        This ensures calendar fields stay in sync when loading old saves or
        after time advances. Called automatically during load/migration.
        
        Args:
            season_config: Season configuration defining season lengths
        """
        self.current_season, self.day_in_season = season_config.get_season_for_day(
            self.day
        )

    def new_day(self, season_config: SeasonConfig) -> None:
        """
        Advance to the next day and reset daily state.
        
        Called at the end of each day (camp/collapse). Increments day counter,
        updates calendar, resets time to Dawn, and transitions to wake phase.
        
        Args:
            season_config: Season configuration for calendar calculations
        """
        self.stage = "wake"
        self.day += 1
        self.recalculate_calendar(season_config)
        # Reset time of day to Dawn at start of new day
        self.time_of_day = "Dawn"

    def prune_expired_effects(self) -> None:
        """
        Remove expired timed modifiers (buffs/debuffs).
        
        Removes any TimedModifier that has expired based on current day.
        This prevents old tea buffs, curses, etc. from lingering forever.
        Called periodically during gameplay.
        """
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
            forest_act1=dict(data.get("forest_act1", {})) if data.get("forest_act1") else None,
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
            npc_state=dict(data.get("npc_state", {})),
            echo_present_at_glade=bool(data.get("echo_present_at_glade", True)),
            echo_radio_connection_hint_shown=bool(data.get("echo_radio_connection_hint_shown", False)),
            echo_last_pet_day=data.get("echo_last_pet_day"),
            echo_last_pet_variant=int(data.get("echo_last_pet_variant", 0)),
            echo_last_boop_variant=int(data.get("echo_last_boop_variant", 0)),
            echo_last_hug_variant=int(data.get("echo_last_hug_variant", 0)),
            echo_vore_tension=float(data.get("echo_vore_tension", 0.0)),
            echo_last_vore_tension_day=data.get("echo_last_vore_tension_day"),
            belly_state=dict(data.get("belly_state", {})) if data.get("belly_state") else None,
            condition=int(data.get("condition", 0)),
            time_of_day=data.get("time_of_day", "Day"),
            is_sheltered=bool(data.get("is_sheltered", False)),
            flags=dict(data.get("flags", {})),
            rare_event_triggers=dict(data.get("rare_event_triggers", {})),
            hollow_turns=int(data.get("hollow_turns", 0)),
        )


class GameStateRepository:
    """
    Load and save the game state with automatic migrations.
    
    This class handles all save/load operations and ensures old save files
    work with new game versions through automatic migration.
    
    ## Migration System:
    When game structure changes, old saves are automatically upgraded using
    the _migrate() method. This preserves player progress across updates.
    
    ## For Developers:
    When adding new GameState fields:
    1. Add field to GameState with sensible default
    2. Add migration logic in _migrate() to set default for old saves
    3. Increment CURRENT_VERSION if breaking compatibility
    
    ## Save File Location:
    Saves are stored at: <project_root>/save/save.json
    """

    def __init__(self, save_path: Path):
        """
        Initialize repository with save file path.
        
        Args:
            save_path: Path to save.json file (will be created if missing)
        """
        self.save_path = save_path
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[GameState]:
        """
        Load game state from disk, applying migrations if needed.
        
        Returns:
            GameState if save exists, None if no save file found
        """
        if not self.save_path.exists():
            return None
        with self.save_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        migrated = self._migrate(raw)
        return GameState.from_dict(migrated)

    def save(self, state: GameState) -> None:
        """
        Save game state to disk as JSON.
        
        Args:
            state: Current game state to persist
        """
        state.schema_version = CURRENT_VERSION
        payload = state.to_dict()
        with self.save_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def create_new(self, character: Character) -> GameState:
        """
        Create a new game state for a fresh playthrough.
        
        Sets up initial state: player wakes in Charred Hollow with starting
        inventory (water bottle + 5 days of food). Stamina is set to max,
        and intro sequence begins.
        
        Args:
            character: Newly created character (from character creation)
            
        Returns:
            Fresh GameState ready for intro sequence
        """
        state = GameState(character=character)
        
        # Set stamina to max (player starts well-rested)
        state.stamina = state.character.get_stat(
            "stamina_max",
            timed_modifiers=state.timed_modifiers,
            current_day=state.day,
        )
        
        # Start in intro sequence (player wakes in Charred Hollow after portal accident)
        state.stage = "intro"
        state.active_zone = "charred_tree_interior"
        state.zone_depths["charred_tree_interior"] = 0
        state.time_of_day = "Dawn"
        state.hollow_turns = 0  # Tracks turns in hollow (triggers Echo rescue)
        
        # Starting inventory: water bottle + 5 days of food
        state.inventory.append("water_bottle")
        
        # Add 5 random snacks for survival (mix of forest berries, nuts, dried berries)
        import random
        for _ in range(5):
            state.inventory.append(random.choice(["forest_berries", "trail_nuts", "dried_berries"]))
        
        return state

    def _migrate(self, data: Dict[str, object]) -> Dict[str, object]:
        """
        Migrate old save files to current version.
        
        This method updates old save files to work with the current game version.
        It adds missing fields with sensible defaults and converts deprecated
        fields to new formats.
        
        ## Migration Strategy:
        - Always preserve player progress (never delete important data)
        - Add new fields with safe defaults
        - Convert old formats to new ones
        - Keep deprecated fields if they're used for backward compat
        
        ## For Developers:
        When adding new GameState fields, add default values here so old saves
        don't break. Use data.setdefault("new_field", default_value).
        
        Args:
            data: Raw save data dictionary
            
        Returns:
            Migrated data dictionary ready for GameState.from_dict()
        """
        schema_version = data.get("schema_version", 1)
        if "character" not in data:
            data["character"] = {
                "name": data.get("name", "Wanderer"),
                "race_id": data.get("race_id", "human"),
            }
        character = data["character"]
        if not character.get("race_id"):
            character["race_id"] = "human"
        
        # Migrate character fields for modular race system
        # If missing, set defaults and try to load from races.json if available
        if "body_type" not in character:
            character["body_type"] = "humanoid"
        if "size" not in character:
            character["size"] = "medium"
        if "archetype" not in character:
            character["archetype"] = "forest_creature"
        if "flavor_tags" not in character:
            # Try to load default flavor_tags from races.json
            default_flavor_tags = []
            try:
                from . import main
                data_dir, _ = main.resolve_paths()
                races = main.load_races(data_dir)
                race_id = character.get("race_id", "human")
                if race_id in races:
                    race_data = races[race_id]
                    default_flavor_tags = list(race_data.get("flavor_tags", []))
            except Exception:
                pass
            character["flavor_tags"] = default_flavor_tags
        
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
        # Initialize forest_act1 if missing (will be populated by init_forest_act1_state)
        if "forest_act1" not in data:
            data["forest_act1"] = None
        data.setdefault("act1_quest_stage", 0)
        data.setdefault("act1_repaired_runestones", 0)
        data.setdefault("act1_total_runestones", 0)
        data.setdefault("act1_forest_stabilized", False)
        # Ensure forest_act1 is initialized for old saves
        # This will be properly initialized when the game loads via init_forest_act1_state
        # But we ensure the structure exists in the save data
        if data.get("forest_act1") is None:
            # Initialize with defaults based on existing legacy fields
            repaired = data.get("act1_repaired_runestones", 0)
            total = data.get("act1_total_runestones", 0)
            if total == 0:
                total = 3  # Default based on runestones_forest.json
            data["forest_act1"] = {
                "runestones_total": total,
                "runestones_repaired": repaired,
                "first_repair_done": repaired > 0,
                "completed": data.get("act1_forest_stabilized", False)
            }
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
        # NPC state (centralized flags for Wave 1 NPCs)
        if "npc_state" not in data:
            data["npc_state"] = {}
        # Initialize safe defaults for old saves
        npc_state = data.get("npc_state", {})
        npc_state.setdefault("hermit_met", False)
        npc_state.setdefault("hermit_explained_runestones", False)
        npc_state.setdefault("naiad_met", False)
        npc_state.setdefault("naiad_share_recipe", False)
        npc_state.setdefault("druid_met", False)
        npc_state.setdefault("druid_shroomling_quest_started", False)
        npc_state.setdefault("druid_shroomling_quest_completed", False)
        npc_state.setdefault("fisher_met", False)
        npc_state.setdefault("fisher_mussel_quest_started", False)
        npc_state.setdefault("fisher_mussel_quest_completed", False)
        npc_state.setdefault("astrin_status", "missing")  # "missing", "found", "at_glade"
        npc_state.setdefault("astrin_tea_unlocked", False)
        # Micro-quest flags
        npc_state.setdefault("echo_checkin_last_day", None)
        npc_state.setdefault("echo_favor_last_day", None)
        npc_state.setdefault("hermit_trinket_quest_started", False)
        npc_state.setdefault("hermit_trinket_quest_completed", False)
        npc_state.setdefault("hermit_sketch_given", False)
        npc_state.setdefault("naiad_blessing_quest_started", False)
        npc_state.setdefault("naiad_blessing_quest_completed", False)
        npc_state.setdefault("naiad_blessing_last_week", None)
        npc_state.setdefault("druid_night_ritual_available", False)
        npc_state.setdefault("fisher_mussel_mastery_learned", False)
        npc_state.setdefault("fisher_mussel_mastery_expires_day", None)
        npc_state.setdefault("fisher_trap_quest_started", False)
        npc_state.setdefault("fisher_trap_quest_completed", False)
        npc_state.setdefault("astrin_herb_id_last_day", None)
        npc_state.setdefault("astrin_request_quest_started", False)
        npc_state.setdefault("astrin_request_quest_completed", False)
        npc_state.setdefault("blue_fireflies_seen", False)
        data["npc_state"] = npc_state
        # Echo state defaults
        data.setdefault("echo_present_at_glade", True)
        data.setdefault("echo_radio_connection_hint_shown", False)
        data.setdefault("echo_last_pet_day", None)
        # Echo interaction variant tracking defaults
        data.setdefault("echo_last_pet_variant", 0)
        data.setdefault("echo_last_boop_variant", 0)
        data.setdefault("echo_last_hug_variant", 0)
        # Echo vore state defaults (Phase 1: Safe Belly Shelter)
        data.setdefault("echo_vore_tension", 0.0)
        data.setdefault("echo_last_vore_tension_day", None)
        data.setdefault("belly_state", None)
        # Condition/strain defaults (0 = fine)
        data.setdefault("condition", 0)
        # Time-of-day defaults
        data.setdefault("time_of_day", "Day")
        data.setdefault("is_sheltered", False)
        # General flags
        data.setdefault("flags", {})
        # Rare lore event tracking
        data.setdefault("rare_event_triggers", {})
        return data
