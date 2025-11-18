"""Sky description generation for Lost Hiker."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState
    from .time_of_day import TimeOfDay


def get_sky_description(state: "GameState") -> str:
    """
    Generate a sky description based on time of day and season.
    
    Args:
        state: Current game state
        
    Returns:
        Description of the sky/light conditions
    """
    from .time_of_day import get_time_of_day, is_player_sheltered
    
    # Check if player is sheltered/enclosed
    if is_player_sheltered(state):
        return "You can't see the sky from in here."
    
    time_of_day = get_time_of_day(state)
    season = state.get_season_name()
    
    # Generate descriptions based on time of day and season
    descriptions = {
        ("Dawn", "spring"): (
            "Soft gray light seeps through the canopy; the sky is pale "
            "with the first hints of sunrise."
        ),
        ("Dawn", "summer"): (
            "The sky brightens early, pale gold filtering through the leaves. "
            "The forest stirs with morning warmth."
        ),
        ("Dawn", "fall"): (
            "Mist clings to the branches as dawn breaks. The sky is a muted gray, "
            "with hints of orange bleeding through the canopy."
        ),
        ("Dawn", "winter"): (
            "The sky is a cold, pale gray. Dawn comes slowly, offering little warmth. "
            "Frost glints on the bare branches above."
        ),
        ("Day", "spring"): (
            "Bright patches of sky show through the canopy. The light is gentle, "
            "filtered green by new leaves."
        ),
        ("Day", "summer"): (
            "The sky is a bright patchwork through the leaves, harsh sunlight "
            "pressing down. The heat is palpable even in the shade."
        ),
        ("Day", "fall"): (
            "The sky is a clear, crisp blue between the branches. Golden light "
            "filters through autumn leaves, casting warm shadows."
        ),
        ("Day", "winter"): (
            "The sky is a pale, washed-out blue. Weak sunlight filters through "
            "bare branches, offering little warmth."
        ),
        ("Dusk", "spring"): (
            "The sky beyond the branches is streaked with orange and pink. "
            "Shadows grow long as evening settles in."
        ),
        ("Dusk", "summer"): (
            "The sky blazes with orange and red as the sun sets. The heat of the day "
            "begins to fade, and shadows stretch across the forest floor."
        ),
        ("Dusk", "fall"): (
            "The sky beyond the branches is streaked with orange and red; shadows "
            "are growing long. The air carries a crisp chill."
        ),
        ("Dusk", "winter"): (
            "The sky fades to a cold purple-gray. The sun sets early, and darkness "
            "creeps in quickly. The air grows sharp and biting."
        ),
        ("Night", "spring"): (
            "You can just make out the stars through gaps in the branches; the forest "
            "is mostly shapes and silhouettes. The night air is cool but not cold."
        ),
        ("Night", "summer"): (
            "The stars are clear and bright overhead, visible through breaks in the canopy. "
            "The forest is dark but not uncomfortably so, and the air is still warm."
        ),
        ("Night", "fall"): (
            "The night sky is clear and full of stars. The forest is dark, and the air "
            "has a sharp chill. You can just make out shapes in the moonlight."
        ),
        ("Night", "winter"): (
            "The sky is a deep, cold black, studded with brilliant stars. The forest "
            "is pitch dark, and the cold bites at any exposed skin. Moonlight offers "
            "little comfort."
        ),
    }
    
    key = (time_of_day.to_display_name(), season)
    return descriptions.get(key, "The sky is visible through the canopy above.")

