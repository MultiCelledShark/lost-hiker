"""Tea and brew flavor system for Lost Hiker.

This module provides race-aware flavor text for teas and brews, enriching
descriptions with race-specific sensory details. All differences are purely
narrative with no mechanical impact.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from .state import GameState


# Tea flavor categories
TEA_CATEGORY_CALMING = "calming"
TEA_CATEGORY_STAMINA = "stamina"
TEA_CATEGORY_CLARITY = "clarity"
TEA_CATEGORY_WARMTH = "warmth"
TEA_CATEGORY_MYSTICAL = "mystical"

# Map tea IDs to their flavor categories
TEA_CATEGORIES: Dict[str, str] = {
    "mint_tea": TEA_CATEGORY_CALMING,
    "dream_fern_infusion": TEA_CATEGORY_CALMING,
    "dreamleaf_tea": TEA_CATEGORY_CALMING,
    "brambleroot_decoction": TEA_CATEGORY_STAMINA,
    "water_clarity_tea": TEA_CATEGORY_CLARITY,
    "focus_clarity_tea": TEA_CATEGORY_CLARITY,
    # Future teas can be added here
    # "ember_root_tea": TEA_CATEGORY_WARMTH,
    # "heartmore_tea": TEA_CATEGORY_STAMINA,
    # "starlace_tea": TEA_CATEGORY_CLARITY,
    # "veilgrass_tea": TEA_CATEGORY_CALMING,
    # "echo_leaf_tea": TEA_CATEGORY_MYSTICAL,
}

# Race-aware flavor sentences by tea category and race
RACE_TEA_FLAVOR: Dict[str, Dict[str, list[str]]] = {
    "elf": {
        TEA_CATEGORY_CALMING: [
            "The tea tastes crisp and botanical; you feel the forest breathing with you.",
            "Each sip connects you deeper to the forest's quiet rhythms.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew awakens something ancient in your blood—forest energy flows through you.",
        ],
        TEA_CATEGORY_CLARITY: [
            "The clarity tea sharpens your forest-tuned senses; paths seem to sing their names.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads through you like sunlight filtering through leaves.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew resonates with the ley-lines; you feel the forest's magic pulse.",
        ],
    },
    "dwarf": {
        TEA_CATEGORY_CALMING: [
            "The tea feels earthy and grounding; solid warmth spreads through your limbs.",
            "Each sip anchors you deeper, like roots finding stone.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew fills you with steady, unshakeable energy—mountain-strong.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your mind clears like polished stone; everything feels solid and certain.",
        ],
        TEA_CATEGORY_WARMTH: [
            "The warmth settles deep in your bones, steady and lasting.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew resonates with stone-memory; you feel the earth's ancient pulse.",
        ],
    },
    "lizard_folk": {
        TEA_CATEGORY_CALMING: [
            "The tea soothes your cold-blooded nature; your scales relax.",
        ],
        TEA_CATEGORY_STAMINA: [
            "Energy courses through you, warming your scales from within.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your sharp senses sharpen further; every detail stands out clearly.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Heat seeps into stiff scales; blissful warmth spreads through your body.",
            "The warmth is especially welcome—your cold-blooded nature drinks it in.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew tingles against your scales; something ancient stirs.",
        ],
    },
    "cow_kin": {
        TEA_CATEGORY_CALMING: [
            "The tea brings steady, filling comfort—like a full belly and safe pasture.",
            "A sense of calm settles over you, steady and reliable.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew fills you with steady, enduring energy—built to last.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your mind clears with patient, methodical clarity.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads through you like a gentle, steady sunbeam.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew feels grounding, connecting you to the earth's steady pulse.",
        ],
    },
    "wolf_kin": {
        TEA_CATEGORY_CALMING: [
            "The tea's aroma hits your senses like fresh winter air—sharp and clean.",
            "Herbs dance on your tongue; your keen nose picks up every subtle note.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew awakens your predator instincts; energy flows like a hunt.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your sharp senses sharpen further; scents and sounds become crystal clear.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads through your fur; you feel cozy and alert.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew makes your fur tingle; wild magic stirs in your blood.",
        ],
    },
    "deer_kin": {
        TEA_CATEGORY_CALMING: [
            "The tea feels calming, heart-slowing; your pulse settles into a forest rhythm.",
            "A gentle calm washes over you, like settling into a safe thicket.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew fills you with graceful, sustained energy—ready to bound through the forest.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your keen hearing sharpens; every distant sound becomes clear and distinct.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads gently through you, like morning sun on your fur.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew makes your ears twitch; forest magic whispers to you.",
        ],
    },
    "fox_kin": {
        TEA_CATEGORY_CALMING: [
            "The tea brings a little tingle, a spark of mischief; your tongue tingles with playful energy.",
            "A light, playful calm settles over you—restless but content.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew fills you with quick, darting energy—ready to pounce.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your quick mind sharpens; details snap into focus with clever clarity.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads through you with a playful spark; you feel energized and alert.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew makes your tail twitch; trickster magic dances in your veins.",
        ],
    },
    "gryphon_folk": {
        TEA_CATEGORY_CALMING: [
            "The tea feels airy and bright; steam curls around your beak as your feathers fluff.",
            "A light, airy calm settles over you; your feathers relax.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew fills you with soaring energy—ready to take flight.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your sharp eyes sharpen further; everything comes into perfect focus.",
        ],
        TEA_CATEGORY_WARMTH: [
            "Warmth spreads through your feathers; you feel cozy and alert.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew makes your feathers ruffle; wind-magic stirs in your blood.",
        ],
    },
    "dragonborn": {
        TEA_CATEGORY_CALMING: [
            "The tea plays off your internal warmth; the brew awakens something glowing inside you.",
            "Your inner fire responds to the brew; warmth radiates from within.",
        ],
        TEA_CATEGORY_STAMINA: [
            "The brew stokes your inner fire; draconic energy courses through your veins.",
        ],
        TEA_CATEGORY_CLARITY: [
            "Your draconic senses sharpen; magic in the air becomes visible to you.",
        ],
        TEA_CATEGORY_WARMTH: [
            "The warmth resonates with your inner fire; heat spreads like dragon's breath.",
        ],
        TEA_CATEGORY_MYSTICAL: [
            "The mystical brew awakens your draconic heritage; ancient magic stirs in your blood.",
        ],
    },
    # Human gets generic descriptions (no special race flavor)
}


def get_tea_category(tea_id: str) -> Optional[str]:
    """
    Get the flavor category for a tea.
    
    Args:
        tea_id: The tea item ID
        
    Returns:
        Tea category string, or None if not categorized
    """
    return TEA_CATEGORIES.get(tea_id)


def get_race_tea_flavor(
    tea_id: str,
    race_id: str,
    races_data: Optional[Dict[str, Dict[str, Any]]] = None,
    chance: float = 0.4,
) -> Optional[str]:
    """
    Get optional race-aware flavor text to append to tea descriptions.
    
    This function appends a short sentence describing how the tea feels
    to the player's race, based on their flavor_tags and the tea's category.
    
    Args:
        tea_id: The tea item ID
        race_id: The player's race ID
        races_data: Optional races.json data (for future flavor_tag-based selection)
        chance: Probability of returning flavor (default 40%)
        
    Returns:
        Optional flavor text string to append, or None
    """
    if random.random() > chance:
        return None
    
    # Get tea category
    category = get_tea_category(tea_id)
    if not category:
        return None
    
    # Get race-specific flavor lines
    race_flavor = RACE_TEA_FLAVOR.get(race_id)
    if not race_flavor:
        return None
    
    category_lines = race_flavor.get(category)
    if not category_lines:
        return None
    
    return random.choice(category_lines)


def enhance_tea_description(
    base_description: str,
    tea_id: str,
    race_id: str,
    races_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """
    Enhance a tea description with optional race-aware flavor text.
    
    Args:
        base_description: The base tea description
        tea_id: The tea item ID
        race_id: The player's race ID
        races_data: Optional races.json data
        
    Returns:
        Enhanced description with optional race flavor appended
    """
    race_flavor = get_race_tea_flavor(tea_id, race_id, races_data)
    if race_flavor:
        return f"{base_description} {race_flavor}"
    return base_description

