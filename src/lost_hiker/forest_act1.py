"""Forest Act I quest state and progression tracking for Lost Hiker."""

from __future__ import annotations

from typing import Dict, Optional

from .state import GameState

# Configuration: number of runestones required to complete Act I
REQUIRED_ACT1_RUNESTONES = 3


def init_forest_act1_state(state: GameState) -> None:
    """
    Initialize or ensure forest_act1 state structure exists.
    
    This function ensures backward compatibility by migrating from old
    flat fields to the new forest_act1 dict structure.
    
    Args:
        state: Current game state
    """
    # Get total runestones from definitions if not already set
    total_runestones = state.act1_total_runestones
    if total_runestones == 0:
        # Try to load from runestone definitions
        try:
            from pathlib import Path
            import json
            # Try to find data directory (this is a fallback)
            # In practice, the engine should set this via update_forest_act1_on_runestone_repair
            # But we'll use a default of 3 if we can't determine it
            total_runestones = 3  # Default based on runestones_forest.json
        except Exception:
            total_runestones = 3
    
    # Check if forest_act1 dict exists, if not create it
    if not hasattr(state, "forest_act1") or state.forest_act1 is None:
        # Migrate from old fields if they exist
        state.forest_act1 = {
            "runestones_total": total_runestones if state.act1_total_runestones == 0 else state.act1_total_runestones,
            "runestones_repaired": state.act1_repaired_runestones,
            "first_repair_done": state.act1_repaired_runestones > 0,
            "completed": state.act1_forest_stabilized,
            "completion_acknowledged": False,
        }
    else:
        # Ensure all required fields exist
        state.forest_act1.setdefault("runestones_total", total_runestones if state.act1_total_runestones == 0 else state.act1_total_runestones)
        state.forest_act1.setdefault("runestones_repaired", state.act1_repaired_runestones)
        state.forest_act1.setdefault("first_repair_done", state.act1_repaired_runestones > 0)
        state.forest_act1.setdefault("completed", state.act1_forest_stabilized)
        state.forest_act1.setdefault("completion_acknowledged", False)
    
    # Sync old fields with new structure for backward compatibility
    _sync_to_legacy_fields(state)


def _sync_to_legacy_fields(state: GameState) -> None:
    """Sync forest_act1 dict to legacy flat fields for backward compatibility."""
    if not hasattr(state, "forest_act1") or state.forest_act1 is None:
        return
    
    act1 = state.forest_act1
    state.act1_quest_stage = 3 if act1.get("completed", False) else (2 if act1.get("first_repair_done", False) else (1 if act1.get("started", False) else 0))
    state.act1_total_runestones = act1.get("runestones_total", 0)
    state.act1_repaired_runestones = act1.get("runestones_repaired", 0)
    state.act1_forest_stabilized = act1.get("completed", False)


def update_forest_act1_on_runestone_found(
    state: GameState, stone_id: str, total_runestones: int
) -> None:
    """
    Update forest_act1 state when a runestone is discovered.
    
    Args:
        state: Current game state
        stone_id: ID of the discovered runestone
        total_runestones: Total number of runestones in the forest
    """
    init_forest_act1_state(state)
    
    act1 = state.forest_act1
    act1["started"] = True
    act1["runestones_total"] = total_runestones
    act1["first_runestone_found"] = True
    
    _sync_to_legacy_fields(state)


def update_forest_act1_on_runestone_repair(
    state: GameState, stone_id: str, total_runestones: int
) -> None:
    """
    Update forest_act1 state when a runestone is repaired.
    
    Args:
        state: Current game state
        stone_id: ID of the repaired runestone
        total_runestones: Total number of runestones in the forest
    """
    init_forest_act1_state(state)
    
    act1 = state.forest_act1
    act1["started"] = True
    act1["runestones_total"] = total_runestones
    
    # Count repaired runestones from state
    from .runestones import get_repaired_runestone_count
    repaired_count = get_repaired_runestone_count(state)
    act1["runestones_repaired"] = repaired_count
    act1["first_repair_done"] = repaired_count > 0
    
    # Check for completion
    was_completed = act1.get("completed", False)
    if repaired_count >= REQUIRED_ACT1_RUNESTONES and not was_completed:
        act1["completed"] = True
        # Set town_path_known flag when Act I completes
        if not hasattr(state, "flags"):
            state.flags = {}
        state.flags["town_path_known"] = True
    
    _sync_to_legacy_fields(state)


