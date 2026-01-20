"""
Character models and stat modifier pipeline for Lost Hiker.

This module handles player character data, stats, and the modifier system.
Characters have base stats that are modified by race traits, temporary buffs
(teas, curses), and permanent unlocks.

## Key Concepts:
- Character: Player character with race, stats, and modifiers
- TimedModifier: Temporary stat changes (tea buffs, debuffs) that expire
- Modifier Pipeline: Base stats → race mods → permanent mods → timed mods = final stat

## Stat System:
Stats are calculated dynamically by applying modifiers in order:
1. Start with base_stats (default values for all characters)
2. Apply race_modifiers (racial traits like wolf_kin +1 stamina)
3. Apply permanent_modifiers (unlocks, gear)
4. Apply timed_modifiers (tea buffs, temporary effects)

## For Content Editors:
- Race stats are defined in data/races.json
- Modifiers use {"add": {"stat": value}, "mul": {"stat": multiplier}} format
- Common stats: stamina_max, inventory_slots, stamina_camp_restore
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# Type alias for modifier specifications
# Format: {"add": {"stat_name": value}, "mul": {"stat_name": multiplier}}
ModifierSpec = Dict[str, Dict[str, float]]

# Default base stats for all characters
# These are the starting values before any racial/equipment modifiers
DEFAULT_BASE_STATS: Dict[str, float] = {
    "stamina_max": 4.0,  # Maximum stamina points (explore actions before needing rest)
    "stamina_wake_restore": 1.0,  # Stamina restored when waking up (partial rest)
    "stamina_camp_restore": 3.0,  # Stamina restored from proper camp (full rest)
    "explore_slots": 1.0,  # Exploration actions per stamina point (usually 1)
    "camp_meal_cost": 1.0,  # Meal units consumed when camping (usually 1)
    "inventory_slots": 20.0,  # Backpack capacity (number of items)
}


@dataclass
class TimedModifier:
    """
    Temporary stat modifier that expires on a specific day.
    
    Used for tea buffs, curses, temporary debuffs, etc.
    These are stored in GameState.timed_modifiers and automatically
    pruned when they expire.
    
    ## Example:
    Drinking "stamina tea" might create:
    TimedModifier(
        source="stamina_tea",
        modifiers=[{"add": {"stamina_max": 2.0}}],
        expires_on_day=5  # Expires at end of day 5
    )
    
    Attributes:
        source: Identifier for what created this modifier (e.g., "stamina_tea", "curse_weakness")
        modifiers: List of stat modifications to apply
        expires_on_day: Day when effect ends (None = permanent until manually removed)
    """

    source: str  # What caused this modifier (item name, effect ID, etc.)
    modifiers: Sequence[ModifierSpec]  # List of stat modifications
    expires_on_day: Optional[int] = None  # Day when effect expires (None = permanent)

    def is_active(self, current_day: int) -> bool:
        """
        Check if this modifier is still active.
        
        Args:
            current_day: Current in-game day number
            
        Returns:
            True if modifier should still be applied, False if expired
        """
        if self.expires_on_day is None:
            return True  # Permanent modifier (no expiration)
        return current_day <= self.expires_on_day


@dataclass
class Character:
    """
    Player character data and stat computation engine.
    
    This class stores all character-specific information and provides methods
    to calculate final stats after applying all modifiers.
    
    ## Modular Race System:
    Characters are built from race templates (data/races.json) but can be
    customized during creation. Race determines starting modifiers and flavor tags.
    
    ## Flavor Tags:
    Tags like "scaly", "fluffy", "warm_blooded" affect NPC reactions and flavor text.
    NPCs and creatures respond differently based on tags (see race_flavor.py).
    
    Attributes:
        name: Player's chosen character name
        race_id: Race identifier (e.g., "human", "wolf_kin", "elf")
        body_type: Physical form ("humanoid", "taur", "naga", "quadruped")
        size: Size category ("small", "medium", "large")
        archetype: Ecology type ("forest_creature", "cave_creature", etc.)
        flavor_tags: Sensory/aesthetic tags for NPC reactions
        tags: Gameplay tags (from race, affects mechanics)
        base_stats: Unmodified stat values
        race_modifiers: Stat modifiers from race (e.g., wolf_kin gets +stamina)
        permanent_modifiers: Unlocks/achievements that modify stats permanently
    """

    name: str = ""  # Character name (shown in UI, dialogue)
    race_id: str = "human"  # Race identifier (links to races.json)
    
    # Physical attributes (chosen during character creation)
    body_type: str = "humanoid"  # "humanoid", "taur", "naga", "quadruped"
    size: str = "medium"  # "small", "medium", "large"
    archetype: str = "forest_creature"  # Ecology type for flavor/reactions
    
    # Tags for flavor and mechanics
    flavor_tags: List[str] = field(default_factory=list)  # For NPC reactions (scaly, fluffy, etc.)
    tags: List[str] = field(default_factory=list)  # Gameplay tags from race
    
    # Stats and modifiers
    base_stats: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_BASE_STATS)
    )  # Unmodified baseline stats
    race_modifiers: Sequence[ModifierSpec] = field(default_factory=tuple)  # From race (immutable)
    permanent_modifiers: List[ModifierSpec] = field(default_factory=list)  # From unlocks/achievements

    def active_modifiers(
        self,
        timed_modifiers: Iterable[TimedModifier],
        current_day: int,
    ) -> Iterator[Tuple[str, ModifierSpec]]:
        """
        Yield all active modifiers in application order.
        
        Modifiers are applied in a specific order to ensure consistent behavior:
        1. Race modifiers (racial traits)
        2. Permanent modifiers (unlocks, achievements)
        3. Timed modifiers (tea buffs, temporary effects)
        
        Args:
            timed_modifiers: List of temporary modifiers from GameState
            current_day: Current in-game day (for checking expiration)
            
        Yields:
            (source, modifier_spec) tuples for each active modifier
        """
        # 1. Apply race modifiers first (baseline racial traits)
        for spec in self.race_modifiers:
            yield ("race", spec)
        
        # 2. Apply permanent modifiers (achievements, unlocks)
        for spec in self.permanent_modifiers:
            yield ("permanent", spec)
        
        # 3. Apply timed modifiers (teas, buffs, debuffs)
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
        """
        Calculate final stat value after applying all modifiers.
        
        This is the core stat calculation engine. It starts with base value
        and applies modifiers in order: add first, then multiply.
        
        ## Example Calculation:
        Base stamina_max = 4.0
        + Race adds +1.0 = 5.0
        + Tea adds +2.0 = 7.0
        * Curse multiplies by 0.8 = 5.6
        Final stamina_max = 5.6
        
        Args:
            key: Stat name (e.g., "stamina_max", "inventory_slots")
            timed_modifiers: Active temporary modifiers
            current_day: Current day (for checking modifier expiration)
            
        Returns:
            Final calculated stat value (after all modifiers)
        """
        # Start with base stat value
        value = float(self.base_stats.get(key, 0.0))
        
        # Apply each modifier in order (race → permanent → timed)
        for _source, spec in self.active_modifiers(timed_modifiers, current_day):
            # Apply additive modifiers first (+/- to stat)
            if "add" in spec:
                value += spec["add"].get(key, 0.0)
            
            # Apply multiplicative modifiers second (* to stat)
            if "mul" in spec:
                value *= spec["mul"].get(key, 1.0)
        
        return value

    def to_dict(self) -> Dict[str, object]:
        """Serialize this character to a plain dictionary."""
        return {
            "name": self.name,
            "race_id": self.race_id,
            "body_type": self.body_type,
            "size": self.size,
            "archetype": self.archetype,
            "flavor_tags": list(self.flavor_tags),
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
            body_type=str(data.get("body_type", "humanoid")),
            size=str(data.get("size", "medium")),
            archetype=str(data.get("archetype", "forest_creature")),
            flavor_tags=list(data.get("flavor_tags", [])),
            tags=list(data.get("tags", [])),
            base_stats=dict(data.get("base_stats", DEFAULT_BASE_STATS)),
            race_modifiers=tuple(data.get("race_modifiers", [])),
            permanent_modifiers=list(data.get("permanent_modifiers", [])),
        )


def build_character_from_race(
    race_id: str,
    race_data: Dict[str, object],
    name: str,
    body_type: Optional[str] = None,
    size: Optional[str] = None,
    archetype: Optional[str] = None,
    flavor_tags: Optional[List[str]] = None,
) -> Character:
    """
    Create a new character from race template.
    
    Called during character creation to build a Character from race data
    (loaded from data/races.json). Allows customization of body_type, size,
    and archetype while preserving race modifiers and defaults.
    
    Args:
        race_id: Race identifier (e.g., "human", "wolf_kin")
        race_data: Race definition from races.json
        name: Player's chosen character name
        body_type: Override default body_type (None = use race default)
        size: Override default size (None = use race default)
        archetype: Override default archetype (None = use race default)
        flavor_tags: Override flavor tags (None = use race default)
        
    Returns:
        New Character instance ready for gameplay
    """
    # Extract race modifiers and tags from race data
    tags = list(race_data.get("tags", []))
    modifiers = tuple(race_data.get("modifiers", []))
    
    return Character(
        name=name,
        race_id=race_id,
        # Use provided values or fall back to race defaults
        body_type=body_type or str(race_data.get("body_type_default", "humanoid")),
        size=size or str(race_data.get("size_default", "medium")),
        archetype=archetype or str(race_data.get("archetype_default", "forest_creature")),
        flavor_tags=list(flavor_tags) if flavor_tags is not None else list(race_data.get("flavor_tags", [])),
        tags=tags,
        race_modifiers=modifiers,
    )


def sync_character_with_race(
    character: Character, race_data: Dict[str, object]
) -> None:
    """
    Update existing character with current race data.
    
    Called when loading old saves to ensure character has latest race
    modifiers and stats. Useful when race definitions are updated in
    races.json between game versions.
    
    Args:
        character: Existing character instance (from loaded save)
        race_data: Current race definition from races.json
    """
    # Update race-derived fields to match current race definition
    character.tags = list(race_data.get("tags", []))
    character.race_modifiers = tuple(race_data.get("modifiers", []))
    
    # Ensure base_stats contains all expected stats (for migration)
    if not character.base_stats:
        character.base_stats = dict(DEFAULT_BASE_STATS)
    for key, value in DEFAULT_BASE_STATS.items():
        character.base_stats.setdefault(key, value)
