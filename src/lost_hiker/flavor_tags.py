"""Flavor tag registry and tag pack definitions for Lost Hiker.

This module provides a centralized registry of all flavor tags organized by
family, and defines tag packs for character creation. All tags are purely
narrative and have no mechanical impact.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Tag families organized by theme
TAG_FAMILIES: Dict[str, List[str]] = {
    # Existing core tags
    "core": [
        "furred",
        "scaled",
        "slimy",
        "chitinous",
        "feathered",
        "plantlike",
        "stoneborn",
        "coldblooded",
        "ambient_magic",
        "forestborn",
        "caveborn",
        "riverborn",
        "manylimbed",
    ],
    # Fungal / Mycelial
    "fungal": [
        "fungal",
        "mycelial",
        "sporeborne",
        "decomposer",
        "glowcap",
        "rootmind",
        "softbloom",
        "mossy",
    ],
    # Slime / Ooze / Amorphous
    "slime": [
        "slimy",  # Already in core, but listed here for completeness
        "gelatinous",
        "amorphous",
        "viscous",
        "elastic",
        "transparent",
        "pseudopods",
        "softbodied",
    ],
    # Synth / Construct / Biotech
    "synth": [
        "synthetic",
        "composite",
        "alloyed",
        "modular",
        "smoothplate",
        "softservo",
        "lightcore",
        "resonanceframe",
    ],
    # Mix-In (hybrids / elemental / psionic / materials)
    "mix_in": [
        "hybrid",
        "stitched",
        "grafted",
        "emberheart",
        "frostbreath",
        "stormtouched",
        "mistborne",
        "mindecho",
        "astral",
        "dreamlinked",
        "veilborn",
        "saplike",
        "rubberlike",
        "fungal_leather",
        "crystalhide",
        "mossfur",
        "boneplated",
    ],
}

# Tag packs for character creation
TAG_PACKS: Dict[str, Dict[str, Any]] = {
    "fungal_essence": {
        "name": "Fungal Essence",
        "description": "A mycelial, sporeborne form with fungal characteristics",
        "tags": ["fungal", "sporeborne", "mycelial"],
    },
    "ooze_form": {
        "name": "Ooze / Slime Form",
        "description": "An amorphous, gelatinous body with slime-like properties",
        "tags": ["slimy", "gelatinous", "amorphous"],
    },
    "synthetic_construct": {
        "name": "Synthetic / Construct",
        "description": "A synthetic, modular form with construct-like features",
        "tags": ["synthetic", "modular", "smoothplate"],
    },
    "none": {
        "name": "None / Manual Selection",
        "description": "Choose tags manually without a preset pack",
        "tags": [],
    },
}


def get_all_tags() -> List[str]:
    """Get a flat list of all valid flavor tags."""
    all_tags: List[str] = []
    for family_tags in TAG_FAMILIES.values():
        all_tags.extend(family_tags)
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in all_tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    return unique_tags


def get_tags_by_family(family: str) -> List[str]:
    """Get all tags in a specific family."""
    return TAG_FAMILIES.get(family, [])


def get_tag_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    """Get a tag pack by ID."""
    return TAG_PACKS.get(pack_id)


def get_all_tag_packs() -> Dict[str, Dict[str, Any]]:
    """Get all available tag packs."""
    return TAG_PACKS.copy()


def is_valid_tag(tag: str) -> bool:
    """Check if a tag is valid."""
    return tag in get_all_tags()