def is_forest_act1_complete(state: GameState) -> bool:
    """
    Check if Forest Act I is complete.
    
    Args:
        state: Current game state
        
    Returns:
        True if Act I is complete
    """
    init_forest_act1_state(state)
    return state.forest_act1.get("completed", False)


def get_forest_act1_progress_summary(state: GameState) -> Dict[str, str]:
    """
    Get a summary of Forest Act I progress for UI display.
    
    Args:
        state: Current game state
        
    Returns:
        Dictionary with "status" (X / Y stabilized or Stabilized) and
        "progress" (X/Y runestones repaired)
    """
    init_forest_act1_state(state)
    
    act1 = state.forest_act1
    repaired = act1.get("runestones_repaired", 0)
    total = act1.get("runestones_total", 0)
    completed = act1.get("completed", False)
    
    # Build status string per task requirements: "X / Y stabilized" or "Stabilized"
    if completed or (total > 0 and repaired >= total):
        status = "Stabilized"
    elif total > 0:
        status = f"{repaired} / {total} stabilized"
    elif repaired > 0:
        status = f"{repaired} stabilized"
    else:
        status = "0 stabilized"
    
    # Build progress string
    if total > 0:
        progress = f"{repaired}/{total} runestones repaired"
    elif repaired > 0:
        progress = f"{repaired} runestone{'s' if repaired > 1 else ''} repaired"
    else:
        progress = "No runestones repaired yet"
    
    return {
        "status": status,
        "progress": progress,
    }


def get_forest_stability_label(state: GameState) -> str:
    """
    Get a simple stability label for the forest.
    
    Args:
        state: Current game state
        
    Returns:
        One of: "Unstable", "Stabilizing", "Stabilized", "Act I complete"
    """
    summary = get_forest_act1_progress_summary(state)
    return summary["status"]


def get_threat_encounter_modifier(state: GameState) -> float:
    """
    Get modifier for threat encounter frequency based on Act I progress.
    
    Args:
        state: Current game state
        
    Returns:
        Multiplier for encounter frequency (1.0 = normal, <1.0 = reduced)
    """
    init_forest_act1_state(state)
    repaired = state.forest_act1.get("runestones_repaired", 0)
    
    if repaired >= REQUIRED_ACT1_RUNESTONES:
        # Act I complete: 15% reduction
        return 0.85
    elif repaired >= 2:
        # 2 repairs: 10% reduction
        return 0.90
    elif repaired >= 1:
        # 1 repair: 5% reduction
        return 0.95
    else:
        # No repairs: normal
        return 1.0


def get_forest_memory_modifier(state: GameState) -> float:
    """
    Get modifier for forest memory/wayfinding friendliness.
    
    Args:
        state: Current game state
        
    Returns:
        Multiplier for wayfinding success (1.0 = normal, >1.0 = improved)
    """
    init_forest_act1_state(state)
    repaired = state.forest_act1.get("runestones_repaired", 0)
    
    if repaired >= REQUIRED_ACT1_RUNESTONES:
        # Act I complete: 20% improvement
        return 1.20
    elif repaired >= 2:
        # 2 repairs: 15% improvement
        return 1.15
    elif repaired >= 1:
        # 1 repair: 10% improvement
        return 1.10
    else:
        # No repairs: normal
        return 1.0


def should_show_first_runestone_tip(state: GameState) -> bool:
    """
    Check if the first runestone discovery tip should be shown.
    
    Args:
        state: Current game state
        
    Returns:
        True if tip should be shown
    """
    init_forest_act1_state(state)
    act1 = state.forest_act1
    
    # Show tip if this is the first runestone found and tip hasn't been shown
    if act1.get("first_runestone_found", False) and not act1.get("first_tip_shown", False):
        act1["first_tip_shown"] = True
        return True
    return False


def mark_completion_acknowledged(state: GameState) -> None:
    """
    Mark that the Act I completion narrative has been acknowledged.
    
    Args:
        state: Current game state
    """
    init_forest_act1_state(state)
    state.forest_act1["completion_acknowledged"] = True


def should_show_completion_narrative(state: GameState) -> bool:
    """
    Check if Act I completion narrative should be shown.
    
    Args:
        state: Current game state
        
    Returns:
        True if completion narrative should be shown
    """
    init_forest_act1_state(state)
    act1 = state.forest_act1
    # Check if completed and not yet acknowledged
    if not act1.get("completed", False):
        return False
    # Use completion_acknowledged flag if it exists, otherwise check if we just completed
    if "completion_acknowledged" in act1:
        return not act1.get("completion_acknowledged", False)
    # If flag doesn't exist, show the narrative (first time completion)
    return True

