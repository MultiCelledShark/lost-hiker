"""Wayfinding tea teleportation system for Lost Hiker."""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple

from .state import GameState
from .landmarks import Landmark, LandmarkCatalog
from .forest_memory import get_path_stability
from .forest_effects import get_max_reliable_depth, should_allow_deep_depth_roll
from .encounter_outcomes import EncounterOutcome, OutcomeContext, resolve_encounter_outcome
from .hunger import apply_stamina_cap


class UI(Protocol):
    """UI interface for displaying messages."""

    def echo(self, text: str) -> None: ...
    def menu(self, prompt: str, options: List[str]) -> str: ...


def can_use_wayfinding(state: GameState) -> bool:
    """
    Check if the player can use wayfinding right now.
    
    Conditions:
    - wayfinding_ready is True (player drank wayfinding_tea)
    - At least 1 runestone is repaired in the Forest
    
    Args:
        state: Current game state
        
    Returns:
        True if wayfinding is available
    """
    if not state.wayfinding_ready:
        return False
    
    # Require at least 1 repaired runestone
    if state.act1_repaired_runestones < 1:
        return False
    
    return True


def get_valid_wayfinding_destinations(
    state: GameState,
    landmark_catalog: LandmarkCatalog,
    current_location: Optional[str] = None,
) -> List[Tuple[Landmark, str]]:
    """
    Get list of valid wayfinding teleport destinations.
    
    Criteria for landmarks:
    - Landmark is discovered
    - Path stability >= 2 ("familiar" or "well-worn")
    - Landmark is in the Forest zone
    - Landmark depth is accessible based on runestone progression
    - Not the current location
    
    Args:
        state: Current game state
        landmark_catalog: Catalog to look up landmarks
        current_location: Current landmark ID or None (excluded from destinations)
        
    Returns:
        List of (landmark, display_name) tuples, sorted by name
    """
    valid: List[Tuple[Landmark, str]] = []
    
    # Only allow wayfinding in Forest zone
    if state.active_zone != "forest":
        return valid
    
    for landmark_id in state.discovered_landmarks:
        if landmark_id == current_location:
            continue
        
        landmark = landmark_catalog.get(landmark_id)
        if not landmark:
            continue
        
        # Check path stability (must be >= 2 for wayfinding)
        stability = get_path_stability(state, landmark_id)
        if stability < 2:
            continue
        
        # Check depth gating - respect runestone-based progression
        # Only allow teleport to landmarks in depth bands that would already be reachable
        max_reliable_depth = get_max_reliable_depth(state)
        
        # Check if landmark is within accessible depth range
        # If landmark's minimum depth exceeds reliable depth, check if it's allowed
        if landmark.depth_min > max_reliable_depth:
            # Check if this specific depth would be allowed (soft gate)
            if not should_allow_deep_depth_roll(state, landmark.depth_min):
                continue
        
        # Include if all checks pass
        valid.append((landmark, landmark.name))
    
    # Sort by display name for consistent display
    valid.sort(key=lambda x: x[1])
    return valid


def execute_wayfinding_teleport(
    state: GameState,
    landmark_catalog: LandmarkCatalog,
    destination: Landmark,
    destination_name: str,
    ui: UI,
) -> None:
    """
    Execute wayfinding teleport to a destination.
    
    The caller should validate that the destination is valid before calling this.
    
    Args:
        state: Current game state
        landmark_catalog: Catalog to look up landmarks (for validation)
        destination: Landmark to teleport to
        destination_name: Display name of destination
        ui: UI interface
    """
    if not can_use_wayfinding(state):
        return
    
    # Validate destination is in valid list
    current_location = state.current_landmark
    valid_destinations = get_valid_wayfinding_destinations(
        state, 
        landmark_catalog,
        current_location
    )
    
    # Find destination in valid list
    valid_landmarks = [lm for lm, _ in valid_destinations]
    if destination not in valid_landmarks:
        ui.echo("The Forest resists your attempt to reach that place. The path is not clear enough, or too far beyond your progress.\n")
        return
    
    # Teleport description
    ui.echo("\n")
    ui.echo("The paths of the Forest fold around you—not movement, but memory made real.\n")
    ui.echo("Places you've walked before overlap with where you stand now.\n")
    ui.echo("You step through the space between, and the Forest remembers.\n")
    ui.echo("\n")
    
    # Use TRANSPORTED outcome for location/stamina handling
    context = OutcomeContext(
        source_id="wayfinding_tea",
        target_zone="forest",  # Landmarks are in forest zone
        target_landmark_id=destination.landmark_id,
    )
    
    # Note: We don't pass UI here because wayfinding has its own flavor text
    # The outcome handler will handle location/stamina, but we keep our own descriptions
    resolve_encounter_outcome(
        state,
        EncounterOutcome.TRANSPORTED,
        context=context,
        ui=None,  # Use our own flavor text
    )
    
    # Clear wayfinding_ready (one-time use per tea)
    state.wayfinding_ready = False
    
    # Show arrival message
    base_stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    # Apply caps (rest, hunger, condition) to get actual maximum
    capped_stamina_max = apply_stamina_cap(state, base_stamina_max)
    ui.echo(f"You arrive at {destination_name}.\n")
    ui.echo(f"Stamina: {state.stamina:.0f}/{capped_stamina_max:.0f}\n")
    ui.echo("\n")
