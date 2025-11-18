"""Micro-quest logic for Wave 1 NPCs and special events."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .state import GameState
    from .ui import UI


def check_blue_fireflies_event(state: GameState) -> bool:
    """
    Check if Blue Fireflies event should trigger.
    
    Conditions:
    - Season == Spring
    - Time-of-day == Night
    - Location == Glade
    - Random chance (2-5%)
    - Not already seen this playthrough (optional)
    
    Args:
        state: Current game state
        
    Returns:
        True if event should trigger
    """
    if state.current_season != "spring":
        return False
    if state.time_of_day != "Night":
        return False
    if state.active_zone != "glade":
        return False
    # Low random chance (3% base)
    if random.random() > 0.03:
        return False
    # Optional: only trigger once per playthrough
    if state.npc_state.get("blue_fireflies_seen", False):
        return False
    return True


def trigger_blue_fireflies_event(state: GameState, ui: UI) -> None:
    """
    Trigger the Blue Fireflies Spring night event at the Glade.
    
    Shows the event scene, includes Echo and Astrin if present,
    and optionally offers Echo belly shelter if vore is enabled.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
    """
    from .echo import is_echo_present_at_glade
    from .vore import is_vore_enabled
    from .echo_vore import can_echo_vore_trigger, trigger_echo_belly_shelter
    
    # Show the event scene
    ui.echo(
        "\nAs night falls, the Glade fills with a soft, ethereal light. "
        "Blue fireflies drift into the clearing, their bioluminescent bodies "
        "pulsing in perfect synchrony. They move as one, creating patterns of "
        "light that seem to trace the ley-lines themselves. The air hums with "
        "a gentle harmony, and for a moment, the forest feels perfectly at peace.\n"
    )
    
    # Echo's reaction
    if is_echo_present_at_glade(state):
        ui.echo(
            "[RADIO] Look... the fireflies. They're all moving together, pulsing "
            "in unison. It's rare—a sign of harmony. The forest remembers itself tonight.\n"
        )
    
    # Astrin's reaction if present
    if state.npc_state.get("astrin_status") == "at_glade":
        ui.echo(
            "Astrin looks up from her work, her half-dryad eyes reflecting the "
            "fireflies' light. 'The forest is singing tonight. The ley-lines are "
            "in harmony. It's beautiful, isn't it?'\n"
        )
    
    # Optional small buff (forest_memory or rapport)
    from .character import TimedModifier
    state.timed_modifiers.append(
        TimedModifier(
            source="blue_fireflies",
            modifiers=[{"add": {"forest_memory": 1.0}}],
            expires_on_day=state.day + 3,  # Lasts 3 days
        )
    )
    
    # Mark as seen
    state.npc_state["blue_fireflies_seen"] = True
    
    # If vore is enabled and conditions are met, offer Echo belly shelter
    if is_vore_enabled(state) and is_echo_present_at_glade(state):
        if can_echo_vore_trigger(state):
            ui.echo(
                "\n[RADIO] The night is peaceful. Would you like to rest inside me? "
                "You'll be safe, warm, protected. And if Astrin wishes, she can join us too.\n"
            )
            # Note: Actual vore trigger would be handled by player choice in dialogue/command
            # For now, we just show the offer text


def check_echo_checkin(state: GameState) -> bool:
    """
    Check if Echo check-in interaction should trigger.
    
    Conditions:
    - At Glade
    - Echo present
    - Low stamina or recent threat encounters
    - Not checked in today
    - Low frequency (20% chance per eligible visit)
    
    Args:
        state: Current game state
        
    Returns:
        True if check-in should trigger
    """
    from .echo import is_echo_present_at_glade
    
    if state.active_zone != "glade":
        return False
    if not is_echo_present_at_glade(state):
        return False
    
    # Check if already checked in today
    last_checkin = state.npc_state.get("echo_checkin_last_day")
    if last_checkin == state.day:
        return False
    
    # Check for rough day conditions (low stamina or condition > 0)
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    if state.stamina < stamina_max * 0.5 or state.condition > 0:
        # 20% chance when conditions are met
        if random.random() < 0.2:
            return True
    
    return False


def trigger_echo_checkin(state: GameState, ui: UI) -> None:
    """
    Trigger Echo check-in interaction.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
    """
    from .dialogue import start_dialogue, get_current_dialogue_text, get_available_options
    from .dialogue import select_option, DialogueSession
    
    ui.echo(
        "[RADIO] You seem tired. Rough day? The forest can be harsh, but you're safe here. "
        "Rest. Recover. I'll watch over you.\n"
    )
    
    # Small stamina or rapport boost
    from .rapport import change_rapport
    change_rapport(state, "echo", 1)
    
    # Small stamina boost
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    state.stamina = min(stamina_max, state.stamina + 1.0)
    
    # Mark as checked in today
    state.npc_state["echo_checkin_last_day"] = state.day


def check_echo_favor(state: GameState) -> bool:
    """
    Check if Echo favor event should trigger.
    
    Conditions:
    - At Glade
    - Echo present
    - Sufficient rapport (friendly tier)
    - Not triggered today
    - Low frequency (5% chance per eligible visit)
    
    Args:
        state: Current game state
        
    Returns:
        True if favor event should trigger
    """
    from .echo import is_echo_present_at_glade
    from .rapport import get_rapport, get_rapport_tier
    
    if state.active_zone != "glade":
        return False
    if not is_echo_present_at_glade(state):
        return False
    
    # Check rapport tier (friendly = 2-3, bonded = 4-5)
    rapport = get_rapport(state, "echo")
    rapport_tier = get_rapport_tier(rapport)
    if rapport < 2:  # Need at least "friendly" tier
        return False
    
    # Check if already triggered today
    last_favor = state.npc_state.get("echo_favor_last_day")
    if last_favor == state.day:
        return False
    
    # Low frequency (5% chance)
    if random.random() < 0.05:
        return True
    
    return False


def trigger_echo_favor(state: GameState, ui: UI) -> None:
    """
    Trigger Echo favor event (Echo brings small finds).
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
    """
    ui.echo(
        "[RADIO] I found something while you were away. Small things—berries, herbs. "
        "I thought you might need them. Take them, please.\n"
    )
    
    # Add small random resource
    resources = ["forest_berries", "mint", "trail_nuts"]
    resource = random.choice(resources)
    state.inventory.append(resource)
    ui.echo(f"You receive: {resource.replace('_', ' ').title()}.\n")
    
    # Mark as triggered today
    state.npc_state["echo_favor_last_day"] = state.day


def apply_hermit_sketch_buff(state: GameState) -> None:
    """
    Apply Hermit's forest sketch buff (temporary forest_memory bonus).
    
    Args:
        state: Current game state
    """
    from .character import TimedModifier
    
    if state.npc_state.get("hermit_sketch_given", False):
        # Add temporary forest_memory modifier (lasts 3 days)
        state.timed_modifiers.append(
            TimedModifier(
                source="hermit_sketch",
                modifiers=[{"add": {"forest_memory": 1.0}}],
                expires_on_day=state.day + 3,
            )
        )


def apply_druid_night_ritual_buff(state: GameState) -> None:
    """
    Apply Druid's night ritual buff (one-night forest_memory bonus).
    
    Args:
        state: Current game state
    """
    from .character import TimedModifier
    
    # Add one-night forest_memory modifier
    state.timed_modifiers.append(
        TimedModifier(
            source="druid_night_ritual",
            modifiers=[{"add": {"forest_memory": 1.0}}],
            expires_on_day=state.day + 1,  # Lasts until next day
        )
    )


def apply_fisher_mussel_mastery(state: GameState) -> None:
    """
    Apply Fisher's mussel mastery (temporary improved mussel yield).
    
    Sets expiration day for the mastery buff.
    
    Args:
        state: Current game state
    """
    if state.npc_state.get("fisher_mussel_mastery_learned", False):
        # Set expiration (lasts 5 days)
        if state.npc_state.get("fisher_mussel_mastery_expires_day") is None:
            state.npc_state["fisher_mussel_mastery_expires_day"] = state.day + 5


def check_astrin_herb_id_available(state: GameState) -> bool:
    """
    Check if Astrin can identify herbs today.
    
    Args:
        state: Current game state
        
    Returns:
        True if herb ID is available today
    """
    if state.npc_state.get("astrin_status") != "at_glade":
        return False
    
    last_id_day = state.npc_state.get("astrin_herb_id_last_day")
    if last_id_day == state.day:
        return False
    
    return True


def trigger_astrin_herb_id(state: GameState, ui: UI) -> None:
    """
    Trigger Astrin's daily herb identification.
    
    Args:
        state: Current game state
        ui: UI interface for displaying messages
    """
    # Mark as used today
    state.npc_state["astrin_herb_id_last_day"] = state.day
    ui.echo(
        "Astrin examines your herbs and identifies them, explaining their uses. "
        "She's particularly helpful with forest herbs.\n"
    )


def check_naiad_blessing_available(state: GameState) -> bool:
    """
    Check if Naiad water blessing is available this week.
    
    Args:
        state: Current game state
        
    Returns:
        True if blessing is available this week
    """
    if not state.npc_state.get("naiad_blessing_quest_completed", False):
        return False
    
    last_blessing_week = state.npc_state.get("naiad_blessing_last_week")
    if last_blessing_week is None:
        return True
    
    # Check if a week has passed (7 days)
    if state.day - last_blessing_week >= 7:
        return True
    
    return False

