"""Unified encounter outcome framework for Lost Hiker.

This module centralizes all encounter resolution logic, including retreats,
collapses, sheltered rest, and transportation. The framework is designed to
be vore-ready but vore-free in this phase.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Protocol

from .state import GameState
from .vore import is_vore_enabled, is_player_pred_enabled


class EncounterOutcome(Enum):
    """Standardized encounter outcome types."""
    
    NORMAL = "NORMAL"  # Encounter ends, player remains where they are
    RETREAT = "RETREAT"  # Forced retreat to safer location
    COLLAPSE = "COLLAPSE"  # Player blacks out, wakes later in safe place
    SHELTERED = "SHELTERED"  # Player ends up in safe, protected state for a time
    TRANSPORTED = "TRANSPORTED"  # Player moved to different landmark/zone


class UI(Protocol):
    """UI interface for displaying messages."""
    
    def echo(self, text: str) -> None: ...
    def heading(self, text: str) -> None: ...


@dataclass
class OutcomeContext:
    """Context information for encounter outcomes."""
    
    # Source of the outcome (creature_id, npc_id, etc.)
    source_id: Optional[str] = None
    
    # Target location for TRANSPORTED
    target_landmark_id: Optional[str] = None
    target_zone: Optional[str] = None
    
    # Flags for outcome behavior
    was_safe_shelter: bool = False  # For SHELTERED outcomes
    collapse_severity: float = 1.0  # For COLLAPSE outcomes (1.0 = normal)
    
    # Additional metadata
    metadata: Dict[str, object] = field(default_factory=dict)


def is_vore_enabled(state: GameState) -> bool:
    """
    Check if vore content is enabled.
    
    Args:
        state: Current game state
        
    Returns:
        True if vore is enabled
    """
    return state.vore_enabled


def is_pred_enabled(state: GameState) -> bool:
    """
    Check if player-as-predator content is enabled.
    
    Args:
        state: Current game state
        
    Returns:
        True if player-as-predator is enabled
    """
    return state.player_as_pred_enabled


def resolve_encounter_outcome(
    state: GameState,
    outcome: EncounterOutcome,
    context: Optional[OutcomeContext] = None,
    ui: Optional[UI] = None,
) -> None:
    """
    Central handler for encounter outcomes.
    
    This function coordinates location, time, stamina, condition, and other
    state changes based on the outcome type.
    
    Args:
        state: Current game state
        outcome: The outcome type to resolve
        context: Optional context with additional information
        ui: Optional UI interface for displaying messages
    """
    if context is None:
        context = OutcomeContext()
    
    if outcome == EncounterOutcome.NORMAL:
        _do_normal_outcome(state, context, ui)
    elif outcome == EncounterOutcome.RETREAT:
        _do_retreat(state, context, ui)
    elif outcome == EncounterOutcome.COLLAPSE:
        _do_collapse(state, context, ui)
    elif outcome == EncounterOutcome.SHELTERED:
        _do_sheltered_rest(state, context, ui)
    elif outcome == EncounterOutcome.TRANSPORTED:
        _do_transport(state, context, ui)
    else:
        # Unknown outcome - log warning and treat as NORMAL
        if ui:
            ui.echo("(Unknown outcome type - treating as normal)\n")
        _do_normal_outcome(state, context, ui)


def _do_normal_outcome(
    state: GameState,
    context: OutcomeContext,
    ui: Optional[UI],
) -> None:
    """
    Handle NORMAL outcome - minimal/no special handling.
    
    Args:
        state: Current game state
        context: Outcome context
        ui: Optional UI interface
    """
    # NORMAL outcome does nothing special - encounter just ends
    # Clear sheltered flag if set (player is back in normal outdoor conditions)
    state.is_sheltered = False


def _do_retreat(
    state: GameState,
    context: OutcomeContext,
    ui: Optional[UI],
) -> None:
    """
    Handle RETREAT outcome - move player to safer location with stamina penalties.
    
    Args:
        state: Current game state
        context: Outcome context
        ui: Optional UI interface
    """
    # Clear sheltered flag (retreat moves player to normal outdoor conditions)
    state.is_sheltered = False
    
    # Determine retreat destination
    current_zone = state.active_zone
    current_depth = state.zone_depths.get(current_zone, 0)
    
    # Default: retreat to Glade if in forest, or reduce depth by 1-2 steps
    if current_zone == "forest" and current_depth > 0:
        # Retreat to shallower depth (reduce by 1-2, minimum 0)
        retreat_depth = max(0, current_depth - random.randint(1, 2))
        state.zone_depths[current_zone] = retreat_depth
        
        if ui:
            ui.echo(
                "You retreat to safer ground, your heart pounding. "
                "The forest feels less threatening here.\n"
            )
    else:
        # Retreat to Glade
        state.active_zone = "glade"
        state.current_landmark = None
        state.zone_depths.pop(current_zone, None)
        
        if ui:
            ui.echo(
                "You retreat back to the Glade, shaken but safe. "
                "The familiar clearing offers some comfort.\n"
            )
    
    # Apply stamina penalty (retreat is exhausting)
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    stamina_loss = max(1.0, stamina_max * 0.15)  # 15% of max stamina, minimum 1
    state.stamina = max(0.0, state.stamina - stamina_loss)
    
    # Slight condition increase from stress
    from .combat import change_condition
    if random.random() < 0.3:  # 30% chance of minor condition increase
        change_condition(state, 1)


def _do_collapse(
    state: GameState,
    context: OutcomeContext,
    ui: Optional[UI],
) -> None:
    """
    Handle COLLAPSE outcome - move player to safe location, drain stamina.
    
    Note: Day advancement is handled by the caller (e.g., _summarize_day),
    as it requires season_config which is not available in this module.
    
    Args:
        state: Current game state
        context: Outcome context
        ui: Optional UI interface
    """
    # Clear sheltered flag (collapse moves player to normal outdoor conditions)
    state.is_sheltered = False
    
    # Move to safe location (usually Glade)
    current_zone = state.active_zone
    state.active_zone = "glade"
    state.current_landmark = None
    state.zone_depths.pop(current_zone, None)
    
    # Track collapse rest type
    state.rest_type = "collapse"
    
    # Set stamina to low but non-zero value (50% of max, or floor based on severity)
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    severity = context.collapse_severity if context else 1.0
    stamina_restored = max(0.0, math.floor(stamina_max * 0.5 * severity))
    state.stamina = stamina_restored
    
    # Increase condition (collapse is rough)
    from .combat import change_condition
    condition_increase = 1 if severity >= 1.0 else 0
    if condition_increase > 0:
        change_condition(state, condition_increase)
    
    # Collapse flavor text
    if ui:
        dream_roll = random.random()
        dream_text = ""
        if dream_roll < 0.2:
            dream_text = "A strange dream of winding roots and distant hissing clings to your thoughts.\n"
        
        rescue_roll = random.random()
        if rescue_roll < 0.25:
            # Glade rescue
            ui.echo(
                "You wake in the Glade, unsure how you got here. "
                "Someone—or something—must have found you and brought you to safety.\n"
            )
            if dream_text:
                ui.echo(dream_text)
        elif rescue_roll < 0.35:
            # Echo protection
            ui.echo(
                "Echo's silent shape loops around you as you come to. "
                "She must have watched over you while you were unconscious.\n"
            )
            if dream_text:
                ui.echo(dream_text)
        else:
            # Generic collapse recovery
            ui.echo(
                "You come to slowly, your body aching. "
                "You're in the Glade, though you don't remember how you got here.\n"
            )
            if dream_text:
                ui.echo(dream_text)


def _do_sheltered_rest(
    state: GameState,
    context: OutcomeContext,
    ui: Optional[UI],
) -> None:
    """
    Handle SHELTERED outcome - safe forced rest with time passing.
    
    This is a generic "safe but forced rest" outcome. In future phases,
    this can be flavored as belly-rest when vore is enabled, but for now
    it uses generic shelter descriptions (hidden grove, burrow, tree hollow, etc.).
    
    Note: Day advancement should be handled by the caller if needed,
    as it requires season_config which is not available in this module.
    
    Args:
        state: Current game state
        context: Outcome context
        ui: Optional UI interface
    """
    # Set sheltered flag (player is now in enclosed/sheltered state)
    state.is_sheltered = True
    
    # Restore stamina (sheltered rest is restorative)
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    stamina_restored = max(0.0, math.floor(stamina_max * 0.75))  # 75% restoration
    state.stamina = stamina_restored
    
    # Track as camp rest (good rest)
    state.rest_type = "camp"
    
    # Slight condition recovery (shelter is safe)
    from .combat import recover_condition_at_camp
    recover_condition_at_camp(state)
    
    # Generic shelter flavor text (non-vore)
    # Skip generic text if this is an Echo belly shelter (echo_vore handles its own text)
    if ui and not context.metadata.get("echo_belly", False):
        shelter_types = [
            "a hidden grove",
            "a natural burrow",
            "a tree hollow",
            "a protective thicket",
            "a sheltered alcove",
        ]
        shelter = random.choice(shelter_types)
        
        base_text = (
            f"You find yourself in {shelter}, safe and protected. "
            "Time passes in a blur—when you emerge, you feel more rested, "
            "though you're not entirely sure how long you were there.\n"
        )
        ui.echo(base_text)
        
        # Add optional tag-based resting flavor
        try:
            from .flavor_profiles import get_resting_flavor
            flavor_text = get_resting_flavor(state.character, context="sheltered")
            if flavor_text:
                ui.echo(f"{flavor_text}\n")
        except Exception:
            pass


def _do_transport(
    state: GameState,
    context: OutcomeContext,
    ui: Optional[UI],
) -> None:
    """
    Handle TRANSPORTED outcome - move player to target location.
    
    Args:
        state: Current game state
        context: Outcome context (must include target_landmark_id or target_zone)
        ui: Optional UI interface
    """
    # Clear sheltered flag (transport moves player to normal outdoor conditions)
    state.is_sheltered = False
    
    # Validate target
    target_landmark_id = context.target_landmark_id if context else None
    target_zone = context.target_zone if context else None
    
    if not target_landmark_id and not target_zone:
        # No target specified - fall back to Glade
        if ui:
            ui.echo("(Transport destination unclear - returning to Glade)\n")
        target_zone = "glade"
        target_landmark_id = None
    
    # Update location
    if target_landmark_id:
        state.current_landmark = target_landmark_id
        state.active_zone = target_zone or "forest"
    else:
        state.current_landmark = None
        state.active_zone = target_zone or "glade"
    
    # Clear zone depths (transport resets exploration depth)
    state.zone_depths.pop(state.active_zone, None)
    
    # Apply stamina cost (transportation is not free)
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    stamina_cost = max(1.0, stamina_max * 0.1)  # 10% of max stamina, minimum 1
    state.stamina = max(0.0, state.stamina - stamina_cost)
    
    # Note: Transport flavor text is handled by the calling system
    # (Kirin, wayfinding tea, etc.) to maintain their unique descriptions

