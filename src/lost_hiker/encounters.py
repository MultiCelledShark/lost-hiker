"""Encounter framework for creature interactions in Lost Hiker."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState
from .rapport import get_rapport, change_rapport, get_rapport_tier


@dataclass
class EncounterChoice:
    """A single choice option in an encounter."""
    
    text: str
    outcome_key: str
    requirements: Dict[str, object] = field(default_factory=dict)


@dataclass
class EncounterOutcome:
    """Result of a choice in an encounter."""
    
    text: str
    rapport_delta: Dict[str, int] = field(default_factory=dict)
    stamina_delta: float = 0.0
    inventory_add: List[str] = field(default_factory=list)
    inventory_remove: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)
    condition_delta: int = 0  # For threat encounters
    threat_resolution: Optional[str] = None  # "flee", "calm", "stand_ground" for threat encounters


@dataclass
class EncounterDefinition:
    """Definition of a creature encounter."""
    
    encounter_id: str
    creature_id: str
    intro_text: str
    choices: List[EncounterChoice]
    outcomes: Dict[str, EncounterOutcome]
    trigger_conditions: Dict[str, object] = field(default_factory=dict)
    encounter_type: str = "normal"  # "normal" or "threat"
    
    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "EncounterDefinition":
        """Load an encounter definition from a dictionary."""
        choices_data = data.get("choices", [])
        choices = [
            EncounterChoice(
                text=choice.get("text", ""),
                outcome_key=choice.get("outcome", ""),
                requirements=dict(choice.get("requirements", {})),
            )
            for choice in choices_data
        ]
        
        outcomes_data = data.get("outcomes", {})
        outcomes = {}
        for key, outcome_data in outcomes_data.items():
            outcomes[key] = EncounterOutcome(
                text=outcome_data.get("text", ""),
                rapport_delta=dict(outcome_data.get("rapport_delta", {})),
                stamina_delta=float(outcome_data.get("stamina_delta", 0.0)),
                inventory_add=list(outcome_data.get("inventory_add", [])),
                inventory_remove=list(outcome_data.get("inventory_remove", [])),
                flags=dict(outcome_data.get("flags", {})),
                condition_delta=int(outcome_data.get("condition_delta", 0)),
                threat_resolution=outcome_data.get("threat_resolution"),
            )
        
        return cls(
            encounter_id=str(data.get("id", "")),
            creature_id=str(data.get("creature_id", "")),
            intro_text=str(data.get("intro_text", "")),
            choices=choices,
            outcomes=outcomes,
            trigger_conditions=dict(data.get("trigger_conditions", {})),
            encounter_type=str(data.get("encounter_type", "normal")),
        )


class EncounterEngine:
    """Engine for running creature encounters."""
    
    def __init__(self, encounters: List[EncounterDefinition]):
        self.encounters = {enc.encounter_id: enc for enc in encounters}
    
    def get_encounter(self, encounter_id: str) -> Optional[EncounterDefinition]:
        """Get an encounter definition by ID."""
        return self.encounters.get(encounter_id)
    
    def select_encounter_for_creature(
        self, 
        state: GameState, 
        creature_id: str,
        depth: int,
        season: str,
    ) -> Optional[EncounterDefinition]:
        """
        Select an appropriate encounter for a creature based on conditions.
        
        Args:
            state: The game state
            creature_id: The creature ID
            depth: Current exploration depth
            season: Current season
            
        Returns:
            An encounter definition, or None if no suitable encounter found
        """
        # Find all encounters for this creature
        candidate_encounters = [
            enc for enc in self.encounters.values()
            if enc.creature_id == creature_id
        ]
        
        if not candidate_encounters:
            return None
        
        # Filter by trigger conditions
        valid_encounters = []
        for enc in candidate_encounters:
            if self._check_trigger_conditions(state, enc, depth, season):
                valid_encounters.append(enc)
        
        if not valid_encounters:
            # Fall back to any encounter for this creature (ignore trigger conditions)
            # This ensures encounters can still trigger even if conditions aren't perfectly met
            valid_encounters = candidate_encounters
        
        # Select randomly from valid encounters
        return random.choice(valid_encounters) if valid_encounters else None
    
    def _check_trigger_conditions(
        self,
        state: GameState,
        encounter: EncounterDefinition,
        depth: int,
        season: str,
    ) -> bool:
        """Check if an encounter's trigger conditions are met."""
        conditions = encounter.trigger_conditions
        
        # Check depth range
        min_depth = conditions.get("min_depth")
        max_depth = conditions.get("max_depth")
        if min_depth is not None and depth < int(min_depth):
            return False
        if max_depth is not None and depth > int(max_depth):
            return False
        
        # Check season
        preferred_seasons = conditions.get("preferred_seasons")
        if preferred_seasons and season not in preferred_seasons:
            return False
        
        # Check time of day
        preferred_time_of_day = conditions.get("preferred_time_of_day")
        if preferred_time_of_day:
            from .time_of_day import get_time_of_day
            current_time = get_time_of_day(state).value
            if current_time not in preferred_time_of_day:
                return False
        
        # Check required landmark
        required_landmark = conditions.get("required_landmark")
        if required_landmark:
            if not state.current_landmark or state.current_landmark != required_landmark:
                return False
        
        # Check rapport tier
        required_tier = conditions.get("required_rapport_tier")
        if required_tier:
            current_rapport = get_rapport(state, encounter.creature_id)
            current_tier = get_rapport_tier(current_rapport)
            if current_tier != required_tier:
                return False
        
        # Check minimum rapport
        min_rapport = conditions.get("min_rapport")
        if min_rapport is not None:
            current_rapport = get_rapport(state, encounter.creature_id)
            if current_rapport < int(min_rapport):
                return False
        
        # Check maximum rapport
        max_rapport = conditions.get("max_rapport")
        if max_rapport is not None:
            current_rapport = get_rapport(state, encounter.creature_id)
            if current_rapport > int(max_rapport):
                return False
        
        return True
    
    def get_available_choices(
        self,
        state: GameState,
        encounter: EncounterDefinition,
    ) -> List[EncounterChoice]:
        """
        Get choices available to the player based on requirements.
        
        Args:
            state: The game state
            encounter: The encounter definition
            
        Returns:
            List of available choices
        """
        available = []
        for choice in encounter.choices:
            if self._check_choice_requirements(state, choice, encounter):
                available.append(choice)
        return available
    
    def _check_choice_requirements(
        self,
        state: GameState,
        choice: EncounterChoice,
        encounter: EncounterDefinition,
    ) -> bool:
        """Check if a choice's requirements are met."""
        requirements = choice.requirements
        
        # Check inventory requirements
        # If requires_items is a list, check if ANY item is present (for food offerings)
        requires_items = requirements.get("requires_items", [])
        if requires_items:
            inventory_set = set(state.inventory)
            # Check if at least one required item is present
            has_any = any(item in inventory_set for item in requires_items)
            if not has_any:
                return False
        
        # Check vore requirements
        requires_vore_enabled = requirements.get("requires_vore_enabled", False)
        if requires_vore_enabled and not state.vore_enabled:
            return False
        
        requires_player_pred = requirements.get("requires_player_pred_enabled", False)
        if requires_player_pred and not state.player_as_pred_enabled:
            return False
        
        # Check rapport requirements
        requires_rapport_tier = requirements.get("requires_rapport_tier")
        if requires_rapport_tier:
            # This would need creature_id context, but for now we'll skip
            # This can be enhanced later
            pass
        
        return True
    
    def apply_outcome(
        self,
        state: GameState,
        encounter: EncounterDefinition,
        outcome: EncounterOutcome,
    ) -> None:
        """
        Apply an encounter outcome to the game state.
        
        Args:
            state: The game state
            encounter: The encounter definition
            outcome: The outcome to apply
        """
        # Apply rapport changes
        for creature_id, delta in outcome.rapport_delta.items():
            change_rapport(state, creature_id, delta)
        
        # Apply stamina changes
        if outcome.stamina_delta != 0.0:
            stamina_max = state.character.get_stat(
                "stamina_max",
                timed_modifiers=state.timed_modifiers,
                current_day=state.day,
            )
            state.stamina = max(
                0.0,
                min(stamina_max, state.stamina + outcome.stamina_delta)
            )
        
        # Apply inventory changes
        for item in outcome.inventory_add:
            state.inventory.append(item)
        
        # Remove items (only remove one instance of each)
        for item in outcome.inventory_remove:
            try:
                state.inventory.remove(item)
            except ValueError:
                # Item not in inventory, skip
                pass
        
        # Special handling: if outcome requires food offering but inventory_remove is empty,
        # remove one food item that was used (berries, nuts, or dried berries)
        if not outcome.inventory_remove and "food" in outcome.text.lower():
            # Try to remove a food item in order of preference
            food_items = ["forest_berries", "trail_nuts", "dried_berries"]
            for food_item in food_items:
                if food_item in state.inventory:
                    state.inventory.remove(food_item)
                    break
        
        # Apply condition changes (for threat encounters)
        if outcome.condition_delta != 0:
            from .combat import change_condition
            change_condition(state, outcome.condition_delta)
        
        # Apply flags (store in state if needed - for now we'll skip this)
        # This can be enhanced later to track encounter-specific state


def load_encounter_definitions(data_dir: Path, filename: str) -> List[EncounterDefinition]:
    """
    Load encounter definitions from a JSON file.
    
    Args:
        data_dir: Directory containing data files
        filename: Name of the JSON file
        
    Returns:
        List of encounter definitions
    """
    path = data_dir / filename
    if not path.exists():
        return []
    
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    
    encounters = []
    for entry in data.get("encounters", []):
        try:
            encounters.append(EncounterDefinition.from_dict(entry))
        except Exception as e:
            # Log error but continue loading other encounters
            print(f"Error loading encounter: {e}")
            continue
    
    return encounters

