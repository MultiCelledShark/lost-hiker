"""Central vore configuration and helper functions for Lost Hiker.

This module provides a unified API for checking vore-related settings and gating
logic. All vore logic throughout the game should use these helpers rather than
directly accessing state settings.
"""

from __future__ import annotations

from typing import Optional

from .state import GameState
from .rapport import get_rapport, get_rapport_tier

# Predator-specific rapport thresholds for vore gating
ECHO_ID = "echo"
KIRIN_ID = "kirin"
ECHO_MIN_VORE_RAPPORT = 4  # "bonded" tier or rapport >= 4
KIRIN_MIN_VORE_RAPPORT = 2  # "friendly" tier or rapport >= 2


def is_vore_enabled(state: GameState) -> bool:
    """
    Check if vore content is enabled for this run.
    
    Args:
        state: Current game state
        
    Returns:
        True if vore is enabled
    """
    return state.vore_enabled


def is_player_pred_enabled(state: GameState) -> bool:
    """
    Check if player-as-predator content is enabled for this run.
    
    Args:
        state: Current game state
        
    Returns:
        True if player-as-predator is enabled
    """
    return state.player_as_pred_enabled


def can_pred_swallow(
    state: GameState,
    predator_id: str,
    prey_id: Optional[str] = None,
) -> bool:
    """
    Check if a predator can swallow prey in the current context.
    
    This function checks:
    - vore_enabled must be True
    - For player-as-predator, player_as_pred_enabled must also be True
    - Rapport thresholds for specific predators (Echo, Kirin, etc.)
    
    Args:
        state: Current game state
        predator_id: ID of the predator (e.g., "echo", "kirin", "player")
        prey_id: Optional ID of the prey (currently unused but reserved for future use)
        
    Returns:
        True if the predator can swallow in this context
    """
    # Vore must be enabled
    if not is_vore_enabled(state):
        return False
    
    # For player-as-predator, check player_as_pred_enabled
    if predator_id == "player":
        return is_player_pred_enabled(state)
    
    # For Echo, check rapport threshold
    if predator_id == ECHO_ID:
        rapport = get_rapport(state, ECHO_ID)
        rapport_tier = get_rapport_tier(rapport)
        return rapport >= ECHO_MIN_VORE_RAPPORT or rapport_tier == "bonded"
    
    # For Kirin, check rapport threshold
    if predator_id == KIRIN_ID:
        rapport = get_rapport(state, KIRIN_ID)
        rapport_tier = get_rapport_tier(rapport)
        return rapport >= KIRIN_MIN_VORE_RAPPORT or rapport_tier in ("friendly", "bonded")
    
    # For other predators (wild creatures), allow if vore is enabled
    # Individual encounters may add additional checks (e.g., depth, condition, etc.)
    return True


def is_vore_allowed_in_context(
    state: GameState,
    context: Optional[str] = None,
) -> bool:
    """
    Check if vore is allowed in the current game context.
    
    This function respects things like:
    - Current location (camp vs wild)
    - Current outcome type (threat vs friendly)
    - Rapport tiers
    
    Args:
        state: Current game state
        context: Optional context string (e.g., "camp", "threat", "friendly", "wild")
        
    Returns:
        True if vore is allowed in this context
    """
    # Vore must be enabled
    if not is_vore_enabled(state):
        return False
    
    # If context is provided, check context-specific rules
    if context:
        # Vore is generally allowed at camp (for friendly creatures like Echo)
        if context == "camp":
            return True
        
        # Vore is allowed in threat encounters if enabled (for predator encounters)
        if context == "threat":
            return True
        
        # Vore is allowed in friendly encounters if enabled
        if context == "friendly":
            return True
        
        # Vore is allowed in wild encounters if enabled
        if context == "wild":
            return True
    
    # Default: allow if vore is enabled
    return True

