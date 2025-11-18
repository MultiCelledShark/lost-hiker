"""Forest memory system: path stability and landmark recall for Lost Hiker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .state import GameState

if TYPE_CHECKING:
    from .landmarks import Landmark, LandmarkCatalog


def init_landmark_memory(state: GameState) -> None:
    """Initialize landmark memory if not present in state."""
    if not hasattr(state, "landmark_stability"):
        state.landmark_stability = {}
    # Ensure all discovered landmarks have at least stability 1
    for landmark_id in state.discovered_landmarks:
        if landmark_id not in state.landmark_stability:
            state.landmark_stability[landmark_id] = 1


def get_path_stability(state: GameState, landmark_id: str) -> int:
    """
    Get the path stability for a landmark.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark
        
    Returns:
        Stability value (0-3): 0=unknown, 1=faint, 2=familiar, 3=well-worn
    """
    if not hasattr(state, "landmark_stability"):
        state.landmark_stability = {}
    return state.landmark_stability.get(landmark_id, 0)


def bump_path_stability(state: GameState, landmark_id: str) -> None:
    """
    Increase path stability for a landmark on revisit.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark being revisited
    """
    if not hasattr(state, "landmark_stability"):
        state.landmark_stability = {}
    current = state.landmark_stability.get(landmark_id, 0)
    # Increase stability up to max of 3
    if current < 3:
        state.landmark_stability[landmark_id] = current + 1
    else:
        state.landmark_stability[landmark_id] = 3


def ensure_minimum_stability(state: GameState, landmark_id: str, minimum: int) -> None:
    """
    Ensure a landmark has at least a minimum stability value.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark
        minimum: Minimum stability value to ensure
    """
    if not hasattr(state, "landmark_stability"):
        state.landmark_stability = {}
    current = state.landmark_stability.get(landmark_id, 0)
    if current < minimum:
        state.landmark_stability[landmark_id] = minimum


def get_stability_label(stability: int) -> str:
    """
    Get a human-readable label for a stability value.
    
    Args:
        stability: Stability value (0-3)
        
    Returns:
        Label string
    """
    labels = {
        0: "unknown",
        1: "faint path",
        2: "familiar path",
        3: "well-worn path",
    }
    return labels.get(stability, "unknown")


def adjust_landmark_weights_based_on_memory(
    state: GameState,
    candidate_landmarks: List[Landmark],
    context: Optional[Dict[str, object]] = None,
) -> List[float]:
    """
    Adjust landmark selection weights based on path stability and context.
    
    Args:
        state: Current game state
        candidate_landmarks: List of candidate landmarks to weight
        context: Optional context dict with keys like:
            - "hungry": bool (player is hungry)
            - "has_mortar": bool (player has mortar or ingredients)
            - "day": int (current day, for runestone discovery bias)
            - "has_runestone_landmark": bool (player has discovered a runestone landmark)
        
    Returns:
        List of weights corresponding to candidate_landmarks
    """
    if not candidate_landmarks:
        return []
    
    if context is None:
        context = {}
    
    weights = []
    for landmark in candidate_landmarks:
        weight = 1.0
        stability = get_path_stability(state, landmark.landmark_id)
        
        # Base weight from stability: higher stability = higher weight
        # Stability 0 (unknown) gets base weight 1.0
        # Stability 1 (faint) gets 1.2x
        # Stability 2 (familiar) gets 1.5x
        # Stability 3 (well-worn) gets 2.0x
        stability_multipliers = {
            0: 1.0,
            1: 1.2,
            2: 1.5,
            3: 2.0,
        }
        weight *= stability_multipliers.get(stability, 1.0)
        
        # Context-sensitive biasing
        
        # If hungry, favor food-capable landmarks
        if context.get("hungry", False) and landmark.features.get("has_food", False):
            weight *= 2.5
        
        # If player has mortar/ingredients, favor runestone landmarks
        if context.get("has_mortar", False) and landmark.features.get("has_runestone", False):
            weight *= 2.0
        
        # If approaching day 10 without finding a runestone, favor runestone landmarks
        day = context.get("day", 0)
        has_runestone_landmark = context.get("has_runestone_landmark", False)
        if not has_runestone_landmark and day >= 8 and landmark.features.get("has_runestone", False):
            # Gradual increase as day approaches 10
            day_bias = 1.0 + (min(day - 8, 2) * 0.25)  # 1.0 at day 8, 1.5 at day 10+
            weight *= day_bias
        
        # As more runestones are repaired, slightly increase weight for higher-stability landmarks
        from .forest_act1 import init_forest_act1_state, get_forest_memory_modifier
        init_forest_act1_state(state)
        repaired_count = state.forest_act1.get("runestones_repaired", 0) if state.forest_act1 else state.act1_repaired_runestones
        if repaired_count > 0 and stability > 0:
            # Use forest memory modifier from forest_act1
            memory_modifier = get_forest_memory_modifier(state)
            weight *= memory_modifier
        
        weights.append(weight)
    
    return weights


def get_known_landmarks_with_stability(
    state: GameState,
    landmark_catalog: LandmarkCatalog,
) -> List[Tuple[Landmark, int]]:
    """
    Get all known landmarks with their stability values.
    
    Args:
        state: Current game state
        landmark_catalog: Catalog to look up landmarks
        
    Returns:
        List of (landmark, stability) tuples, sorted by name
    """
    known = []
    for landmark_id in state.discovered_landmarks:
        landmark = landmark_catalog.get(landmark_id)
        if landmark:
            stability = get_path_stability(state, landmark_id)
            known.append((landmark, stability))
    
    # Sort by name for consistent display
    known.sort(key=lambda x: x[0].name)
    return known

