"""Tag-based flavor system for Lost Hiker.

This module provides a central flavor helper that reads the player's body_type,
flavor_tags, size, and archetype to return narrative flavor snippets for various
game contexts. All differences are purely narrative with no mechanical impact.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .character import Character

# Size category ordering for comparisons
SIZE_ORDER = {"small": 0, "medium": 1, "large": 2}


def get_exploration_flavor(
    character: Character,
    chance: float = 0.15,
) -> Optional[str]:
    """
    Get optional tag-based flavor text for exploration.
    
    Args:
        character: Player character with body_type, flavor_tags, size, archetype
        chance: Probability of returning flavor (default 15% to avoid overuse)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    snippets = []
    
    # Body type flavor
    body_type_snippets = {
        "naga": [
            "Your coils glide smoothly over the forest floor.",
            "Your tail provides steady traction as you move through the undergrowth.",
            "You navigate the terrain with serpentine grace.",
        ],
        "taur": [
            "Your hooves find solid purchase on the uneven ground.",
            "You lower your front half to pass under a low-hanging branch.",
            "Your mass shifts as you carefully navigate the terrain.",
        ],
        "quadruped": [
            "Your paws move quietly through the leaf litter.",
            "You move in a low, steady posture through the undergrowth.",
            "Your four-legged stance keeps you balanced on uneven ground.",
        ],
        "humanoid": [
            # Default biped text - no special flavor needed
        ],
    }
    
    body_snippets = body_type_snippets.get(character.body_type, [])
    if body_snippets:
        snippets.append(random.choice(body_snippets))
    
    # Flavor tag snippets
    tag_snippets = {
        "furred": [
            "Branches catch in your fur, leaving small burrs behind.",
            "Your fur brushes against the undergrowth, catching stray leaves.",
        ],
        "scaled": [
            "The cold ground feels sharp against your scales.",
            "You seek patches of sunlight filtering through the canopy for warmth.",
        ],
        "slimy": [
            "The damp forest floor leaves impressions in your trail.",
            "You move carefully, mindful of the muck clinging to your form.",
        ],
        "chitinous": [
            "Your exoskeleton clicks softly as you move through the brush.",
            "Hard chitin scrapes against bark as you navigate tight spaces.",
        ],
        "feathered": [
            "A stray breeze ruffles your feathers.",
            "You notice a few molting feathers caught in the undergrowth.",
        ],
    }
    
    for tag in character.flavor_tags:
        tag_lines = tag_snippets.get(tag, [])
        if tag_lines and random.random() < 0.3:  # 30% chance per tag
            snippets.append(random.choice(tag_lines))
    
    # Size flavor
    size_snippets = {
        "small": [
            "You slip easily through gaps in the undergrowth.",
            "Narrow spaces that would trouble others pose no obstacle.",
        ],
        "large": [
            "Branches bend and snap as you push through the forest.",
            "Your footsteps thud heavily on the forest floor.",
        ],
    }
    
    size_lines = size_snippets.get(character.size, [])
    if size_lines and random.random() < 0.3:
        snippets.append(random.choice(size_lines))
    
    # Archetype flavor
    archetype_snippets = {
        "cave_creature": [
            "You feel more at home near rocky outcrops and cave-mouths.",
            "The solid presence of stone nearby is reassuring.",
        ],
        "forest_creature": [
            "You feel at ease among the trees, as if you belong here.",
            "The forest's rhythms feel natural and familiar.",
        ],
        "river_creature": [
            "You're drawn to the sound of water in the distance.",
            "The presence of streams and creeks calls to you.",
        ],
    }
    
    archetype_lines = archetype_snippets.get(character.archetype, [])
    if archetype_lines and random.random() < 0.25:
        snippets.append(random.choice(archetype_lines))
    
    if snippets:
        return random.choice(snippets)
    return None


