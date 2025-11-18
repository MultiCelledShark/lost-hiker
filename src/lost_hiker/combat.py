"""Threat encounter system for hostile forest creatures."""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from .state import GameState
from .rapport import get_rapport, change_rapport


# Condition/strain constants
CONDITION_MIN = 0
CONDITION_MAX = 3

CONDITION_LABELS = {
    0: "fine",
    1: "bruised",
    2: "battered",
    3: "near collapse",
}


def get_condition_label(condition: int) -> str:
    """Get a human-readable label for condition level."""
    return CONDITION_LABELS.get(condition, "fine")


def change_condition(state: GameState, delta: int) -> int:
    """
    Change condition by a delta amount, clamping to valid range.
    
    Args:
        state: The game state
        delta: The amount to change condition by (can be negative)
        
    Returns:
        The new condition value after the change
    """
    current = state.condition
    new_value = current + delta
    clamped = max(CONDITION_MIN, min(CONDITION_MAX, new_value))
    state.condition = clamped
    return clamped


def get_condition_effects(state: GameState) -> Dict[str, float]:
    """
    Get effects of current condition on player stats.
    
    Returns:
        Dictionary with effect multipliers/penalties
    """
    condition = state.condition
    effects = {
        "stamina_cap_reduction": 0.0,  # Percentage reduction in max stamina
        "collapse_risk_multiplier": 1.0,  # Multiplier for collapse chance
    }
    
    if condition >= 3:
        effects["stamina_cap_reduction"] = 0.15  # 15% reduction at max condition
        effects["collapse_risk_multiplier"] = 2.0
    elif condition >= 2:
        effects["stamina_cap_reduction"] = 0.10  # 10% reduction
        effects["collapse_risk_multiplier"] = 1.5
    elif condition >= 1:
        effects["stamina_cap_reduction"] = 0.05  # 5% reduction
        effects["collapse_risk_multiplier"] = 1.2
    
    return effects


def recover_condition_at_camp(state: GameState) -> int:
    """
    Recover condition when resting at camp (Glade).
    
    Reduces condition by 1 if condition > 0.
    
    Args:
        state: The game state
        
    Returns:
        The new condition value
    """
    if state.condition > 0:
        return change_condition(state, -1)
    return state.condition


def should_force_retreat(state: GameState) -> bool:
    """
    Check if condition is high enough to force a retreat/blackout.
    
    Args:
        state: The game state
        
    Returns:
        True if player should be forced to retreat
    """
    return state.condition >= 3 and state.stamina <= 0.5


def calculate_flee_success(
    state: GameState,
    creature_id: str,
    depth: int,
    stamina_ratio: float,
) -> bool:
    """
    Calculate if a flee attempt succeeds.
    
    Args:
        state: The game state
        creature_id: The creature being fled from
        depth: Current depth in forest
        stamina_ratio: Current stamina / max stamina
        
    Returns:
        True if flee succeeds
    """
    # Base success chance
    base_chance = 0.6
    
    # Higher stamina = better chance
    stamina_bonus = stamina_ratio * 0.3
    
    # Lower depth = easier to escape
    depth_penalty = min(0.2, depth * 0.01)
    
    # Rapport can help (if positive) or hurt (if negative)
    rapport = get_rapport(state, creature_id)
    rapport_modifier = rapport * 0.05
    
    final_chance = base_chance + stamina_bonus - depth_penalty + rapport_modifier
    final_chance = max(0.2, min(0.9, final_chance))  # Clamp between 20% and 90%
    
    return random.random() < final_chance


def calculate_calm_success(
    state: GameState,
    creature_id: str,
    has_food: bool,
) -> bool:
    """
    Calculate if a calm/appease attempt succeeds.
    
    Args:
        state: The game state
        creature_id: The creature being calmed
        has_food: Whether player has food to offer
        
    Returns:
        True if calm succeeds
    """
    # Base success chance
    base_chance = 0.4
    
    # Food offering significantly helps
    food_bonus = 0.3 if has_food else 0.0
    
    # Rapport helps
    rapport = get_rapport(state, creature_id)
    rapport_modifier = rapport * 0.08
    
    final_chance = base_chance + food_bonus + rapport_modifier
    final_chance = max(0.15, min(0.85, final_chance))  # Clamp between 15% and 85%
    
    return random.random() < final_chance


def calculate_stand_ground_success(
    state: GameState,
    creature_id: str,
    stamina_ratio: float,
) -> bool:
    """
    Calculate if standing ground succeeds (higher risk, higher reward).
    
    Args:
        state: The game state
        creature_id: The creature being faced
        stamina_ratio: Current stamina / max stamina
        
    Returns:
        True if stand ground succeeds
    """
    # Lower base chance (riskier)
    base_chance = 0.35
    
    # Higher stamina helps
    stamina_bonus = stamina_ratio * 0.25
    
    # Rapport helps significantly
    rapport = get_rapport(state, creature_id)
    rapport_modifier = rapport * 0.1
    
    final_chance = base_chance + stamina_bonus + rapport_modifier
    final_chance = max(0.2, min(0.8, final_chance))  # Clamp between 20% and 80%
    
    return random.random() < final_chance

