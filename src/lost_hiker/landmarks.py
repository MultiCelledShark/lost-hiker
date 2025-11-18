"""Landmark discovery and management for Lost Hiker."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .state import GameState
from .forest_memory import (
    adjust_landmark_weights_based_on_memory,
    get_path_stability,
)


@dataclass(frozen=True)
class Landmark:
    """Data structure for a discoverable landmark."""

    landmark_id: str
    name: str
    depth_min: int
    depth_max: int
    tags: tuple[str, ...]
    short_description: str
    long_description: str
    features: Dict[str, bool]
    encounter_biases: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Landmark":
        """Create a Landmark from JSON data."""
        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = tuple(str(t) for t in tags)
        else:
            tags = ()
        features = data.get("features", {})
        if not isinstance(features, dict):
            features = {}
        encounter_biases = data.get("encounter_biases", {})
        if not isinstance(encounter_biases, dict):
            encounter_biases = {}
        # Convert encounter_biases values to float
        encounter_biases_float = {
            str(k): float(v) for k, v in encounter_biases.items()
        }
        return cls(
            landmark_id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            depth_min=int(data.get("depth_min", 0)),
            depth_max=int(data.get("depth_max", 100)),
            tags=tags,
            short_description=str(data.get("short_description", "")),
            long_description=str(data.get("long_description", "")),
            features={k: bool(v) for k, v in features.items()},
            encounter_biases=encounter_biases_float,
        )

    def is_available_at_depth(self, depth: int) -> bool:
        """Check if this landmark can appear at the given depth."""
        return self.depth_min <= depth <= self.depth_max


class LandmarkCatalog:
    """Catalog of all landmarks for a zone."""

    def __init__(self, landmarks: List[Landmark]):
        self.landmarks = landmarks
        self._by_id: Dict[str, Landmark] = {
            lm.landmark_id: lm for lm in landmarks
        }

    def get(self, landmark_id: str) -> Optional[Landmark]:
        """Get a landmark by ID."""
        return self._by_id.get(landmark_id)

    def select_for_discovery(
        self, state: GameState, depth: int, discovery_chance: float = 0.15
    ) -> Optional[Landmark]:
        """
        Select a landmark for discovery based on depth, discovery state, and path stability.
        
        Uses forest memory system to:
        - Weight known landmarks by their path stability (higher stability = more likely)
        - Apply context-sensitive biasing (hunger, mortar, runestone discovery)
        - Integrate with runestone repair progress

        Args:
            state: Current game state
            depth: Current exploration depth
            discovery_chance: Base probability of discovering a landmark (default 0.15)

        Returns:
            A landmark to discover, or None if no discovery occurs
        """
        # Check if we should discover a landmark
        if random.random() > discovery_chance:
            return None

        # Get available landmarks at this depth
        available = [
            lm
            for lm in self.landmarks
            if lm.is_available_at_depth(depth)
        ]

        if not available:
            return None

        discovered = set(state.discovered_landmarks)
        undiscovered = [lm for lm in available if lm.landmark_id not in discovered]
        known = [lm for lm in available if lm.landmark_id in discovered]

        # Determine candidates: prefer known landmarks with higher stability
        # But still allow discovering new ones
        candidates = []
        
        # If we have known landmarks, check if we should prefer revisiting
        # Higher stability landmarks are more likely to be selected
        if known:
            # Calculate base revisit probability based on number of known landmarks
            # More known landmarks = higher chance of revisiting
            num_known = len(known)
            base_revisit_chance = min(0.6, 0.3 + (num_known * 0.05))
            
            # Adjust based on average stability of known landmarks
            if known:
                avg_stability = sum(get_path_stability(state, lm.landmark_id) for lm in known) / len(known)
                # Higher average stability increases revisit chance
                stability_bonus = avg_stability * 0.1
                revisit_chance = min(0.7, base_revisit_chance + stability_bonus)
            else:
                revisit_chance = base_revisit_chance
            
            prefer_revisit = random.random() < revisit_chance
            
            if prefer_revisit:
                candidates = known
            elif undiscovered:
                # Mix: prefer known but allow new discoveries
                # Weight towards known based on stability
                if random.random() < 0.3:  # 30% chance to discover new
                    candidates = undiscovered
                else:
                    candidates = known
            else:
                candidates = known
        else:
            # No known landmarks, only undiscovered available
            candidates = undiscovered
        
        if not candidates:
            return None
        
        # Build context for forest memory weighting
        has_mortar = "primitive_mortar" in state.inventory
        has_mortar_ingredients = (
            "clay_lump" in state.inventory
            or "sand_handful" in state.inventory
            or "ash_scoop" in state.inventory
        )
        has_runestone_landmark = any(
            self.get(lm_id) and self.get(lm_id).features.get("has_runestone", False)
            for lm_id in discovered
        )
        
        context = {
            "hungry": state.days_without_meal >= 1,
            "has_mortar": has_mortar or has_mortar_ingredients,
            "day": state.day,
            "has_runestone_landmark": has_runestone_landmark,
        }
        
        # Get weights from forest memory system
        weights = adjust_landmark_weights_based_on_memory(state, candidates, context)
        
        # Select based on weights
        if weights and len(weights) == len(candidates):
            return random.choices(candidates, weights=weights, k=1)[0]
        
        return random.choice(candidates) if candidates else None

    def select_for_revisit(
        self, state: GameState, depth: int, revisit_chance: float = 0.1
    ) -> Optional[Landmark]:
        """
        Select a known landmark to revisit.

        Args:
            state: Current game state
            depth: Current exploration depth
            revisit_chance: Probability of revisiting a known landmark (default 0.1)

        Returns:
            A known landmark to revisit, or None
        """
        if random.random() > revisit_chance:
            return None

        discovered = set(state.discovered_landmarks)
        available = [
            lm
            for lm in self.landmarks
            if lm.landmark_id in discovered
            and lm.is_available_at_depth(depth)
        ]

        if not available:
            return None

        return random.choice(available)


def load_landmark_catalog(data_dir: Path, filename: str = "landmarks_forest.json") -> LandmarkCatalog:
    """Load landmarks from a JSON file."""
    path = data_dir / filename
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    landmarks = [
        Landmark.from_dict(entry)
        for entry in raw.get("landmarks", [])
    ]

    return LandmarkCatalog(landmarks)

