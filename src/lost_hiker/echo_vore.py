"""Echo vore mechanics - Phase 1: Safe Belly Shelter.

This module handles the limited, consensual, non-lethal vore mechanic for Echo,
triggered by hugging or booping when vore is enabled and rapport is high enough.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .encounter_outcomes import (
    EncounterOutcome,
    OutcomeContext,
    UI,
    resolve_encounter_outcome,
)
from .vore import is_vore_enabled, can_pred_swallow
from .rapport import get_rapport, get_rapport_tier

if TYPE_CHECKING:
    from .state import GameState

ECHO_ID = "echo"
# Vore gating: require "bonded" tier (rapport >= 4)
MIN_VORE_RAPPORT = 4
# Base vore trigger chances
BASE_HUG_VORE_CHANCE = 0.01  # 1% base
BASE_BOOP_VORE_CHANCE = 0.10  # 10% base
# Tension system
TENSION_INCREASE_PER_ACTION = 0.1  # Increase tension by this amount per hug/boop
TENSION_MAX = 2.0  # Maximum tension value
TENSION_DECAY_DAYS = 3  # Days for tension to decay back to zero
# Tension factor: each point of tension multiplies base chance by (1 + tension_factor)
# With max tension of 2.0, max multiplier is 1 + 2.0 = 3x base chance
TENSION_FACTOR = 1.0  # 1.0 means each point of tension doubles the chance


def can_echo_vore_trigger(state: GameState) -> bool:
    """
    Check if Echo vore can trigger (vore enabled + high enough rapport).
    
    Uses the centralized vore helper system.
    
    Args:
        state: Current game state
        
    Returns:
        True if vore conditions are met
    """
    return can_pred_swallow(state, ECHO_ID)


def update_echo_vore_tension(state: GameState, increase: bool = True) -> None:
    """
    Update Echo vore tension based on player actions.
    
    If increase is True, adds tension for the current action.
    If increase is False, applies decay if enough days have passed.
    
    Args:
        state: Current game state
        increase: If True, increase tension; if False, apply decay
    """
    if increase:
        # Increase tension for this action
        state.echo_vore_tension = min(
            TENSION_MAX,
            state.echo_vore_tension + TENSION_INCREASE_PER_ACTION
        )
        state.echo_last_vore_tension_day = state.day
    else:
        # Apply decay: reduce tension toward zero over TENSION_DECAY_DAYS
        if state.echo_last_vore_tension_day is None:
            return
        
        days_since_tension = state.day - state.echo_last_vore_tension_day
        if days_since_tension >= TENSION_DECAY_DAYS:
            # Fully decayed
            state.echo_vore_tension = 0.0
            state.echo_last_vore_tension_day = None
        elif days_since_tension > 0:
            # Partial decay: multiply by (remaining_days / total_days)
            remaining_days = TENSION_DECAY_DAYS - days_since_tension
            decay_factor = remaining_days / TENSION_DECAY_DAYS
            state.echo_vore_tension *= decay_factor


def get_effective_vore_chance(base_chance: float, state: GameState) -> float:
    """
    Calculate effective vore chance with tension modifier.
    
    Formula: base_chance * (1 + tension_factor * echo_vore_tension)
    
    Args:
        base_chance: Base vore chance (e.g., 0.01 for hug, 0.10 for boop)
        state: Current game state
        
    Returns:
        Effective vore chance with tension applied
    """
    tension_factor = 1.0 + (TENSION_FACTOR * state.echo_vore_tension)
    return min(1.0, base_chance * tension_factor)


def should_trigger_echo_vore(base_chance: float, state: GameState) -> bool:
    """
    Determine if Echo vore should trigger this action.
    
    Args:
        base_chance: Base vore chance for this action type
        state: Current game state
        
    Returns:
        True if vore should trigger
    """
    if not can_echo_vore_trigger(state):
        return False
    
    effective_chance = get_effective_vore_chance(base_chance, state)
    return random.random() < effective_chance


def trigger_echo_belly_shelter(
    state: GameState,
    ui: UI,
    entry_method: str = "hug",  # "hug" or "boop"
) -> None:
    """
    Trigger Echo belly shelter outcome.
    
    Moves the player to the belly area where they can interact with Echo.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
        entry_method: How the player entered ("hug" or "boop")
    """
    # Show swallow description
    swallow_text = (
        "Echo's coils wrap around you in a warm, protective embrace. "
        "She pulls you closer, and you feel her massive head draw near. "
        "Her jaws open gently—not a threat, but an invitation. "
        "You're enveloped in darkness, warmth, and a steady, rhythmic pressure. "
        "The world fades away, replaced by a sense of profound safety and belonging.\n"
    )
    ui.echo(swallow_text)
    
    # Set belly state with entry method tracking
    state.belly_state = {
        "predator_id": ECHO_ID,
        "mode": "shelter",
        "entry_method": entry_method,  # Track how player got here
        "entry_day": state.day,  # Track what day they entered
    }
    
    # Set sheltered flag (for "check sky" compatibility)
    state.is_sheltered = True
    
    # Move player to belly zone
    state.active_zone = "echo_belly"
    state.current_landmark = None
    
    # Show initial belly description
    ui.echo(
        "\nYou find yourself in a warm, dark space. "
        "Echo's presence surrounds you—gentle, protective, safe. "
        "The rhythmic pulse of her breathing is steady and calming.\n"
    )


def calculate_release_probability(state: GameState) -> float:
    """
    Calculate the probability that Echo will release the player when requested.
    
    Factors:
    - Entry method: hug = higher chance, boop = lower chance
    - Rapport: higher rapport = higher chance
    - Time held: longer = slightly higher chance
    
    Args:
        state: Current game state
        
    Returns:
        Probability between 0.0 and 1.0
    """
    if not state.belly_state or state.belly_state.get("predator_id") != ECHO_ID:
        return 0.0
    
    entry_method = state.belly_state.get("entry_method", "hug")
    rapport = get_rapport(state, ECHO_ID)
    
    # Base probability by entry method
    if entry_method == "hug":
        base_prob = 0.6  # 60% base for hugs
    else:  # boop
        base_prob = 0.2  # 20% base for boops
    
    # Rapport modifier: +0.05 per rapport point above 4
    rapport_bonus = max(0.0, (rapport - 4) * 0.05)
    
    # Time held modifier: +0.1 if held overnight
    entry_day = state.belly_state.get("entry_day", state.day)
    time_held_bonus = 0.1 if state.day > entry_day else 0.0
    
    total_prob = min(1.0, base_prob + rapport_bonus + time_held_bonus)
    return total_prob


def request_echo_release(state: GameState, ui: UI) -> bool:
    """
    Request that Echo release the player.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
        
    Returns:
        True if released, False if held
    """
    prob = calculate_release_probability(state)
    released = random.random() < prob
    
    if released:
        release_player_from_echo_belly(state, ui)
        return True
    else:
        # Echo holds the player
        rapport = get_rapport(state, ECHO_ID)
        if rapport >= 4:
            ui.echo(
                "[RADIO] A warm, contented pulse. Not yet. Stay a little longer. "
                "The radio thrums with gentle insistence—Echo wants to keep you safe a bit more.\n"
            )
        else:
            ui.echo(
                "[RADIO] A soft, steady pulse. The warmth around you tightens slightly, "
                "not in a threatening way, but clearly indicating you should stay. "
                "Echo isn't ready to let you go yet.\n"
            )
        return False


def release_player_from_echo_belly(state: GameState, ui: UI) -> None:
    """
    Release the player from Echo's belly and return them to the Glade.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
    """
    # Show release description
    release_text = (
        "Echo's warmth shifts around you, and you feel a gentle movement. "
        "Slowly, carefully, she releases you back into the Glade. "
        "You emerge into the open air, and Echo watches you with patient eyes, "
        "the radio emitting a soft, contented pulse. You feel well-rested and safe.\n"
    )
    ui.echo(release_text)
    
    # Move player back to Glade
    state.active_zone = "glade"
    state.current_landmark = None
    
    # Clear sheltered flag and belly state
    state.is_sheltered = False
    state.belly_state = None
    
    # Reset tension after successful swallow (prevents immediate retrigger)
    state.echo_vore_tension = 0.0
    state.echo_last_vore_tension_day = None

