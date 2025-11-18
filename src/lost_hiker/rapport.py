"""Generic rapport system for tracking relationships with creatures and NPCs."""

from __future__ import annotations

from typing import Dict

from .state import GameState

# Rapport score range
RAPPORT_MIN = -5
RAPPORT_MAX = 5
RAPPORT_NEUTRAL = 0


def get_rapport(state: GameState, creature_id: str) -> int:
    """
    Get the current rapport score for a creature or NPC.
    
    Args:
        state: The game state
        creature_id: The ID of the creature or NPC
        
    Returns:
        The rapport score (defaults to 0 if not set)
    """
    return state.rapport.get(creature_id, RAPPORT_NEUTRAL)


def change_rapport(state: GameState, creature_id: str, delta: int) -> int:
    """
    Change rapport by a delta amount, clamping to valid range.
    
    Args:
        state: The game state
        creature_id: The ID of the creature or NPC
        delta: The amount to change rapport by (can be negative)
        
    Returns:
        The new rapport score after the change
    """
    current = get_rapport(state, creature_id)
    new_value = current + delta
    clamped = max(RAPPORT_MIN, min(RAPPORT_MAX, new_value))
    state.rapport[creature_id] = clamped
    return clamped


def get_rapport_tier(score: int) -> str:
    """
    Convert a numeric rapport score into a tier label.
    
    Args:
        score: The rapport score
        
    Returns:
        A tier label: "hostile", "wary", "neutral", "friendly", or "bonded"
    """
    if score <= -3:
        return "hostile"
    elif score <= -1:
        return "wary"
    elif score <= 1:
        return "neutral"
    elif score <= 3:
        return "friendly"
    else:
        return "bonded"

