"""Echo-specific helper functions for camp interactions and presence tracking."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .state import GameState
from .rapport import get_rapport, change_rapport, RAPPORT_MAX
from .vore import is_vore_enabled

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
    vore_on = is_vore_enabled(state)
    
    # Check if we can gain rapport today
    can_gain = can_pet_echo_today(state) and current_rapport < RAPPORT_MAX
    
    if can_gain:
        # Gain rapport
        change_echo_rapport(state, 1)
        state.echo_last_pet_day = state.day
        
        # Variant pools organized by rapport tier
        # Low rapport (negative or very low)
        low_rapport_variants = [
            "Echo tenses slightly at your touch, scales cool and guarded. The radio emits a low, uncertain hum.",
            "Your hand meets Echo's side, and she pulls back just a fraction. The radio crackles with caution—not rejection, but wariness.",
            "Echo's scales feel cold under your palm. She watches you carefully, and the radio hums a questioning note.",
        ]
        
        # Medium-low rapport (0-1)
        medium_low_variants = [
            "Echo's scales warm under your hand, and a soft pulse of static flows through the radio—curious, testing.",
            "You run your hand along Echo's side. Her scales begin to warm, and the radio thrums with a tentative, hopeful note.",
            "Echo shifts slightly, allowing your touch. The radio emits a gentle pulse—cautious acceptance, slowly building trust.",
        ]
        
        # Medium rapport (2-3)
        medium_rapport_variants = [
            "Echo coils closer, pressing into your touch with a contented hiss. The radio thrums with warm, steady static.",
            "Echo's tail thumps softly against the ground as you pet her. She leans into your hand, and the radio sings with gentle warmth.",
            "You stroke Echo's scales, and she responds with a low, rumbling vibration. The radio pulses with contentment—this is familiar, comfortable.",
            "Echo relaxes under your touch, coils shifting to press closer. The radio emits a steady, satisfied hum.",
        ]
        
        # High rapport (4+)
        high_rapport_variants = [
            "Echo leans into your hand, massive coils shifting to give you better access. The radio sings with deep, resonant warmth—clearly bonded.",
            "Echo presses against your hand with obvious delight, tail thumping rhythmically. The radio thrums with deep, loving static—you've built something special here.",
            "Echo's coils wrap closer as you pet her, protective and warm. The radio pulses with fondness, and you feel completely at ease.",
        ]
        
        # Select variant pool based on rapport
        if current_rapport < 0:
            variants = low_rapport_variants
        elif current_rapport < 2:
            variants = medium_low_variants
        elif current_rapport < 4:
            variants = medium_rapport_variants
        else:
            variants = high_rapport_variants
        
        # Rotate variant to avoid repeats
        last_variant = state.echo_last_pet_variant
        available_indices = [i for i in range(len(variants)) if i != last_variant]
        if available_indices:
            variant_idx = random.choice(available_indices)
        else:
            variant_idx = random.randint(0, len(variants) - 1)
        state.echo_last_pet_variant = variant_idx
        
        description = variants[variant_idx]
        
        # Add rapport-based conditional lines
        if current_rapport >= 4:
            rapport_lines = [
                " Her coils tighten protectively around you.",
                " You feel her deep contentment in the way she presses closer.",
            ]
            if random.random() < 0.4:  # 40% chance to add extra line
                description += random.choice(rapport_lines)
        elif current_rapport >= 2:
            rapport_lines = [
                " She seems to be warming up to you.",
                " The connection between you grows stronger.",
            ]
            if random.random() < 0.3:  # 30% chance
                description += random.choice(rapport_lines)
        
        # Add vore hints if enabled (very subtle, occasional)
        if vore_on and current_rapport >= 2 and random.random() < 0.15:  # 15% chance
            vore_hints = [
                " For a moment, her gaze lingers on you like you're something precious—or perhaps delicious. She blinks, and the moment passes.",
                " There's a playful glint in her eye, and you catch her sizing you up before she shakes her head with what could be amusement.",
            ]
            description += random.choice(vore_hints)
        
        return description, True
    else:
        # Already petted today or at max rapport - use variants for repeat interactions
        if current_rapport >= RAPPORT_MAX:
            max_rapport_variants = [
                "Echo presses against your hand with deep contentment, but you sense the bond has reached its peak. The radio hums with steady, satisfied warmth.",
                "You stroke Echo's scales again, and she responds with familiar warmth. The bond between you is as strong as it can be—this moment is its own reward.",
                "Echo leans into your touch, the radio singing with deep satisfaction. Your connection is complete, and each gentle moment reaffirms it.",
            ]
            # Rotate variant
            last_variant = state.echo_last_pet_variant
            available_indices = [i for i in range(len(max_rapport_variants)) if i != last_variant % len(max_rapport_variants)]
            if available_indices:
                variant_idx = available_indices[0]
            else:
                variant_idx = random.randint(0, len(max_rapport_variants) - 1)
            state.echo_last_pet_variant = variant_idx
            description = max_rapport_variants[variant_idx]
        else:
            repeat_variants = [
                "Echo enjoys the attention, but you've already shared this moment today. The radio emits a gentle, familiar pulse.",
                "You pet Echo again, and she responds with warmth, though the deeper connection comes from that first touch each day. The radio hums softly.",
                "Echo's scales are warm under your hand. She appreciates the extra attention, but you sense today's meaningful moment has already passed.",
            ]
            # Rotate variant
            last_variant = state.echo_last_pet_variant
            available_indices = [i for i in range(len(repeat_variants)) if i != last_variant % len(repeat_variants)]
            if available_indices:
                variant_idx = available_indices[0]
            else:
                variant_idx = random.randint(0, len(repeat_variants) - 1)
            state.echo_last_pet_variant = variant_idx
            description = repeat_variants[variant_idx]
        
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
    vore_on = is_vore_enabled(state)
    
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
        
        # Variant pools organized by rapport tier
        # Medium rapport (2)
        medium_rapport_variants = [
            "You wrap your arms around Echo's massive coils. She tenses for a moment, then relaxes, pressing back with gentle warmth. The radio thrums with surprised but pleased static—this is new, but welcome.",
            "You press yourself against Echo's side, wrapping your arms as far as you can. Her coils shift to accommodate you, and the radio pulses with tentative warmth—she's learning to trust this closeness.",
            "Echo's coils are warm and solid as you hug her. She stills, processing this new gesture, then relaxes into it. The radio hums with cautious acceptance.",
        ]
        
        # Medium-high rapport (3-4)
        medium_high_variants = [
            "Echo's coils wrap around you in return, a warm, protective embrace. The radio sings with deep contentment, and you feel a profound sense of connection. This is home.",
            "You hug Echo, and her coils respond immediately, wrapping you in warmth and weight. The radio thrums with satisfaction—this closeness is becoming natural.",
            "Echo's embrace tightens around you, not constricting but secure. You feel the steady rhythm of her breathing, and the radio pulses with deep, contented warmth.",
            "Her coils shift to hold you closer, and you feel the reassuring weight and warmth of her presence. The radio sings with fondness—you belong here.",
        ]
        
        # High rapport (5+)
        high_rapport_variants = [
            "Echo's embrace is familiar now, but no less meaningful. Her coils hold you close, and the radio pulses with steady, loving warmth. You are bonded, and this moment of closeness reaffirms that bond.",
            "You hug Echo, and her coils wrap around you instantly—protective, warm, completely at ease. The radio thrums with deep love, and you feel utterly safe.",
            "Echo's coils tighten around you in a perfect embrace. The radio sings with profound contentment, and you feel the depth of your connection in every warm, solid coil.",
        ]
        
        # Select variant pool based on rapport
        if current_rapport < 3:
            variants = medium_rapport_variants
        elif current_rapport < 5:
            variants = medium_high_variants
        else:
            variants = high_rapport_variants
        
        # Rotate variant to avoid repeats
        last_variant = state.echo_last_hug_variant
        available_indices = [i for i in range(len(variants)) if i != last_variant]
        if available_indices:
            variant_idx = random.choice(available_indices)
        else:
            variant_idx = random.randint(0, len(variants) - 1)
        state.echo_last_hug_variant = variant_idx
        
        description = variants[variant_idx]
        
        # Add rapport-based conditional lines
        if current_rapport >= 5:
            rapport_lines = [
                " Her coils hold you like you're the most precious thing in the world.",
                " You could stay like this forever, and she seems to feel the same.",
            ]
            if random.random() < 0.5:  # 50% chance for high rapport
                description += random.choice(rapport_lines)
        elif current_rapport >= 3:
            rapport_lines = [
                " The connection between you grows stronger with each embrace.",
                " You feel her trust in the way her coils relax around you.",
            ]
            if random.random() < 0.35:  # 35% chance
                description += random.choice(rapport_lines)
        
        # Add vore hints if enabled (subtle, occasional)
        if vore_on and current_rapport >= 3 and random.random() < 0.12:  # 12% chance (less common than boop)
            vore_hints = [
                " Her coils tighten just slightly—protective, or perhaps possessive? Either way, you feel completely safe.",
                " You catch a low rumble from deep within her, but it's warm and content, like a satisfied purr.",
                " For a moment, her coils press closer, and you feel the solid warmth of her body around you. She could hold you like this for a very long time.",
            ]
            description += random.choice(vore_hints)
        
        return description, True, False, "hug"
    elif current_rapport < 2:
        reject_variants = [
            "You move to hug Echo, but she pulls back slightly, scales cool with uncertainty. The radio emits a cautious pulse. Perhaps you need to build more trust first.",
            "You reach out to hug Echo, but she shifts away, watching you carefully. The radio crackles with wariness—she's not ready for such close contact yet.",
        ]
        # Rotate variant
        last_variant = state.echo_last_hug_variant
        variant_idx = (last_variant + 1) % len(reject_variants)
        state.echo_last_hug_variant = variant_idx
        description = reject_variants[variant_idx]
        return description, False, False, "hug"
    else:
        # At max rapport, still meaningful but no further gain
        max_rapport_variants = [
            "Echo's embrace is warm and familiar. The radio hums with deep contentment. Your bond is as strong as it can be, and this moment of closeness is its own reward.",
            "You hug Echo, and she responds with the same deep, protective warmth as always. The radio thrums with satisfaction—your connection is complete, but these moments remain precious.",
            "Echo's coils wrap around you with familiar affection. The radio pulses with steady love. Even at the peak of your bond, every embrace feels like coming home.",
        ]
        # Rotate variant
        last_variant = state.echo_last_hug_variant
        available_indices = [i for i in range(len(max_rapport_variants)) if i != last_variant % len(max_rapport_variants)]
        if available_indices:
            variant_idx = available_indices[0]
        else:
            variant_idx = random.randint(0, len(max_rapport_variants) - 1)
        state.echo_last_hug_variant = variant_idx
        description = max_rapport_variants[variant_idx]
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
    vore_on = is_vore_enabled(state)
    
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
        
        # Variant pools organized by rapport tier
        # Low rapport (1)
        low_rapport_variants = [
            "You gently boop Echo's snout. She blinks, then lets out a soft, surprised hiss. The radio crackles with amusement—playful static dancing across the speaker. She seems to enjoy this.",
            "You tap Echo's snout playfully. Her head tilts in curiosity, and she responds with a gentle nose-boop back. The radio emits a surprised but pleased crackle.",
            "You give Echo's snout a gentle boop. She flicks her tongue out, tasting the air, then nudges you back with careful curiosity. The radio thrums with tentative amusement.",
        ]
        
        # Medium rapport (2-3)
        medium_rapport_variants = [
            "You boop Echo's snout playfully. She responds by nudging you back with her head, a gentle push that's clearly meant as a game. The radio thrums with laughter-like static, and you both share a moment of lighthearted connection.",
            "You boop Echo's snout, and she immediately boops back, her head darting forward in a playful motion. The radio crackles with delighted static—this is becoming a fun ritual.",
            "Echo's snout meets your finger with a gentle nudge. She tilts her head and flicks her tongue playfully, clearly enjoying the game. The radio pulses with cheerful static.",
            "You tap Echo's nose, and she responds by wrapping a single coil around you briefly before releasing—a playful squeeze. The radio thrums with mirthful warmth.",
        ]
        
        # High rapport (4+)
        high_rapport_variants = [
            "You boop Echo's snout, and she immediately responds with a playful coil-wrap, gently squeezing you before releasing. The radio sings with delighted static—this is a familiar game between you, and it never gets old.",
            "You boop Echo's snout, and she chases your hand playfully, head bobbing in what seems like laughter. The radio pulses with pure joy—this game is a favorite between you.",
            "Echo's snout meets your boop with eager anticipation. She wraps you in a quick, playful squeeze, tail thumping rhythmically. The radio crackles with familiar delight.",
        ]
        
        # Select variant pool based on rapport
        if current_rapport < 2:
            variants = low_rapport_variants
        elif current_rapport < 4:
            variants = medium_rapport_variants
        else:
            variants = high_rapport_variants
        
        # Rotate variant to avoid repeats
        last_variant = state.echo_last_boop_variant
        available_indices = [i for i in range(len(variants)) if i != last_variant]
        if available_indices:
            variant_idx = random.choice(available_indices)
        else:
            variant_idx = random.randint(0, len(variants) - 1)
        state.echo_last_boop_variant = variant_idx
        
        description = variants[variant_idx]
        
        # Add rapport-based conditional lines
        if current_rapport >= 4:
            rapport_lines = [
                " Her coils wrap tighter for just a moment—protective, playful, fond.",
                " You feel completely safe in this game, knowing she'll never truly hurt you.",
            ]
            if random.random() < 0.4:  # 40% chance
                description += random.choice(rapport_lines)
        
        # Add vore hints if enabled (playful teasing, especially with repeated boops)
        if vore_on and current_rapport >= 2 and random.random() < 0.2:  # 20% chance (more common for boops)
            vore_hints = [
                " Her eyes briefly linger on you with a playful, hungry look before she shakes her head and resumes the game.",
                " You catch a low rumble from her stomach—is that amusement or appetite? Either way, she's clearly enjoying this.",
                " For a heartbeat, her gaze holds you like prey, but then it softens into playful warmth. She's just teasing.",
            ]
            description += random.choice(vore_hints)
        
        return description, True, False, "boop"
    elif current_rapport < 1:
        reject_variants = [
            "You reach out to boop Echo, but she pulls back, scales cool. The radio emits a low, uncertain hum. She's not ready for playful interactions yet.",
            "You try to boop Echo's snout, but she shifts away, watching you warily. The radio crackles with caution—not rejection, but not yet trust.",
        ]
        # Rotate variant
        last_variant = state.echo_last_boop_variant
        variant_idx = (last_variant + 1) % len(reject_variants)
        state.echo_last_boop_variant = variant_idx
        description = reject_variants[variant_idx]
        return description, False, False, "boop"
    else:
        # At max rapport, still playful but no further gain
        max_rapport_variants = [
            "You boop Echo's snout, and she responds with the same playful energy as always. The radio crackles with familiar amusement. Your bond is at its peak, but the joy of this simple game remains.",
            "You boop Echo, and she plays along with familiar delight. The radio thrums with warmth—your connection is complete, but the fun never ends.",
            "Echo's snout meets your boop eagerly. The radio pulses with playful static. Even at the peak of your bond, these moments bring simple joy.",
        ]
        # Rotate variant
        last_variant = state.echo_last_boop_variant
        available_indices = [i for i in range(len(max_rapport_variants)) if i != last_variant % len(max_rapport_variants)]
        if available_indices:
            variant_idx = available_indices[0]
        else:
            variant_idx = random.randint(0, len(max_rapport_variants) - 1)
        state.echo_last_boop_variant = variant_idx
        description = max_rapport_variants[variant_idx]
        return description, False, False, "boop"

