"""Dialogue system for NPC conversations in Lost Hiker."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from .state import GameState
from .rapport import get_rapport, get_rapport_tier, change_rapport
from .runestones import get_runestone_state
from .flavor_tags import TAG_FAMILIES


@dataclass(frozen=True)
class DialogueOption:
    """A player choice option in a dialogue node."""

    text: str
    next_node_id: str  # "END" to end conversation
    rapport_delta: int = 0
    set_flags: Dict[str, bool] = None  # Optional flags to set
    conditions: Dict[str, Any] = None  # Optional conditions for this option

    def __post_init__(self) -> None:
        if self.set_flags is None:
            object.__setattr__(self, "set_flags", {})
        if self.conditions is None:
            object.__setattr__(self, "conditions", {})

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueOption":
        """Create a DialogueOption from JSON data."""
        return cls(
            text=str(data.get("text", "")),
            next_node_id=str(data.get("next_node_id", "END")),
            rapport_delta=int(data.get("rapport_delta", 0)),
            set_flags=dict(data.get("set_flags", {})),
            conditions=dict(data.get("conditions", {})),
        )


@dataclass(frozen=True)
class DialogueNode:
    """A single dialogue node with NPC text and player options."""

    node_id: str
    npc_id: str
    text: str
    options: List[DialogueOption]
    conditions: Dict[str, Any] = None  # Conditions for this node to be available

    def __post_init__(self) -> None:
        if self.conditions is None:
            object.__setattr__(self, "conditions", {})

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueNode":
        """Create a DialogueNode from JSON data."""
        options_data = data.get("options", [])
        options = [DialogueOption.from_dict(opt) for opt in options_data]
        return cls(
            node_id=str(data.get("id", "")),
            npc_id=str(data.get("npc_id", "")),
            text=str(data.get("text", "")),
            options=options,
            conditions=dict(data.get("conditions", {})),
        )


@dataclass
class DialogueSession:
    """Active dialogue session state."""

    npc_id: str
    current_node_id: str
    dialogue_catalog: "DialogueCatalog"


class DialogueCatalog:
    """Catalog of all dialogue nodes for NPCs."""

    def __init__(self, nodes: List[DialogueNode]):
        self.nodes = nodes
        self._by_id: Dict[str, DialogueNode] = {
            node.node_id: node for node in nodes
        }
        self._by_npc: Dict[str, List[DialogueNode]] = {}
        for node in nodes:
            if node.npc_id not in self._by_npc:
                self._by_npc[node.npc_id] = []
            self._by_npc[node.npc_id].append(node)

    def get_node(self, node_id: str, state: Optional[GameState] = None) -> Optional[DialogueNode]:
        """
        Get a dialogue node by ID.
        
        For certain nodes (like astrin_brewing), checks for race-specific variants first.
        """
        # Check for race-specific variants for certain nodes
        if state and node_id == "astrin_brewing":
            race_id = state.character.race_id
            race_variant_id = f"{node_id}_{race_id}"
            race_node = self._by_id.get(race_variant_id)
            if race_node and check_node_conditions(race_node, state, "astrin"):
                return race_node
        
        return self._by_id.get(node_id)

    def get_starting_node(self, npc_id: str, state: Optional[GameState] = None) -> Optional[DialogueNode]:
        """
        Get the starting node for an NPC (node with id 'start' or first node).
        
        For Echo, also checks for race-aware greeting nodes that match the player's race.
        Occasionally checks for tag/body_type/archetype-aware reaction nodes.
        """
        npc_nodes = self._by_npc.get(npc_id, [])
        if not npc_nodes:
            return None
        
        # For Echo, check for race-aware greeting nodes first
        if npc_id == "echo" and state:
            race_id = state.character.race_id
            race_greeting_id = f"echo_race_greeting_{race_id}"
            race_node = self._by_id.get(race_greeting_id)
            if race_node and check_node_conditions(race_node, state, npc_id):
                return race_node
        
        # Occasionally (15% chance) check for tag/body_type/archetype-aware reaction nodes
        # This makes NPCs occasionally comment on player morphology
        if state and random.random() < 0.15:
            character = state.character
            # Check body_type reactions
            body_type_nodes = [
                f"{npc_id}_body_type_{character.body_type}",
            ]
            for node_id in body_type_nodes:
                node = self._by_id.get(node_id)
                if node and check_node_conditions(node, state, npc_id):
                    return node
            
            # Check tag family reactions (check before individual tags for priority)
            tag_family_checks = [
                ("fungal", is_fungal),
                ("ooze", is_ooze),
                ("synth", is_synth),
                ("elemental", is_elemental),
                ("psionic", is_psionic),
                ("material", is_material),
            ]
            for family_name, check_func in tag_family_checks:
                if check_func(character):
                    family_node_id = f"{npc_id}_tag_family_{family_name}"
                    node = self._by_id.get(family_node_id)
                    if node and check_node_conditions(node, state, npc_id):
                        return node
            
            # Check flavor_tag reactions (check first matching tag)
            for tag in character.flavor_tags:
                tag_node_id = f"{npc_id}_flavor_tag_{tag}"
                node = self._by_id.get(tag_node_id)
                if node and check_node_conditions(node, state, npc_id):
                    return node
            
            # Check size reactions
            size_node_id = f"{npc_id}_size_{character.size}"
            node = self._by_id.get(size_node_id)
            if node and check_node_conditions(node, state, npc_id):
                return node
            
            # Check archetype reactions
            archetype_node_id = f"{npc_id}_archetype_{character.archetype}"
            node = self._by_id.get(archetype_node_id)
            if node and check_node_conditions(node, state, npc_id):
                return node
            
            # Special: Echo's Forest size-bending lore (5% chance when other reactions don't trigger)
            if npc_id == "echo" and random.random() < 0.33:
                node = self._by_id.get("echo_forest_size_bending")
                if node and check_node_conditions(node, state, npc_id):
                    return node
        
        # Look for a node with id ending in "_start" or just "start"
        # First, try race-aware start nodes (e.g., "astrin_glade_start_elf")
        if state:
            race_id = state.character.race_id
            race_start_ids = [
                f"{npc_id}_glade_start_{race_id}",
                f"{npc_id}_start_{race_id}",
                f"start_{race_id}",
            ]
            for race_start_id in race_start_ids:
                race_node = self._by_id.get(race_start_id)
                if race_node and check_node_conditions(race_node, state, npc_id):
                    return race_node
        
        # Look for regular start nodes
        for node in npc_nodes:
            if (node.node_id.endswith("_start") or node.node_id == "start") and (
                not state or check_node_conditions(node, state, npc_id)
            ):
                return node
        # Fall back to first node that passes conditions (if checking)
        if state:
            for node in npc_nodes:
                if check_node_conditions(node, state, npc_id):
                    return node
        return npc_nodes[0] if npc_nodes else None


def has_tag_family(character: "Character", family: str) -> bool:
    """
    Check if a character has any tags from a specific tag family.
    
    Args:
        character: The character to check
        family: The tag family name (e.g., "fungal", "slime", "synth")
        
    Returns:
        True if character has any tag from the family, False otherwise
    """
    family_tags = TAG_FAMILIES.get(family, [])
    player_tags = set(character.flavor_tags)
    return any(tag in player_tags for tag in family_tags)


def is_fungal(character: "Character") -> bool:
    """Check if character has fungal/mycelial tags."""
    return has_tag_family(character, "fungal")


def is_ooze(character: "Character") -> bool:
    """Check if character has slime/ooze tags."""
    return has_tag_family(character, "slime")


def is_synth(character: "Character") -> bool:
    """Check if character has synth/construct tags."""
    return has_tag_family(character, "synth")


def is_elemental(character: "Character") -> bool:
    """Check if character has elemental tags (emberheart, frostbreath, stormtouched)."""
    player_tags = set(character.flavor_tags)
    elemental_tags = ["emberheart", "frostbreath", "stormtouched", "mistborne"]
    return any(tag in player_tags for tag in elemental_tags)


def is_psionic(character: "Character") -> bool:
    """Check if character has psionic tags (mindecho, astral, dreamlinked, veilborn)."""
    player_tags = set(character.flavor_tags)
    psionic_tags = ["mindecho", "astral", "dreamlinked", "veilborn"]
    return any(tag in player_tags for tag in psionic_tags)


def is_material(character: "Character") -> bool:
    """Check if character has material tags (saplike, rubberlike, fungal_leather, crystalhide, mossfur, boneplated)."""
    player_tags = set(character.flavor_tags)
    material_tags = ["saplike", "rubberlike", "fungal_leather", "crystalhide", "mossfur", "boneplated"]
    return any(tag in player_tags for tag in material_tags)


def check_condition(
    condition_key: str, condition_value: Any, state: GameState, npc_id: str
) -> bool:
    """
    Check if a condition is met.
    
    Args:
        condition_key: The type of condition (e.g., "min_rapport_tier", "require_flag")
        condition_value: The value to check against
        state: Current game state
        npc_id: The NPC ID for context
        
    Returns:
        True if condition is met, False otherwise
    """
    if condition_key == "min_rapport_tier":
        current_rapport = get_rapport(state, npc_id)
        current_tier = get_rapport_tier(current_rapport)
        required_tier = str(condition_value).lower()
        tier_order = ["hostile", "wary", "neutral", "friendly", "bonded"]
        try:
            current_index = tier_order.index(current_tier)
            required_index = tier_order.index(required_tier)
            return current_index >= required_index
        except ValueError:
            return False

    elif condition_key == "require_flag":
        flag_name = str(condition_value)
        # Check both npc_flags and npc_state
        npc_flags = state.npc_flags.get(npc_id, {})
        if flag_name in npc_flags:
            return bool(npc_flags.get(flag_name, False))
        # Also check npc_state for Wave 1 NPC flags
        if flag_name in state.npc_state:
            return bool(state.npc_state.get(flag_name, False))
        return False

    elif condition_key == "require_not_flag":
        flag_name = str(condition_value)
        # Check both npc_flags and npc_state
        npc_flags = state.npc_flags.get(npc_id, {})
        if flag_name in npc_flags:
            return not bool(npc_flags.get(flag_name, False))
        # Also check npc_state for Wave 1 NPC flags
        if flag_name in state.npc_state:
            return not bool(state.npc_state.get(flag_name, False))
        # If flag doesn't exist, require_not_flag is True
        return True

    elif condition_key == "require_race":
        required_races = condition_value
        if isinstance(required_races, str):
            required_races = [required_races]
        return state.character.race_id in required_races

    elif condition_key == "runestone_progress":
        # Check runestone repair progress
        from .forest_act1 import init_forest_act1_state, is_forest_act1_complete
        init_forest_act1_state(state)
        progress_type = str(condition_value).lower()
        if progress_type == "none":
            return state.act1_repaired_runestones == 0
        elif progress_type == "some":
            return 1 <= state.act1_repaired_runestones < 3
        elif progress_type == "act1_complete":
            return is_forest_act1_complete(state)
        return False

    elif condition_key == "has_items":
        # Check if player has required items in inventory
        # Supports both simple list and dict with quantities
        from collections import Counter
        inventory_counts = Counter(state.inventory)
        
        if isinstance(condition_value, dict):
            # Dict format: {"item": quantity, ...}
            for item, qty in condition_value.items():
                if inventory_counts.get(item, 0) < qty:
                    return False
            return True
        else:
            # List format: ["item1", "item2", ...] - checks for at least 1 of each
            required_items = condition_value
            if isinstance(required_items, str):
                required_items = [required_items]
            elif not isinstance(required_items, list):
                return False
            # Check if all required items are in inventory
            inventory_set = set(state.inventory)
            return all(item in inventory_set for item in required_items)

    elif condition_key == "require_state":
        # Check npc_state values
        if not isinstance(condition_value, dict):
            return False
        npc_state = state.npc_state
        for state_key, state_value in condition_value.items():
            if state_key not in npc_state:
                return False
            if npc_state[state_key] != state_value:
                return False
        return True

    elif condition_key == "time_of_day":
        # Check current time of day
        required_time = str(condition_value)
        return state.time_of_day == required_time

    elif condition_key == "require_radio_version":
        # Check if radio version meets requirement (for Echo dialogue)
        required_version = int(condition_value)
        return state.radio_version >= required_version

    elif condition_key == "require_body_type":
        # Check if player's body_type matches
        required_types = condition_value
        if isinstance(required_types, str):
            required_types = [required_types]
        return state.character.body_type in required_types

    elif condition_key == "require_flavor_tag":
        # Check if player has a specific flavor_tag
        required_tags = condition_value
        if isinstance(required_tags, str):
            required_tags = [required_tags]
        player_tags = set(state.character.flavor_tags)
        return any(tag in player_tags for tag in required_tags)

    elif condition_key == "require_tag_family":
        # Check if player has any tag from a specific tag family
        required_family = str(condition_value)
        # Handle special tag families that aren't in TAG_FAMILIES
        if required_family == "elemental":
            return is_elemental(state.character)
        elif required_family == "psionic":
            return is_psionic(state.character)
        else:
            return has_tag_family(state.character, required_family)

    elif condition_key == "require_size":
        # Check if player's size category matches
        required_sizes = condition_value
        if isinstance(required_sizes, str):
            required_sizes = [required_sizes]
        return state.character.size in required_sizes

    elif condition_key == "require_archetype":
        # Check if player's archetype matches
        required_archetypes = condition_value
        if isinstance(required_archetypes, str):
            required_archetypes = [required_archetypes]
        return state.character.archetype in required_archetypes

    elif condition_key == "require_vore_enabled":
        # Check if vore is enabled
        from .vore import is_vore_enabled
        return is_vore_enabled(state)

    elif condition_key == "require_vore_disabled":
        # Check if vore is disabled
        from .vore import is_vore_enabled
        return not is_vore_enabled(state)

    return False


def check_node_conditions(
    node: DialogueNode, state: GameState, npc_id: str
) -> bool:
    """Check if a dialogue node's conditions are met."""
    if not node.conditions:
        return True
    for key, value in node.conditions.items():
        if not check_condition(key, value, state, npc_id):
            return False
    return True


