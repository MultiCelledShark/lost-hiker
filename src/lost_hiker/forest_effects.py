"""Forest-wide effects based on runestone repair progress for Lost Hiker."""

from __future__ import annotations

from typing import Dict

from .state import GameState


def get_stamina_cost_modifier(state: GameState, depth: int) -> float:
    """
    Get stamina cost modifier based on runestone repair progress.
    
    Args:
        state: Current game state
        depth: Current exploration depth
        
    Returns:
        Multiplier for stamina costs (1.0 = normal, <1.0 = reduced cost)
    """
    from .forest_act1 import init_forest_act1_state
    init_forest_act1_state(state)
    repaired = state.forest_act1.get("runestones_repaired", 0) if state.forest_act1 else state.act1_repaired_runestones
    
    # Base modifier: no change at 0 repairs
    if repaired == 0:
        return 1.0
    
    # Slight reduction with 1 repair (only for deeper depths)
    if repaired == 1:
        if depth >= 10:
            return 0.95  # 5% reduction for mid-depth and deeper
        return 1.0
    
    # More noticeable reduction with 2 repairs
    if repaired == 2:
        if depth >= 10:
            return 0.90  # 10% reduction for mid-depth and deeper
        elif depth >= 5:
            return 0.95  # 5% reduction for early mid-depth
        return 1.0
    
    # Maximum benefit with 3 repairs
    if repaired >= 3:
        if depth >= 15:
            return 0.85  # 15% reduction for deep depths
        elif depth >= 10:
            return 0.90  # 10% reduction for mid-depth
        elif depth >= 5:
            return 0.95  # 5% reduction for early mid-depth
        return 1.0
    
    return 1.0


def get_event_category_weights(state: GameState, depth_band: str) -> Dict[str, float]:
    """
    Get modified event category weights based on runestone repair progress.
    
    Args:
        state: Current game state
        depth_band: Current depth band ("edge", "mid", "deep")
        
    Returns:
        Dictionary of category weights (will be merged with base weights)
    """
    from .forest_act1 import init_forest_act1_state, get_threat_encounter_modifier
    init_forest_act1_state(state)
    repaired = state.forest_act1.get("runestones_repaired", 0) if state.forest_act1 else state.act1_repaired_runestones
    
    # Base weights (no modification)
    if repaired == 0:
        return {}
    
    # With repairs, slightly favor safer events
    modifiers: Dict[str, float] = {}
    
    if repaired == 1:
        # Subtle shift: slightly more forage/neutral, slightly less hazard
        modifiers = {
            "forage": 1.05,
            "flavor": 1.05,
            "hazard": 0.95,
            "encounter": 0.98,
        }
    elif repaired == 2:
        # More noticeable shift
        modifiers = {
            "forage": 1.10,
            "flavor": 1.10,
            "hazard": 0.90,
            "encounter": 0.95,
            "boon": 1.05,
        }
    elif repaired >= 3:
        # Maximum benefit: forest feels clearly safer
        modifiers = {
            "forage": 1.15,
            "flavor": 1.15,
            "hazard": 0.85,
            "encounter": 0.92,
            "boon": 1.10,
        }
    
    # Apply depth band scaling (effects are stronger in deeper areas)
    if depth_band == "deep":
        # Amplify effects in deep areas
        for key in modifiers:
            if key in ("forage", "flavor", "boon"):
                modifiers[key] = min(1.3, modifiers[key] * 1.1)
            elif key in ("hazard", "encounter"):
                modifiers[key] = max(0.75, modifiers[key] * 0.95)
    elif depth_band == "mid":
        # Moderate effects in mid areas
        pass  # Use modifiers as-is
    else:  # edge
        # Subtle effects in edge areas (already safer)
        for key in modifiers:
            modifiers[key] = 1.0 + (modifiers[key] - 1.0) * 0.5
    
    return modifiers


def get_max_reliable_depth(state: GameState) -> int:
    """
    Get the maximum depth the player can reliably reach based on runestone repairs.
    
    This is a soft gate - deeper depths are still possible but much rarer.
    
    Args:
        state: Current game state
        
    Returns:
        Maximum reliable depth (deeper depths still possible but rare)
    """
    from .forest_act1 import init_forest_act1_state
    init_forest_act1_state(state)
    repaired = state.forest_act1.get("runestones_repaired", 0) if state.forest_act1 else state.act1_repaired_runestones
    
    if repaired == 0:
        # Very limited deep-depth access
        return 15
    elif repaired == 1:
        # Slightly deeper access
        return 20
    elif repaired == 2:
        # Deeper mid-depths accessible
        return 25
    else:  # repaired >= 3
        # Full Act I depth range accessible
        return 35


def should_allow_deep_depth_roll(state: GameState, depth: int) -> bool:
    """
    Check if a deep depth roll should be allowed based on repair progress.
    
    Args:
        state: Current game state
        depth: Target depth
        
    Returns:
        True if deep depth should be accessible
    """
    max_reliable = get_max_reliable_depth(state)
    
    # Always allow depths within reliable range
    if depth <= max_reliable:
        return True
    
    # Beyond reliable range: heavily reduce chance
    # This is a soft gate - still possible but rare
    import random
    excess = depth - max_reliable
    if excess <= 5:
        # Just beyond: 20% chance
        return random.random() < 0.2
    elif excess <= 10:
        # Further beyond: 5% chance
        return random.random() < 0.05
    else:
        # Way beyond: 1% chance
        return random.random() < 0.01

