"""NPC appearance logic for determining when NPCs are present at landmarks."""

from __future__ import annotations

import random
from typing import List, Optional

from .state import GameState
from .npcs import NPC, NPCCatalog
from .forest_act1 import get_forest_act1_progress_summary
from .runestones import get_repaired_runestone_count


def should_npc_appear(
    npc: NPC,
    state: GameState,
    landmark_id: str,
) -> bool:
    """
    Determine if an NPC should appear at a given landmark.
    
    Args:
        npc: The NPC to check
        state: Current game state
        landmark_id: The landmark ID where the NPC might appear
        
    Returns:
        True if the NPC should appear, False otherwise
    """
    # Check if NPC is associated with this landmark
    if landmark_id not in npc.landmark_ids:
        return False
    
    # Special handling for each NPC
    if npc.npc_id == "echo":
        # Echo is always at the Glade
        return landmark_id == "glade" and state.echo_present_at_glade
    
    elif npc.npc_id == "forest_hermit":
        # Hermit is a wandering NPC, appears at shallow/mid-forest landmarks
        # More likely in early days, but can appear later
        if state.day <= 10:
            # Higher chance in first 10 days
            return random.random() < 0.6
        else:
            # Still possible later, but less common
            return random.random() < 0.3
    
    elif npc.npc_id == "naiad":
        # Naiad only appears after at least one runestone is repaired
        repaired_count = get_repaired_runestone_count(state)
        if repaired_count < 1:
            return False
        # After first repair, has a chance to appear
        return random.random() < 0.5
    
    elif npc.npc_id == "druid":
        # Druid appears at Verdant Hollow and Whispering Hollow
        # Moderate chance when visiting
        return random.random() < 0.4
    
    elif npc.npc_id == "fisher":
        # Fisher appears at creek landmarks during daytime
        if state.time_of_day not in ("Day", "Dawn", "Dusk"):
            return False
        # Good chance during daytime
        return random.random() < 0.5
    
    elif npc.npc_id == "astrin":
        # Astrin's appearance depends on her status
        astrin_status = state.npc_state.get("astrin_status", "missing")
        
        if astrin_status == "missing":
            # Can be found at Sunken Spring or Verdant Hollow
            if landmark_id in ("sunken_spring", "verdant_hollow"):
                return random.random() < 0.4
            return False
        elif astrin_status == "found":
            # After being found but before reaching Glade, she's in transit
            # Don't appear at landmarks
            return False
        elif astrin_status == "at_glade":
            # At the Glade permanently
            return landmark_id == "glade"
        
        return False
    
    # Default: NPC appears if associated with landmark
    return True


def get_present_npcs(
    npc_catalog: NPCCatalog,
    state: GameState,
    landmark_id: str,
) -> List[NPC]:
    """
    Get list of NPCs that should be present at a given landmark.
    
    Args:
        npc_catalog: The NPC catalog
        state: Current game state
        landmark_id: The landmark ID to check
        
    Returns:
        List of NPCs that should appear at this landmark
    """
    all_npcs = npc_catalog.get_npcs_at_landmark(landmark_id)
    present = []
    
    for npc in all_npcs:
        if should_npc_appear(npc, state, landmark_id):
            present.append(npc)
    
    return present


def get_npc_presence_description(npc: NPC, landmark_id: str) -> str:
    """
    Get a description of an NPC's presence at a landmark.
    
    Args:
        npc: The NPC
        landmark_id: The landmark where they appear
        
    Returns:
        A description string
    """
    if npc.npc_id == "echo":
        return "Echo is here, her massive coils resting near the charred tree."
    elif npc.npc_id == "forest_hermit":
        return "Alder sits by a small fire, their weathered face calm and watchful."
    elif npc.npc_id == "naiad":
        return "The Naiad's form shimmers in the spring, mist and water coalescing into a graceful figure."
    elif npc.npc_id == "druid":
        return "The Druid examines the mushrooms, their expression troubled."
    elif npc.npc_id == "fisher":
        return "A lizard-folk crouches by the water's edge, examining the creek with practiced efficiency."
    elif npc.npc_id == "astrin":
        astrin_status = None  # Will be checked in calling code
        return "Astrin is here, organizing her samples and setting up a small workspace."
    
    return f"{npc.name} is here."