def get_foraging_flavor(
    character: Character,
    chance: float = 0.2,
) -> Optional[str]:
    """
    Get optional tag-based flavor text for foraging.
    
    Args:
        character: Player character with body_type, flavor_tags, size, archetype
        chance: Probability of returning flavor (default 20%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    snippets = []
    
    # Body type foraging flavor
    body_type_snippets = {
        "taur": [
            "You lower your front half, bracing with your hind legs as you gather.",
            "Your powerful frame makes it easy to move fallen logs aside.",
        ],
        "naga": [
            "You coil around logs and rocks, using your body to leverage them aside.",
            "Your coils provide stability as you carefully extract your finds.",
        ],
        "quadruped": [
            "You nose and paw at the ground, uncovering hidden treasures.",
            "Your low posture helps you spot things others might miss.",
        ],
        "humanoid": [
            "You kneel and crouch, carefully gathering what you need.",
        ],
    }
    
    body_snippets = body_type_snippets.get(character.body_type, [])
    if body_snippets:
        snippets.append(random.choice(body_snippets))
    
    # Flavor tag foraging snippets
    tag_snippets = {
        "slimy": [
            "You're careful not to get too much muck on your bulk as you gather.",
            "The damp soil clings to you, but you manage to keep your finds clean.",
        ],
        "chitinous": [
            "Your claws and mandibles scrape delicately at bark and soil.",
            "Hard chitin makes precise work of extracting buried items.",
        ],
        "furred": [
            "Your fur brushes against the undergrowth as you search.",
            "Small leaves and twigs catch in your fur as you forage.",
        ],
        "feathered": [
            "Your wings and feathers catch stray leaves as you gather.",
            "You use your feathers to carefully brush away debris.",
        ],
        "manylimbed": [
            "You have plenty of limbs to pry and lift as you search.",
            "Multiple appendages make gathering efficient and thorough.",
        ],
    }
    
    for tag in character.flavor_tags:
        tag_lines = tag_snippets.get(tag, [])
        if tag_lines and random.random() < 0.3:
            snippets.append(random.choice(tag_lines))
    
    if snippets:
        return random.choice(snippets)
    return None


def get_belly_flavor(
    character: Character,
    action: str,  # "enter", "soothe", "struggle", "relax", "pred_hold"
    is_predator: bool = False,
    chance: float = 0.3,
) -> Optional[str]:
    """
    Get optional tag-based flavor text for belly interactions.
    
    Args:
        character: Player character with body_type, flavor_tags, size, archetype
        action: The belly action being performed
        is_predator: True if player is the predator, False if prey
        chance: Probability of returning flavor (default 30%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    snippets = []
    
    if is_predator:
        # Player as predator - how they hold prey
        pred_snippets = {
            "taur": [
                "Your belly rests comfortably beneath your torso, warm and secure.",
                "Your prey settles into the space below your powerful frame.",
            ],
            "naga": [
                "Your coils wrap around your catch, holding them close and safe.",
                "Prey fits snugly within your serpentine form.",
            ],
            "quadruped": [
                "You curl protectively around your catch.",
                "Your four-legged stance keeps your belly close to the ground.",
            ],
            "humanoid": [
                "Your gut holds your catch securely.",
                "Your catch settles comfortably within you.",
            ],
        }
        
        body_lines = pred_snippets.get(character.body_type, [])
        if body_lines:
            snippets.append(random.choice(body_lines))
    else:
        # Player as prey - how they experience being swallowed
        body_type_snippets = {
            "naga": [
                "Your coils fold and curl as you're pulled deeper.",
                "You coil tightly, making yourself as compact as possible.",
            ],
            "taur": [
                "Your bulk settles heavily in the tight space.",
                "You fold your legs, trying to make yourself smaller.",
            ],
            "quadruped": [
                "You curl up instinctively, tail tucked close.",
                "Your four-legged form compresses into a tight ball.",
            ],
            "humanoid": [
                "You curl into a fetal position, trying to fit.",
                "You fold your limbs close to your body.",
            ],
        }
        
        body_lines = body_type_snippets.get(character.body_type, [])
        if body_lines:
            snippets.append(random.choice(body_lines))
        
        # Tag-based belly flavor
        tag_snippets = {
            "furred": [
                "Your fur brushes against the warm, slick walls.",
                "Your thick coat provides some insulation from the heat.",
            ],
            "scaled": [
                "Your scales slide smoothly against the inner walls.",
                "The temperature feels more comfortable than the cold forest outside.",
            ],
            "slimy": [
                "Your slime mixes with the inner moisture, creating a slick layer.",
                "The damp environment feels natural to your slimy form.",
            ],
            "chitinous": [
                "Your hard exoskeleton clicks against the soft walls.",
                "Your chitin provides protection in the close quarters.",
            ],
            "feathered": [
                "Your feathers ruffle in the close, humid space.",
                "The tight quarters make it hard to keep your wings comfortable.",
            ],
        }
        
        for tag in character.flavor_tags:
            tag_lines = tag_snippets.get(tag, [])
            if tag_lines and random.random() < 0.3:
                snippets.append(random.choice(tag_lines))
    
    if snippets:
        return random.choice(snippets)
    return None


def get_forest_magic_size_flavor(
    player_size: str,
    predator_size: str,
    chance: float = 0.25,
) -> Optional[str]:
    """
    Get "Forest magic" flavor when size relationships are odd.
    
    This should be called when a predator swallows prey that is larger than them,
    acknowledging that Forest magic is allowing this impossible size combination.
    
    Args:
        player_size: Player's size category ("small", "medium", "large")
        predator_size: Predator's size category ("small", "medium", "large")
        chance: Probability of returning flavor (default 25%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    player_size_val = SIZE_ORDER.get(player_size, 1)
    pred_size_val = SIZE_ORDER.get(predator_size, 1)
    
    # Only trigger if prey is larger than predator
    if player_size_val <= pred_size_val:
        return None
    
    magic_snippets = [
        "The Forest stretches space around you both; this shouldn't fit, but it does.",
        "Reality bends slightly—the impossible becomes possible in this place.",
        "You feel the Forest's magic at work, making space where there shouldn't be any.",
        "The world warps gently, accommodating what nature says shouldn't be possible.",
        "Forest magic flows through the moment, allowing the impossible to happen.",
    ]
    
    return random.choice(magic_snippets)


def get_resting_flavor(
    character: Character,
    context: str = "camp",  # "camp", "sheltered", "belly"
    chance: float = 0.3,
) -> Optional[str]:
    """
    Get optional tag-based flavor text for resting/camping.
    
    Args:
        character: Player character with body_type, flavor_tags, size, archetype
        context: Resting context ("camp", "sheltered", "belly")
        chance: Probability of returning flavor (default 30%)
        
    Returns:
        Optional flavor text string, or None
    """
    if random.random() > chance:
        return None
    
    snippets = []
    
    # Body type resting flavor
    body_type_snippets = {
        "quadruped": [
            "You curl up comfortably, tail across your nose.",
            "You settle into a familiar four-legged rest position.",
        ],
        "naga": [
            "You loop your coils into a comfortable resting position, tail tip tucked.",
            "Your serpentine form settles into a relaxed spiral.",
        ],
        "taur": [
            "You fold your legs under you, your heavy frame settling steadily.",
            "Your powerful presence is a steady, calming force at rest.",
        ],
        "humanoid": [
            "You settle into a comfortable position by the fire.",
        ],
    }
    
    body_lines = body_type_snippets.get(character.body_type, [])
    if body_lines:
        snippets.append(random.choice(body_lines))
    
    # Tag-based resting flavor
    tag_snippets = {
        "slimy": [
            "You leave a faint damp outline where you rest; others might lay down extra cloth.",
            "Your slimy form leaves a subtle mark on the ground.",
        ],
    }
    
    for tag in character.flavor_tags:
        tag_lines = tag_snippets.get(tag, [])
        if tag_lines and random.random() < 0.3:
            snippets.append(random.choice(tag_lines))
    
    if snippets:
        return random.choice(snippets)
    return None

