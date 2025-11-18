"""Kirin NPC and fast travel system for Lost Hiker."""

from __future__ import annotations

from typing import List, Optional, Protocol

from .state import GameState
from .landmarks import Landmark, LandmarkCatalog
from .forest_memory import get_path_stability
from .encounter_outcomes import EncounterOutcome, OutcomeContext, resolve_encounter_outcome
from .vore import can_pred_swallow


class UI(Protocol):
    """UI interface for displaying messages."""

    def echo(self, text: str) -> None: ...
    def menu(self, prompt: str, options: List[str]) -> str: ...


def can_trigger_kirin_intro(state: GameState) -> bool:
    """
    Check if the Kirin intro can be triggered.
    
    Conditions:
    - Act I forest stabilization is complete (3+ runestones repaired, quest_stage >= 3)
    - kirin_interest_level is at max (3)
    - Kirin is not yet known
    
    Args:
        state: Current game state
        
    Returns:
        True if intro conditions are met
    """
    if state.kirin_known:
        return False
    
    # Check Act I completion
    if not state.act1_forest_stabilized:
        return False
    
    # Check runestone repair count
    if state.act1_repaired_runestones < 3:
        return False
    
    # Check quest stage
    if state.act1_quest_stage < 3:
        return False
    
    # Check Kirin interest level
    if state.kirin_interest_level < 3:
        return False
    
    return True


def trigger_kirin_intro(state: GameState, ui: UI, context: str = "glade") -> None:
    """
    Trigger the one-time Kirin intro scene.
    
    Args:
        state: Current game state
        ui: UI interface
        context: Where the intro is triggered ("glade" or landmark name)
    """
    if state.kirin_known:
        return  # Already met
    
    if not can_trigger_kirin_intro(state):
        return  # Conditions not met
    
    ui.echo("\n")
    ui.echo("A presence stirs at the edge of your awareness—something ancient and powerful.\n")
    ui.echo("You turn to see a magnificent creature stepping from between the trees.\n")
    ui.echo("A Forest Kirin, its coat shimmering like moonlight on water, antlers branching like living crystal.\n")
    ui.echo("It moves with impossible grace, each step silent despite its size.\n")
    ui.echo("\n")
    ui.echo("The Kirin approaches slowly, its eyes holding an intelligence that speaks of ages.\n")
    ui.echo("It stops a respectful distance away, studying you with curiosity rather than hostility.\n")
    ui.echo("You sense it is drawn here by the stabilized forest pulse—the repaired runestones have called to it.\n")
    ui.echo("\n")
    
    # Echo/radio reaction
    if state.radio_version >= 2:
        ui.echo(
            "[RADIO] \"A Kirin... I've only heard whispers. They're guardians of the deep forest, "
            "drawn to places where magic flows true. This one seems... curious about you.\"\n"
        )
    else:
        ui.echo(
            "[RADIO] Awe... reverence... ancient power... curious... watching...\n"
        )
    
    ui.echo("\n")
    ui.echo("The Kirin lowers its head slightly, a gesture of acknowledgment.\n")
    ui.echo("You understand, somehow, that it offers its aid—a way to travel between the places you've made safe.\n")
    ui.echo("\n")
    
    # Travel mode choice based on vore settings
    # Check if vore travel is available (vore enabled + high enough rapport)
    vore_travel_available = can_pred_swallow(state, "kirin")
    if state.vore_enabled and vore_travel_available:
        choice = ui.menu(
            "How would you like to travel with the Kirin?",
            [
                "Ask to travel via portal (horn-opened tree-arch)",
                "Ask to be carried inside (belly/trust-based)",
                "Decline for now",
            ],
        )
        
        if "portal" in choice.lower():
            state.kirin_travel_mode_unlocked = ["portal"]
            ui.echo(
                "\nThe Kirin's antlers glow softly, and a shimmering archway opens between two ancient trees. "
                "You understand this portal can take you to places you've made familiar.\n"
            )
        elif "inside" in choice.lower() or "belly" in choice.lower() or "carried" in choice.lower():
            state.kirin_travel_mode_unlocked = ["vore"]
            ui.echo(
                "\nThe Kirin rumbles softly, a sound of acceptance. It lowers itself, offering its belly. "
                "You understand that within its warmth, you can travel safely to places you've made familiar.\n"
            )
        else:
            state.kirin_travel_mode_unlocked = []
            ui.echo(
                "\nYou nod respectfully. The Kirin seems to understand—it will wait until you're ready.\n"
            )
    else:
        # Vore disabled - only portal option
        choice = ui.menu(
            "The Kirin offers to help you travel. Accept?",
            [
                "Yes, travel via portal",
                "Not yet",
            ],
        )
        
        if "yes" in choice.lower() or "accept" in choice.lower():
            state.kirin_travel_mode_unlocked = ["portal"]
            ui.echo(
                "\nThe Kirin's antlers glow softly, and a shimmering archway opens between two ancient trees. "
                "You understand this portal can take you to places you've made familiar.\n"
            )
        else:
            state.kirin_travel_mode_unlocked = []
            ui.echo(
                "\nYou nod respectfully. The Kirin seems to understand—it will wait until you're ready.\n"
            )
    
    # Set Kirin state
    state.kirin_known = True
    state.kirin_trust_level = 1
    if state.kirin_travel_mode_unlocked:
        state.kirin_travel_unlocked = True
    
    ui.echo("\nThe Kirin fades back into the forest, but you sense it will return when you need it.\n")
    ui.echo("\n")


