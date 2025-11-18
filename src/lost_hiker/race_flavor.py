"""Race-aware flavor text system for Lost Hiker.

This module provides functions to inject race-specific narrative flavor
across different game systems (NPCs, belly interactions, exploration, foraging).
All differences are purely narrative with no mechanical impact.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from .state import GameState


# Race-specific flavor snippets by context
EXPLORATION_FLAVOR: Dict[str, Dict[str, list[str]]] = {
    "wolf_kin": {
        "scent": [
            "Your nose twitches. The forest smells crowded tonight.",
            "A trail of scents leads deeper into the woods.",
            "The air carries hints of something large moving nearby.",
        ],
    },
    "dwarf": {
        "earth": [
            "Stone remembers every footstep. Yours included.",
            "The ground beneath your boots feels solid, reassuring.",
            "You sense the weight of the mountain's memory pressing down.",
        ],
    },
    "elf": {
        "magic": [
            "You sense a faint pull—the ley-lines humming quietly.",
            "The forest's pulse resonates with something deep inside you.",
            "An old memory stirs, touched by the magic flowing through the trees.",
        ],
    },
    "lizard_folk": {
        "temperature": [
            "The air feels cold. Your scales tighten instinctively.",
            "You seek patches of sunlight filtering through the canopy.",
            "Your cold-blooded nature makes you more aware of temperature shifts.",
        ],
    },
    "deer_kin": {
        "alertness": [
            "A twig cracks. You freeze without thinking.",
            "Your ears swivel, catching every distant sound.",
            "Old instincts surface—freeze, listen, assess.",
        ],
    },
    "gryphon_folk": {
        "wind": [
            "A stray gust ruffles your feathers. Storm coming?",
            "The wind carries scents from places you can't see.",
            "Your feathers sense the shift in air pressure.",
        ],
    },
    "dragonborn": {
        "magic": [
            "Your inner warmth stirs. Magic in the air.",
            "Something in the forest resonates with your draconic blood.",
            "The ley-lines feel different—warmer, more alive.",
        ],
    },
    "fox_kin": {
        "restlessness": [
            "Your tail twitches with restless energy.",
            "Every shadow seems to hold potential—opportunity or danger.",
            "Your quick reflexes are ready for anything.",
        ],
    },
}

FORAGING_FLAVOR: Dict[str, list[str]] = {
    "dwarf": [
        "Your fingers dig into the earth, finding roots and secrets buried deep.",
        "The rich scent of soil and root fills your senses.",
        "You harvest with the patience of stone, careful and thorough.",
    ],
    "elf": [
        "The herbs seem to sing faintly as you gather them—a song only you can hear.",
        "You sense the faint aura of each plant before you touch it.",
        "The forest shares its bounty willingly with one who understands its rhythms.",
    ],
    "lizard_folk": [
        "The cold moss contrasts sharply with your warm scales.",
        "Your precise claws make harvesting delicate plants easier.",
        "Temperature shifts guide you to the best gathering spots.",
    ],
    "fox_kin": [
        "Your tail twitches with excitement as you dig for treasures.",
        "You move with light-footed grace, disturbing nothing unnecessary.",
        "Your keen eyes spot details others might miss.",
    ],
    "gryphon_folk": [
        "You use your talons delicately, carefully separating plant from soil.",
        "Your sharp vision helps you spot the choicest specimens.",
        "The wind tells you where the freshest growth lies.",
    ],
    "dragonborn": [
        "Ember-Root feels warm to the touch—almost like kin.",
        "Hot herbs seem to pulse with inner fire, resonating with your own.",
        "Magic-infused plants respond to your draconic presence.",
    ],
    "wolf_kin": [
        "Your nose guides you to the freshest growth.",
        "The scents tell you which plants are ready for harvest.",
    ],
    "deer_kin": [
        "You gather with gentle movements, taking only what you need.",
        "The forest provides, and you accept its gifts gratefully.",
    ],
}

BELLY_FLAVOR: Dict[str, Dict[str, list[str]]] = {
    "wolf_kin": {
        "enter": [
            "Your fur brushes against the warm, slick walls.",
            "The heat is intense, but your thick coat provides some insulation.",
        ],
        "soothe": [
            "You press gently against the walls, your fur soft and calming.",
        ],
        "struggle": [
            "You thrash, your fur matting against the wet walls.",
        ],
        "relax": [
            "You curl up, your fur insulating you from the warmth.",
        ],
    },
    "cow_kin": {
        "enter": [
            "Your sturdy bulk settles heavily in the tight space.",
            "You take up considerable room, but the walls adjust around you.",
        ],
        "relax": [
            "You settle with a steady calm, your bulk anchoring you in place.",
        ],
    },
    "lizard_folk": {
        "enter": [
            "Your scales slide smoothly against the inner walls—surprisingly warm.",
            "The temperature is more comfortable than the cold forest outside.",
        ],
        "relax": [
            "Your scales adjust to the temperature, finding a comfortable equilibrium.",
        ],
    },
    "dragonborn": {
        "enter": [
            "Your scales gleam in the dim interior, warm against the slick walls.",
            "The warmth feels natural, almost familiar to your draconic nature.",
        ],
        "relax": [
            "Your inner fire keeps you comfortable despite the close quarters.",
        ],
    },
    "gryphon_folk": {
        "enter": [
            "Your feathers ruffle slightly in the close, humid space.",
            "The tight quarters make it hard to keep your wings comfortable.",
        ],
        "relax": [
            "You tuck your wings tight, settling despite the cramped space.",
        ],
    },
    "deer_kin": {
        "enter": [
            "Your heart flutters with instinctual fear, but there's no escape.",
            "You freeze instinctively, old prey responses kicking in.",
        ],
        "relax": [
            "You force yourself to calm, fighting down the instinct to panic.",
        ],
    },
    "fox_kin": {
        "enter": [
            "You feel trapped, and your twitchy nature makes you restless.",
            "The tight space makes you want to squirm and wriggle.",
        ],
        "struggle": [
            "You twist and turn, your quick reflexes making you hard to hold.",
        ],
    },
}


def get_exploration_flavor(
    race_id: str, races_data: Dict[str, Dict[str, Any]], chance: float = 0.15
) -> Optional[str]:
    """
    Get optional race-specific flavor text for exploration.
    
    Args:
        race_id: The player's race ID
        races_data: Full races.json data
        chance: Probability of returning flavor (default 15% to avoid overuse)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    flavor_data = EXPLORATION_FLAVOR.get(race_id)
    if not flavor_data:
        return None
    
    # Pick a random category and line
    category_lines = list(flavor_data.values())
    if not category_lines:
        return None
    
    lines = random.choice(category_lines)
    return random.choice(lines)