def check_option_conditions(
    option: DialogueOption, state: GameState, npc_id: str
) -> bool:
    """Check if a dialogue option's conditions are met."""
    if not option.conditions:
        return True
    for key, value in option.conditions.items():
        if not check_condition(key, value, state, npc_id):
            return False
    return True


def get_available_options(
    node: DialogueNode, state: GameState, npc_id: str
) -> List[DialogueOption]:
    """Get the list of available options for a dialogue node."""
    available = []
    for option in node.options:
        if check_option_conditions(option, state, npc_id):
            available.append(option)
    return available


def apply_option_effects(
    option: DialogueOption, state: GameState, npc_id: str
) -> None:
    """Apply the effects of choosing a dialogue option."""
    # Handle micro-quest completions that require items
    # Check if this option completes a quest that needs items
    if option.conditions and "has_items" in option.conditions:
        from collections import Counter
        required_items = option.conditions["has_items"]
        inventory_counts = Counter(state.inventory)
        
        if isinstance(required_items, dict):
            # Dict format: {"item": quantity, ...}
            for item, qty in required_items.items():
                for _ in range(qty):
                    if item in state.inventory:
                        state.inventory.remove(item)
        else:
            # List format: ["item1", "item2", ...] - remove one of each
            if isinstance(required_items, str):
                required_items = [required_items]
            for item in required_items:
                if item in state.inventory:
                    state.inventory.remove(item)
    
    # Handle Astrin rescue - move her to Glade
    if npc_id == "astrin" and option.set_flags.get("astrin_status") == "found":
        state.npc_state["astrin_status"] = "at_glade"
    
    # Handle Rhew Na charm gift
    if npc_id == "rhew_na" and option.set_flags.get("rhew_na_charm_given"):
        if "glitch_marked_charm" not in state.inventory:
            state.inventory.append("glitch_marked_charm")
    
    # Apply rapport change
    if option.rapport_delta != 0:
        change_rapport(state, npc_id, option.rapport_delta)

    # Set flags
    if option.set_flags:
        if npc_id not in state.npc_flags:
            state.npc_flags[npc_id] = {}
        for flag_name, flag_value in option.set_flags.items():
            # Handle npc_state flags
            if flag_name in ("hermit_met", "naiad_met", "druid_met", "fisher_met",
                            "hermit_explained_runestones", "naiad_share_recipe",
                            "druid_shroomling_quest_started", "druid_shroomling_quest_completed",
                            "fisher_mussel_quest_started", "fisher_mussel_quest_completed",
                            "astrin_tea_unlocked", "echo_first_repair_acknowledged",
                            "echo_astrin_acknowledged", "echo_race_greeting_shown",
                            "hermit_trinket_quest_started", "hermit_trinket_quest_completed",
                            "hermit_sketch_given", "naiad_blessing_quest_started",
                            "naiad_blessing_quest_completed", "druid_night_ritual_available",
                            "fisher_mussel_mastery_learned", "fisher_trap_quest_started",
                            "fisher_trap_quest_completed", "astrin_request_quest_started",
                            "astrin_request_quest_completed"):
                state.npc_state[flag_name] = bool(flag_value)
                # Apply buffs when quests are completed
                if flag_name == "hermit_sketch_given" and flag_value:
                    from .micro_quests import apply_hermit_sketch_buff
                    apply_hermit_sketch_buff(state)
                elif flag_name == "fisher_mussel_mastery_learned" and flag_value:
                    from .micro_quests import apply_fisher_mussel_mastery
                    apply_fisher_mussel_mastery(state)
            # Handle astrin_status specially
            elif flag_name == "astrin_status":
                state.npc_state["astrin_status"] = str(flag_value)
            else:
                # Regular npc_flags
                state.npc_flags[npc_id][flag_name] = bool(flag_value)
            # Special handling for Echo radio connection hint
            if npc_id == "echo" and flag_name == "echo_radio_connection_hint_shown" and flag_value:
                state.echo_radio_connection_hint_shown = True


