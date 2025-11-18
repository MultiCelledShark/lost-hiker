"""Hunger system and stamina cap management for Lost Hiker."""

from __future__ import annotations

from .state import GameState


def update_hunger_at_day_start(state: GameState, ate_proper_meal: bool) -> None:
    """
    Update hunger state at the start of a new day.
    
    Args:
        state: Current game state
        ate_proper_meal: Whether the player ate a proper meal yesterday
    """
    if ate_proper_meal:
        state.days_without_meal = 0
    elif not state.ate_snack_today:
        # Only increase hunger if no snack was eaten
        state.days_without_meal += 1
    # Reset snack flag for the new day
    state.ate_snack_today = False


def get_stamina_cap_multiplier(days_without_meal: int) -> float:
    """
    Get the stamina cap multiplier based on days without a proper meal.
    
    Tuned for balance: slightly more forgiving to allow careful players
    to survive without constant death threats, but still punishing.
    
    Args:
        days_without_meal: Number of days without a proper meal
        
    Returns:
        Multiplier for max stamina (0.0 to 1.0)
    """
    if days_without_meal == 0:
        return 1.0
    elif days_without_meal == 1:
        return 0.80  # Slightly more forgiving (was 0.75)
    elif days_without_meal == 2:
        return 0.55  # Slightly more forgiving (was 0.5)
    elif days_without_meal == 3:
        return 0.30  # Slightly more forgiving (was 0.25)
    else:
        return 0.0  # Will trigger game over


def get_rest_cap_multiplier(rest_type: str | None) -> float:
    """
    Get the stamina cap multiplier based on how the player rested.
    
    Args:
        rest_type: "camp", "collapse", or None (defaults to camp)
        
    Returns:
        Multiplier for max stamina (0.5 to 1.0)
    """
    if rest_type == "collapse":
        return 0.5
    # Default to camp (best rest) or None (assume camp)
    return 1.0


def apply_combined_stamina_cap(
    state: GameState, base_stamina_max: float
) -> tuple[float, float, float]:
    """
    Apply combined rest, hunger, and condition caps to base max stamina.
    
    The final cap is the minimum of rest_cap, hunger_cap, and condition_cap,
    so the strictest one wins.
    
    Args:
        state: Current game state
        base_stamina_max: Base maximum stamina before any caps
        
    Returns:
        Tuple of (final_capped_stamina, rest_cap_multiplier, hunger_cap_multiplier)
    """
    rest_cap = get_rest_cap_multiplier(state.rest_type)
    hunger_cap = get_stamina_cap_multiplier(state.days_without_meal)
    
    # Apply condition effects
    from .combat import get_condition_effects
    condition_effects = get_condition_effects(state)
    condition_cap = 1.0 - condition_effects["stamina_cap_reduction"]
    
    final_cap = min(rest_cap, hunger_cap, condition_cap)
    return (base_stamina_max * final_cap, rest_cap, hunger_cap)


def apply_stamina_cap(state: GameState, base_stamina_max: float) -> float:
    """
    Apply combined rest and hunger caps to the base max stamina.
    
    This is a convenience wrapper that returns just the final capped value.
    
    Args:
        state: Current game state
        base_stamina_max: Base maximum stamina before any caps
        
    Returns:
        Capped maximum stamina value
    """
    capped_stamina, _rest_cap, _hunger_cap = apply_combined_stamina_cap(
        state, base_stamina_max
    )
    return capped_stamina


def check_starvation_game_over(state: GameState) -> bool:
    """
    Check if the player has starved (4+ days without meal).
    
    Args:
        state: Current game state
        
    Returns:
        True if game over should trigger
    """
    return state.days_without_meal >= 4


def get_hunger_status_message(days_without_meal: int) -> str:
    """
    Get a flavor text message describing the player's hunger state.
    
    Args:
        days_without_meal: Number of days without a proper meal
        
    Returns:
        Narrative description of hunger state
    """
    messages = {
        0: "You wake steady, stomach full enough to face the day.",
        1: "You wake light-headed. The forest feels heavier.",
        2: "Your limbs ache and colors smear at the edges.",
        3: "You can barely stand. Each breath feels misaligned.",
    }
    return messages.get(days_without_meal, "You can barely stand. Each breath feels misaligned.")


def get_stamina_cap_message(
    days_without_meal: int,
    stamina_max: float,
    capped_max: float,
    rest_cap: float,
    hunger_cap: float,
) -> str:
    """
    Get a message describing the stamina cap effect.
    
    Args:
        days_without_meal: Number of days without a proper meal
        stamina_max: Base maximum stamina
        capped_max: Capped maximum stamina after combined caps
        rest_cap: Rest cap multiplier (0.5 to 1.0)
        hunger_cap: Hunger cap multiplier (0.0 to 1.0)
        
    Returns:
        Message describing the stamina cap
    """
    if capped_max >= stamina_max:
        return ""
    
    percentage = int((capped_max / stamina_max) * 100)
    messages = []
    
    # Only mention rest cap if it's the limiting factor and not full
    if rest_cap < 1.0 and rest_cap <= hunger_cap:
        messages.append("Poor rest limits your recovery")
    
    # Only mention hunger cap if it's the limiting factor
    if hunger_cap < 1.0 and hunger_cap <= rest_cap:
        messages.append("hunger limits your stamina")
    
    if messages:
        reason = " and ".join(messages)
        return f"{reason.capitalize()} to {percentage}% of normal ({capped_max:.0f}/{stamina_max:.0f})."
    
    return f"Stamina limited to {percentage}% of normal ({capped_max:.0f}/{stamina_max:.0f})."


def get_starvation_game_over_message() -> str:
    """
    Get the game over message for starvation.
    
    Returns:
        Narrative description of starvation collapse
    """
    return (
        "You collapse, your connection to the forest fraying beyond repair. "
        "Without proper sustenance, the ley-lines reject your presence. "
        "The world fades as you lose sync with the magical currents.\n"
    )