def get_foraging_flavor(
    race_id: str, races_data: Dict[str, Dict[str, Any]], chance: float = 0.2
) -> Optional[str]:
    """
    Get optional race-specific flavor text for foraging.
    
    Args:
        race_id: The player's race ID
        races_data: Full races.json data
        chance: Probability of returning flavor (default 20%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    lines = FORAGING_FLAVOR.get(race_id)
    if not lines:
        return None
    
    return random.choice(lines)


def get_belly_flavor(
    race_id: str,
    races_data: Dict[str, Dict[str, Any]],
    action: str,  # "enter", "soothe", "struggle", "relax"
    chance: float = 0.3,
) -> Optional[str]:
    """
    Get optional race-specific flavor text for belly interactions.
    
    Args:
        race_id: The player's race ID
        races_data: Full races.json data
        action: The belly action being performed
        chance: Probability of returning flavor (default 30%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    race_flavor = BELLY_FLAVOR.get(race_id)
    if not race_flavor:
        return None
    
    action_lines = race_flavor.get(action)
    if not action_lines:
        # Fallback to "enter" if specific action not found
        action_lines = race_flavor.get("enter", [])
    
    if not action_lines:
        return None
    
    return random.choice(action_lines)


def get_race_data(
    state: "GameState", races_data: Dict[str, Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Get the race data for the player's current race.
    
    Args:
        state: Current game state
        races_data: Full races.json data
        
    Returns:
        Race data dict, or None if not found
    """
    race_id = state.character.race_id
    return races_data.get(race_id)

