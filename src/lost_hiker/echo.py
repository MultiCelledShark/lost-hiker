"""Echo-specific helper functions for camp interactions and presence tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .state import GameState
from .rapport import get_rapport, change_rapport, RAPPORT_MAX

if TYPE_CHECKING:
    from .echo_vore import BASE_BOOP_VORE_CHANCE, BASE_HUG_VORE_CHANCE

ECHO_ID = "echo"


def is_echo_present_at_glade(state: GameState) -> bool:
    """
    Check if Echo is present at the Glade.
    
    Args:
        state: The game state
        
    Returns:
        True if Echo is present at the Glade, False otherwise
    """
    # Echo is present by default unless story logic explicitly removes her
    return state.echo_present_at_glade


def get_echo_rapport(state: GameState) -> int:
    """
    Get Echo's current rapport score.
    
    Args:
        state: The game state
        
    Returns:
        Echo's rapport score (defaults to 0 if not set)
    """
    return get_rapport(state, ECHO_ID)


def change_echo_rapport(state: GameState, delta: int) -> int:
    """
    Change Echo's rapport by a delta amount, clamping to valid range.
    
    Args:
        state: The game state
        delta: The amount to change rapport by (can be negative)
        
    Returns:
        The new rapport score after the change
    """
    return change_rapport(state, ECHO_ID, delta)


def can_pet_echo_today(state: GameState) -> bool:
    """
    Check if the player can pet Echo for rapport gain today.
    
    Args:
        state: The game state
        
    Returns:
        True if the player hasn't petted Echo today (or hasn't gotten the daily bonus)
    """
    last_pet_day = state.echo_last_pet_day
    return last_pet_day is None or last_pet_day < state.day


def pet_echo(state: GameState) -> tuple[str, bool]:
    """
    Handle petting Echo interaction.
    
    Args:
        state: The game state
        
    Returns:
        Tuple of (description_text, gained_rapport)
        - description_text: The flavor text for petting Echo
        - gained_rapport: True if rapport was gained, False if already petted today
    """
    current_rapport = get_echo_rapport(state)
    
    # Check if we can gain rapport today
    can_gain = can_pet_echo_today(state) and current_rapport < RAPPORT_MAX
    
    if can_gain:
        # Gain rapport
        change_echo_rapport(state, 1)
        state.echo_last_pet_day = state.day
        
        # Generate description based on rapport tier
        if current_rapport < 0:
            description = "Echo tenses slightly at your touch, scales cool and guarded. The radio emits a low, uncertain hum."
        elif current_rapport < 2:
            description = "Echo's scales warm under your hand, and a soft pulse of static flows through the radio—curious, testing."
        elif current_rapport < 4:
            description = "Echo coils closer, pressing into your touch with a contented hiss. The radio thrums with warm, steady static."
        else:
            description = "Echo leans into your hand, massive coils shifting to give you better access. The radio sings with deep, resonant warmth—clearly bonded."
        
        return description, True
    else:
        # Already petted today or at max rapport
        if current_rapport >= RAPPORT_MAX:
            description = "Echo presses against your hand with deep contentment, but you sense the bond has reached its peak. The radio hums with steady, satisfied warmth."
        else:
            description = "Echo enjoys the attention, but you've already shared this moment today. The radio emits a gentle, familiar pulse."
        
        return description, False


def has_echo_radio_hint_been_shown(state: GameState) -> bool:
    """
    Check if the Echo-HT radio connection hint has been shown.
    
    Args:
        state: The game state
        
    Returns:
        True if the hint has been shown, False otherwise
    """
    return state.echo_radio_connection_hint_shown


def set_echo_radio_hint_shown(state: GameState) -> None:
    """
    Mark that the Echo-HT radio connection hint has been shown.
    
    Args:
        state: The game state
    """
    state.echo_radio_connection_hint_shown = True


def hug_echo(state: GameState) -> tuple[str, bool, bool, str]:
    """
    Handle hugging Echo interaction - a warm, heartfelt action.
    
    Args:
        state: The game state
        
    Returns:
        Tuple of (description_text, gained_rapport, vore_triggered, entry_method)
        - description_text: The flavor text for hugging Echo
        - gained_rapport: True if rapport was gained, False otherwise
        - vore_triggered: True if vore should trigger (caller must handle)
        - entry_method: "hug" or "boop" (for release probability)
    """
    from .echo_vore import (
        BASE_HUG_VORE_CHANCE,
        can_echo_vore_trigger,
        should_trigger_echo_vore,
        update_echo_vore_tension,
    )
    
    current_rapport = get_echo_rapport(state)
    
    # Update vore tension if enabled
    vore_triggered = False
    entry_method = "hug"  # Track entry method for release probability
    if can_echo_vore_trigger(state):
        update_echo_vore_tension(state, increase=True)
        # Check if vore should trigger (1% base chance, modified by tension)
        if should_trigger_echo_vore(BASE_HUG_VORE_CHANCE, state):
            vore_triggered = True
            entry_method = "hug"
            # Return early if vore triggers - caller will handle the vore outcome
            return "", False, True, entry_method
    
    # Hugging can gain rapport, but less frequently than petting
    # Check if we can gain rapport (hugging has its own tracking or can share pet day)
    can_gain = current_rapport < RAPPORT_MAX
    
    if can_gain and current_rapport >= 2:  # Hugging requires some rapport first
        # Gain rapport (hugging is more meaningful, so +1)
        change_echo_rapport(state, 1)
        
        # Generate description based on rapport tier
        if current_rapport < 3:
            description = "You wrap your arms around Echo's massive coils. She tenses for a moment, then relaxes, pressing back with gentle warmth. The radio thrums with surprised but pleased static—this is new, but welcome."
        elif current_rapport < 5:
            description = "Echo's coils wrap around you in return, a warm, protective embrace. The radio sings with deep contentment, and you feel a profound sense of connection. This is home."
        else:
            description = "Echo's embrace is familiar now, but no less meaningful. Her coils hold you close, and the radio pulses with steady, loving warmth. You are bonded, and this moment of closeness reaffirms that bond."
        
        return description, True, False, "hug"
    elif current_rapport < 2:
        description = "You move to hug Echo, but she pulls back slightly, scales cool with uncertainty. The radio emits a cautious pulse. Perhaps you need to build more trust first."
        return description, False, False, "hug"
    else:
        # At max rapport, still meaningful but no further gain
        description = "Echo's embrace is warm and familiar. The radio hums with deep contentment. Your bond is as strong as it can be, and this moment of closeness is its own reward."
        return description, False, False, "hug"


def boop_echo(state: GameState) -> tuple[str, bool, bool, str]:
    """
    Handle booping Echo interaction - a playful action.
    
    Args:
        state: The game state
        
    Returns:
        Tuple of (description_text, gained_rapport, vore_triggered, entry_method)
        - description_text: The flavor text for booping Echo
        - gained_rapport: True if rapport was gained, False otherwise
        - vore_triggered: True if vore should trigger (caller must handle)
        - entry_method: "hug" or "boop" (for release probability)
    """
    from .echo_vore import (
        BASE_BOOP_VORE_CHANCE,
        can_echo_vore_trigger,
        should_trigger_echo_vore,
        update_echo_vore_tension,
    )
    
    current_rapport = get_echo_rapport(state)
    
    # Update vore tension if enabled
    vore_triggered = False
    entry_method = "boop"  # Track entry method for release probability
    if can_echo_vore_trigger(state):
        update_echo_vore_tension(state, increase=True)
        # Check if vore should trigger (10% base chance, modified by tension)
        if should_trigger_echo_vore(BASE_BOOP_VORE_CHANCE, state):
            vore_triggered = True
            entry_method = "boop"
            # Return early if vore triggers - caller will handle the vore outcome
            return "", False, True, entry_method
    
    # Booping is playful and can gain rapport, but only if rapport is already positive
    can_gain = current_rapport >= 1 and current_rapport < RAPPORT_MAX
    
    if can_gain:
        # Gain rapport (booping is playful, so smaller gain)
        change_echo_rapport(state, 1)
        
        # Generate description based on rapport tier
        if current_rapport < 2:
            description = "You gently boop Echo's snout. She blinks, then lets out a soft, surprised hiss. The radio crackles with amusement—playful static dancing across the speaker. She seems to enjoy this."
        elif current_rapport < 4:
            description = "You boop Echo's snout playfully. She responds by nudging you back with her head, a gentle push that's clearly meant as a game. The radio thrums with laughter-like static, and you both share a moment of lighthearted connection."
        else:
            description = "You boop Echo's snout, and she immediately responds with a playful coil-wrap, gently squeezing you before releasing. The radio sings with delighted static—this is a familiar game between you, and it never gets old."
        
        return description, True, False, "boop"
    elif current_rapport < 1:
        description = "You reach out to boop Echo, but she pulls back, scales cool. The radio emits a low, uncertain hum. She's not ready for playful interactions yet."
        return description, False, False, "boop"
    else:
        # At max rapport, still playful but no further gain
        description = "You boop Echo's snout, and she responds with the same playful energy as always. The radio crackles with familiar amusement. Your bond is at its peak, but the joy of this simple game remains."
        return description, False, False, "boop"

