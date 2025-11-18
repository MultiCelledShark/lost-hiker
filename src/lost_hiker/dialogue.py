"""Dialogue system for NPC conversations in Lost Hiker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

from .state import GameState
from .rapport import get_rapport, get_rapport_tier, change_rapport
from .runestones import get_runestone_state


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

    def get_node(self, node_id: str) -> Optional[DialogueNode]:
        """Get a dialogue node by ID."""
        return self._by_id.get(node_id)

    def get_starting_node(self, npc_id: str) -> Optional[DialogueNode]:
        """Get the starting node for an NPC (node with id 'start' or first node)."""
        npc_nodes = self._by_npc.get(npc_id, [])
        if not npc_nodes:
            return None
        # Look for a node with id ending in "_start" or just "start"
        for node in npc_nodes:
            if node.node_id.endswith("_start") or node.node_id == "start":
                return node
        # Fall back to first node
        return npc_nodes[0]


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
        npc_flags = state.npc_flags.get(npc_id, {})
        return bool(npc_flags.get(flag_name, False))

    elif condition_key == "require_not_flag":
        flag_name = str(condition_value)
        npc_flags = state.npc_flags.get(npc_id, {})
        return not bool(npc_flags.get(flag_name, False))

    elif condition_key == "require_race":
        required_races = condition_value
        if isinstance(required_races, str):
            required_races = [required_races]
        return state.character.race_id in required_races

    elif condition_key == "runestone_progress":
        # Check runestone repair progress
        progress_type = str(condition_value).lower()
        if progress_type == "none":
            return state.act1_repaired_runestones == 0
        elif progress_type == "some":
            return 1 <= state.act1_repaired_runestones < 3
        elif progress_type == "act1_complete":
            return state.act1_forest_stabilized or state.act1_repaired_runestones >= 3
        return False

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
    # Apply rapport change
    if option.rapport_delta != 0:
        change_rapport(state, npc_id, option.rapport_delta)

    # Set flags
    if option.set_flags:
        if npc_id not in state.npc_flags:
            state.npc_flags[npc_id] = {}
        for flag_name, flag_value in option.set_flags.items():
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
        node = dialogue_catalog.get_node(starting_node_id)
    else:
        node = dialogue_catalog.get_starting_node(npc_id)
    
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
    current_node = session.dialogue_catalog.get_node(session.current_node_id)
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
    
    next_node = session.dialogue_catalog.get_node(chosen_option.next_node_id)
    if not next_node:
        return True, None
    
    # Check if next node conditions are met
    if not check_node_conditions(next_node, state, session.npc_id):
        return True, None
    
    # Update session
    session.current_node_id = next_node.node_id
    
    return False, next_node.text


def get_current_dialogue_text(session: DialogueSession) -> str:
    """Get the NPC text for the current dialogue node."""
    node = session.dialogue_catalog.get_node(session.current_node_id)
    if not node:
        return ""
    return node.text


def get_current_dialogue_options(
    session: DialogueSession, state: GameState
) -> List[str]:
    """Get the available option texts for the current dialogue node."""
    node = session.dialogue_catalog.get_node(session.current_node_id)
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