def start_dialogue(
    state: GameState, npc_id: str, dialogue_catalog: DialogueCatalog, starting_node_id: Optional[str] = None
) -> Optional[DialogueSession]:
    """
    Start a dialogue session with an NPC.
    
    Args:
        state: Current game state
        npc_id: ID of the NPC to talk to
        dialogue_catalog: The dialogue catalog
        starting_node_id: Optional specific node to start at (defaults to NPC's start node)
        
    Returns:
        A DialogueSession if dialogue can start, None otherwise
    """
    if starting_node_id:
        node = dialogue_catalog.get_node(starting_node_id, state)
    else:
        node = dialogue_catalog.get_starting_node(npc_id, state)
    
    if not node:
        return None
    
    # Check if starting node conditions are met
    if not check_node_conditions(node, state, npc_id):
        return None
    
    return DialogueSession(
        npc_id=npc_id,
        current_node_id=node.node_id,
        dialogue_catalog=dialogue_catalog,
    )


def step_dialogue(
    session: DialogueSession, state: GameState, choice_index: int
) -> tuple[bool, Optional[str]]:
    """
    Process a player choice in dialogue.
    
    Args:
        session: Current dialogue session
        state: Current game state
        choice_index: Index of the chosen option (0-based)
        
    Returns:
        Tuple of (is_ended, npc_text)
        - is_ended: True if dialogue has ended
        - npc_text: The NPC's text for the current node (None if ended)
    """
    current_node = session.dialogue_catalog.get_node(session.current_node_id, state)
    if not current_node:
        return True, None
    
    # Get available options
    available = get_available_options(current_node, state, session.npc_id)
    if not available:
        # No valid options, end dialogue
        return True, None
    
    if choice_index < 0 or choice_index >= len(available):
        # Invalid choice index
        return False, None
    
    chosen_option = available[choice_index]
    
    # Apply effects
    apply_option_effects(chosen_option, state, session.npc_id)
    
    # Move to next node
    if chosen_option.next_node_id == "END":
        return True, None
    
    next_node = session.dialogue_catalog.get_node(chosen_option.next_node_id, state)
    if not next_node:
        return True, None
    
    # Check if next node conditions are met
    if not check_node_conditions(next_node, state, session.npc_id):
        return True, None
    
    # Update session
    session.current_node_id = next_node.node_id
    
    return False, next_node.text


def get_current_dialogue_text(session: DialogueSession, state: GameState) -> str:
    """Get the NPC text for the current dialogue node."""
    node = session.dialogue_catalog.get_node(session.current_node_id, state)
    if not node:
        return ""
    return node.text


def get_current_dialogue_options(
    session: DialogueSession, state: GameState
) -> List[str]:
    """Get the available option texts for the current dialogue node."""
    node = session.dialogue_catalog.get_node(session.current_node_id, state)
    if not node:
        return []
    available = get_available_options(node, state, session.npc_id)
    return [opt.text for opt in available]


def load_dialogue_catalog(data_dir: Path, filename: str = "dialogue_forest.json") -> DialogueCatalog:
    """Load dialogue nodes from a JSON file."""
    path = data_dir / filename
    if not path.exists():
        return DialogueCatalog([])
    
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    
    nodes = [
        DialogueNode.from_dict(entry)
        for entry in raw.get("nodes", [])
    ]
    
    return DialogueCatalog(nodes)