def get_valid_kirin_destinations(
    state: GameState,
    landmark_catalog: LandmarkCatalog,
    current_location: Optional[str] = None,
) -> List[tuple[Optional[Landmark], str]]:
    """
    Get list of valid Kirin travel destinations.
    
    Returns both landmarks and the Glade (as a special case).
    
    Criteria for landmarks:
    - Landmark is discovered
    - Path stability >= 2 ("familiar" or "well-worn")
    
    The Glade is always available as a destination if player is at a landmark.
    
    Args:
        state: Current game state
        landmark_catalog: Catalog to look up landmarks
        current_location: Current landmark ID or "glade" (excluded from destinations)
        
    Returns:
        List of (landmark, display_name) tuples. landmark is None for Glade.
    """
    valid: List[tuple[Optional[Landmark], str]] = []
    
    # Add Glade as destination if player is at a landmark
    if current_location and current_location != "glade":
        valid.append((None, "The Glade"))
    
    # Add valid landmarks
    for landmark_id in state.discovered_landmarks:
        if landmark_id == current_location:
            continue
        
        landmark = landmark_catalog.get(landmark_id)
        if not landmark:
            continue
        
        # Check path stability
        stability = get_path_stability(state, landmark_id)
        if stability < 2:
            continue
        
        # Include if stability is high enough
        valid.append((landmark, landmark.name))
    
    # Sort by display name for consistent display
    valid.sort(key=lambda x: x[1])
    return valid


def can_use_kirin_travel(state: GameState) -> bool:
    """
    Check if the player can use Kirin travel right now.
    
    Args:
        state: Current game state
        
    Returns:
        True if travel is available (unlocked and not used today)
    """
    if not state.kirin_travel_unlocked:
        return False
    
    # Check once-per-day limit
    if state.kirin_last_travel_day == state.day:
        return False
    
    return True


def execute_kirin_travel(
    state: GameState,
    destination: Optional[Landmark],
    destination_name: str,
    ui: UI,
    travel_mode: Optional[str] = None,
) -> None:
    """
    Execute Kirin travel to a destination.
    
    Args:
        state: Current game state
        destination: Landmark to travel to, or None for Glade
        destination_name: Display name of destination
        ui: UI interface
        travel_mode: "vore" or "portal" (defaults to first available mode)
    """
    if not can_use_kirin_travel(state):
        return
    
    # Determine travel mode
    if not travel_mode:
        if state.kirin_travel_mode_unlocked:
            travel_mode = state.kirin_travel_mode_unlocked[0]
        else:
            travel_mode = "portal"  # Default fallback
    
    # Travel description based on mode
    ui.echo("\n")
    if travel_mode == "vore" and state.vore_enabled:
        ui.echo(
            "The Kirin lowers itself, and you step into its offered warmth. "
            "The world shifts around you—not movement, but something deeper. "
            "Time and space flow differently within the Kirin's embrace.\n"
        )
        ui.echo(
            "When you emerge, you find yourself at the destination, the journey having passed "
            "in a dreamlike haze. The Kirin sets you down gently, its eyes warm with understanding.\n"
        )
    else:
        ui.echo(
            "The Kirin's antlers glow with soft light, and a shimmering archway opens between the trees. "
            "You step through, and the forest shifts around you—familiar paths folding into new ones.\n"
        )
        ui.echo(
            "You emerge at your destination, the portal closing behind you with a soft chime. "
            "The Kirin watches from the edge of vision, then fades back into the forest.\n"
        )
    
    # Radio reaction
    if state.radio_version >= 2:
        ui.echo(
            "[RADIO] \"Safe travels. The Kirin's paths are ancient and true. "
            "You're in good hands.\"\n"
        )
    else:
        ui.echo(
            "[RADIO] Safe... ancient paths... trust...\n"
        )
    
    # Use TRANSPORTED outcome for location/time/stamina handling
    if destination is None:
        # Traveling to Glade
        target_zone = "glade"
        target_landmark_id = None
    else:
        # Traveling to landmark
        target_zone = "forest"  # Landmarks are in forest zone
        target_landmark_id = destination.landmark_id
        # Slightly increase path stability (forest remembers this strong link)
        from .forest_memory import ensure_minimum_stability
        ensure_minimum_stability(state, destination.landmark_id, 2)
    
    context = OutcomeContext(
        source_id="kirin",
        target_zone=target_zone,
        target_landmark_id=target_landmark_id,
    )
    
    # Note: We don't pass UI here because Kirin travel has its own flavor text
    # The outcome handler will handle location/stamina/time, but we keep our own descriptions
    resolve_encounter_outcome(
        state,
        EncounterOutcome.TRANSPORTED,
        context=context,
        ui=None,  # Use our own flavor text
    )
    
    # Mark travel as used today
    state.kirin_last_travel_day = state.day
    
    # Show arrival message
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    ui.echo(f"\nYou arrive at {destination_name}.\n")
    ui.echo(f"Stamina: {state.stamina:.0f}/{stamina_max:.0f}\n")
    ui.echo("\n")

