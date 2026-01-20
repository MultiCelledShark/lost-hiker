"""
Runestone repair system for Lost Hiker.

This module implements the Act I main quest: "Breath of the Forest"
Players repair fractured runestones to stabilize the forest's ley-line network.

## Quest Overview:
The wizard's failed portal experiment fractured runestones throughout the forest.
These stones regulate magical flow and natural cycles. Repairing them stabilizes
the region and is required to progress the main story.

## Repair Process (3 Stages):
1. **Physical Repair**: Apply primitive mortar to seal cracks
   - Requires: primitive_mortar (crafted from clay, sand, ash)
   - Effect: Glyph tracks align, stone structure restored
   
2. **Resonance Tuning**: Use HT radio to tune harmonic frequency
   - Requires: HT radio (always available)
   - Mechanic: Mini-game adjusting frequency until stable
   - Effect: Stone begins humming correctly, mortar magically sets
   
3. **Pulse Realignment**: Drink tea and meditate to restore heartbeat
   - Requires: Dream Fern tea or similar
   - Mechanic: Vision/meditation sequence
   - Effect: Stone pulses in sync with forest, full restoration

## Race-Specific Bonuses:
Different races have different advantages during repair:
- Elves: Sense correct alignment, hear harmonics
- Dwarves: Feel bass vibrations, stabilize edges
- Wolf-kin: Smell fresh vs stale clay, react to emotional tones
- Lizard-kin: Spot micro-fissures, notice flickering lights
- Cow-kin: Enhanced Echo hints, sense comfort/discomfort
- Humans: Rely entirely on Echo's guidance (no special bonuses)

## Completion Rewards:
Each repaired runestone:
- Reduces environmental hazards in local area
- Improves event safety weighting
- Lowers stamina costs in region
- Increases Echo rapport
- Improves radio signal clarity
- Attracts Kirin's interest
- Stabilizes herb growth cycles

## For Content Editors:
- Runestone definitions: data/runestones_forest.json
- Repair dialogue: Hardcoded in this file (consider extracting to JSON)
- Echo hints: get_echo_hint_for_runestone() function
- Completion effects: forest_act1.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from .state import GameState
from .landmarks import Landmark


def get_runestone_state(
    state: GameState, landmark_id: str
) -> dict[str, bool]:
    """
    Get the repair state for a runestone at a landmark.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        
    Returns:
        Dictionary with repair state flags (is_fractured, is_physically_repaired,
        is_resonance_stable, is_fully_repaired)
    """
    runestone_data = state.runestone_states.get(landmark_id, {})
    return {
        "is_fractured": runestone_data.get("is_fractured", True),
        "is_physically_repaired": runestone_data.get("is_physically_repaired", False),
        "is_resonance_stable": runestone_data.get("is_resonance_stable", False),
        "is_fully_repaired": runestone_data.get("is_fully_repaired", False),
    }


def set_runestone_state(
    state: GameState, landmark_id: str, **flags: bool
) -> None:
    """
    Update the repair state for a runestone.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        **flags: State flags to set (is_fractured, is_physically_repaired, etc.)
    """
    if landmark_id not in state.runestone_states:
        state.runestone_states[landmark_id] = {}
    state.runestone_states[landmark_id].update(flags)


def is_runestone_fractured(state: GameState, landmark: Landmark) -> bool:
    """Check if a landmark has a fractured runestone."""
    if not landmark.features.get("has_runestone"):
        return False
    runestone_state = get_runestone_state(state, landmark.landmark_id)
    return runestone_state.get("is_fractured", True)


def can_repair_runestone(state: GameState, landmark: Landmark) -> bool:
    """
    Check if the player can repair the runestone at this landmark.
    
    Args:
        state: Current game state
        landmark: The landmark containing the runestone
        
    Returns:
        True if the runestone is fractured and not yet fully repaired
    """
    if not landmark.features.get("has_runestone"):
        return False
    runestone_state = get_runestone_state(state, landmark.landmark_id)
    return (
        runestone_state.get("is_fractured", True)
        and not runestone_state.get("is_fully_repaired", False)
    )


def has_primitive_mortar(state: GameState) -> bool:
    """Check if the player has primitive_mortar in inventory."""
    return "primitive_mortar" in state.inventory


def apply_physical_repair(
    state: GameState, landmark_id: str
) -> tuple[bool, str]:
    """
    Apply the physical repair step to a runestone.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        
    Returns:
        Tuple of (success, message)
    """
    if not has_primitive_mortar(state):
        return (
            False,
            "You need primitive mortar to repair the runestone. Gather clay and sand "
            "from the creek, ash from your campfire, and craft the mortar using your gold pan.\n",
        )
    
    # Remove mortar from inventory
    try:
        state.inventory.remove("primitive_mortar")
    except ValueError:
        return (False, "You thought you had mortar, but it's not in your bag.\n")
    
    # Mark as physically repaired
    set_runestone_state(
        state, landmark_id, is_physically_repaired=True
    )
    
    message = (
        "You work the primitive mortar into the cracks and fractures of the runestone, "
        "carefully aligning the broken pieces. The gritty paste fills the gaps, binding "
        "the fragments together. The glyph tracks begin to align, though the stone still "
        "pulses with unstable magic.\n"
    )
    return (True, message)


def tune_resonance(
    state: GameState, landmark_id: str, ui
) -> tuple[bool, str]:
    """
    Perform the resonance tuning step using the radio.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        ui: UI interface for interaction
        
    Returns:
        Tuple of (success, message)
    """
    runestone_state = get_runestone_state(state, landmark_id)
    if not runestone_state.get("is_physically_repaired", False):
        return (
            False,
            "The runestone must be physically repaired before you can tune its resonance.\n",
        )
    
    ui.echo(
        "You activate your HT radio and hold it near the runestone. Static crackles, "
        "then resolves into a low, distorted hum. The frequency feels wrong—like a song "
        "played out of tune.\n"
    )
    
    # Simple tuning interaction
    if state.radio_version >= 2:
        ui.echo(
            "[RADIO] \"Steady... adjust slowly. The frequency needs to align with the stone's "
            "natural pulse,\" Echo's voice guides you through the static.\n"
        )
    else:
        ui.echo(
            "[RADIO] Warm pulse... steady... hold...\n"
        )
    
    # Simple interaction - just wait for player to hold steady
    choice = ui.menu(
        "The radio hums. What do you do?",
        ["Hold steady and adjust slowly", "Try a different frequency", "Give up"],
    )
    
    if "give up" in choice.lower():
        return (False, "You step back, the resonance still unstable.\n")
    
    if "different" in choice.lower():
        # Second attempt
        ui.echo(
            "You twist the dial, searching for the right frequency. The static shifts, "
            "then suddenly clicks into place—a clear, steady hum that matches the stone's pulse.\n"
        )
    else:
        ui.echo(
            "You hold the radio steady, making tiny adjustments. The static gradually "
            "resolves into a clear, steady hum that matches the stone's natural resonance.\n"
        )
    
    # Mark resonance as stable
    set_runestone_state(
        state, landmark_id, is_resonance_stable=True
    )
    
    if state.radio_version >= 2:
        echo_message = (
            "[RADIO] \"Perfect. The stone's resonance is stable now. One more step remains.\"\n"
        )
    else:
        echo_message = (
            "[RADIO] Resonance... stable... one step remains...\n"
        )
    
    message = (
        "The mortar glows faintly as the resonance locks into place. The runestone's "
        "magical pulse steadies, though it still feels incomplete.\n"
        + echo_message
    )
    return (True, message)


def apply_pulse_alignment(
    state: GameState, landmark_id: str
) -> tuple[bool, str]:
    """
    Apply the pulse alignment step (Phase 1 stub).
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        
    Returns:
        Tuple of (success, message)
    """
    runestone_state = get_runestone_state(state, landmark_id)
    if not runestone_state.get("is_resonance_stable", False):
        return (
            False,
            "The runestone's resonance must be stable before you can align its pulse.\n",
        )
    
    # Mark as fully repaired
    set_runestone_state(
        state,
        landmark_id,
        is_fully_repaired=True,
        is_fractured=False,
    )
    
    # Apply a simple buff (small stamina bonus for next day)
    from .character import TimedModifier
    state.timed_modifiers.append(
        TimedModifier(
            source=f"runestone_repair:{landmark_id}",
            modifiers=[{"add": {"stamina_max": 0.5}}],
            expires_on_day=state.day + 1,
        )
    )
    
    message = (
        "You place your hand on the runestone, feeling its pulse synchronize with your own heartbeat. "
        "The forest's magical grid steadies around you, distortions fading. The stone is fully repaired, "
        "its power restored. You feel a surge of energy—the forest's gratitude flowing through you.\n"
    )
    return (True, message)


def get_echo_hint_for_runestone(
    state: GameState, landmark: Landmark
) -> Optional[str]:
    """
    Get an Echo hint when examining a fractured runestone.
    
    Args:
        state: Current game state
        landmark: The landmark containing the runestone
        
    Returns:
        Echo hint message, or None if no hint should be shown
    """
    if not is_runestone_fractured(state, landmark):
        return None
    
    runestone_state = get_runestone_state(state, landmark.landmark_id)
    if runestone_state.get("is_fully_repaired", False):
        return None
    
    # Check if player has gold_pan or mortar ingredients
    has_gold_pan = "gold_pan" in state.inventory
    has_clay = "clay_lump" in state.inventory
    has_sand = "sand_handful" in state.inventory
    has_ash = "ash_scoop" in state.inventory
    has_mortar = "primitive_mortar" in state.inventory
    
    if state.radio_version >= 2:
        if has_mortar:
            return (
                "[RADIO] \"The stone needs repair. You have the mortar—use it, then tune the resonance with your radio.\"\n"
            )
        elif has_gold_pan and (has_clay or has_sand or has_ash):
            return (
                "[RADIO] \"You're close. Gather what you need: clay, sand, ash. Mix them in the pan.\"\n"
            )
        elif has_gold_pan:
            return (
                "[RADIO] \"The stone is fractured. You'll need materials to repair it—clay and sand from the creek, "
                "ash from your campfire. Mix them with the pan you found.\"\n"
            )
        else:
            return (
                "[RADIO] \"This stone is broken. To fix it, you'll need materials and tools. "
                "The creek might have what you need.\"\n"
            )
    else:
        # Radio v1 - more impressionistic
        if has_mortar:
            return (
                "[RADIO] Mortar... ready... use it... tune...\n"
            )
        elif has_gold_pan:
            return (
                "[RADIO] Clay... sand... ash... mix... repair...\n"
            )
        else:
            return (
                "[RADIO] Broken stone... needs... materials... creek...\n"
            )


def get_echo_repair_reaction(
    state: GameState, landmark_id: str
) -> str:
    """
    Get Echo's reaction when a runestone is successfully repaired.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        
    Returns:
        Echo's reaction message
    """
    if state.radio_version >= 2:
        return (
            "[RADIO] \"Well done. The forest's pulse steadies with each stone you restore. "
            "The magic flows more smoothly now. You're making a real difference.\"\n"
        )
    else:
        return (
            "[RADIO] Warm... grateful... forest... stronger... pulse... steady...\n"
        )


# ---------- Multi-Runestone Support (Phase 2) ----------


def load_runestone_definitions(data_dir: Path, filename: str = "runestones_forest.json") -> Dict[str, Dict[str, str]]:
    """
    Load runestone definitions from JSON file.
    
    Args:
        data_dir: Directory containing data files
        filename: Name of the runestones data file
        
    Returns:
        Dictionary mapping runestone IDs to their definitions
    """
    path = data_dir / filename
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    runestones = {}
    for entry in raw.get("runestones", []):
        runestone_id = entry.get("id")
        if runestone_id:
            runestones[runestone_id] = {
                "id": runestone_id,
                "landmark_id": entry.get("landmark_id", ""),
                "name": entry.get("name", runestone_id),
                "initial_state": entry.get("initial_state", "fractured"),
            }
    return runestones


def get_runestone_at_landmark(
    state: GameState, landmark: Landmark, runestone_defs: Dict[str, Dict[str, str]]
) -> Optional[Dict[str, str]]:
    """
    Get the runestone definition for a landmark, if it has one.
    
    Args:
        state: Current game state
        landmark: The landmark to check
        runestone_defs: Dictionary of runestone definitions
        
    Returns:
        Runestone definition dict, or None if landmark has no runestone
    """
    if not landmark.features.get("has_runestone"):
        return None
    # Find runestone by landmark_id
    for rs_id, rs_def in runestone_defs.items():
        if rs_def.get("landmark_id") == landmark.landmark_id:
            return rs_def
    return None


def initialize_runestone_state(
    state: GameState, landmark_id: str, runestone_defs: Dict[str, Dict[str, str]]
) -> None:
    """
    Initialize runestone state for a landmark if not already set.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark
        runestone_defs: Dictionary of runestone definitions
    """
    if landmark_id in state.runestone_states:
        return  # Already initialized
    
    # Find runestone for this landmark
    for rs_def in runestone_defs.values():
        if rs_def.get("landmark_id") == landmark_id:
            initial_state = rs_def.get("initial_state", "fractured")
            state.runestone_states[landmark_id] = {
                "is_fractured": initial_state == "fractured",
                "is_physically_repaired": False,
                "is_resonance_stable": False,
                "is_fully_repaired": False,
                "is_discovered": False,
            }
            break


def mark_runestone_discovered(state: GameState, landmark_id: str, runestone_defs: Dict[str, Dict[str, str]]) -> None:
    """
    Mark a runestone as discovered and update quest stage.
    
    Args:
        state: Current game state
        landmark_id: ID of the landmark containing the runestone
        runestone_defs: Dictionary of runestone definitions
    """
    if landmark_id not in state.runestone_states:
        state.runestone_states[landmark_id] = {}
    state.runestone_states[landmark_id]["is_discovered"] = True
    
    # Find the runestone ID for this landmark
    runestone_id = None
    for rs_id, rs_def in runestone_defs.items():
        if rs_def.get("landmark_id") == landmark_id:
            runestone_id = rs_id
            break
    
    # Update forest_act1 state
    from .forest_act1 import update_forest_act1_on_runestone_found
    update_forest_act1_on_runestone_found(state, runestone_id or landmark_id, len(runestone_defs))
    
    # Legacy compatibility: also update old fields
    if state.act1_total_runestones == 0:
        state.act1_total_runestones = len(runestone_defs)
    if state.act1_quest_stage == 0:
        state.act1_quest_stage = 1


def get_repaired_runestone_count(state: GameState) -> int:
    """
    Count how many runestones have been fully repaired.
    
    Args:
        state: Current game state
        
    Returns:
        Number of fully repaired runestones
    """
    count = 0
    for landmark_id, rs_state in state.runestone_states.items():
        if rs_state.get("is_fully_repaired", False):
            count += 1
    return count


def update_quest_state_after_repair(state: GameState, runestone_defs: Dict[str, Dict[str, str]]) -> None:
    """
    Update Act I quest state after a runestone is repaired.
    
    Args:
        state: Current game state
        runestone_defs: Dictionary of runestone definitions
    """
    # Count total runestones
    total_runestones = len(runestone_defs)
    if state.act1_total_runestones == 0:
        state.act1_total_runestones = total_runestones
    
    # Count repaired runestones
    repaired_count = get_repaired_runestone_count(state)
    
    # Find the runestone ID for the current landmark (if available)
    runestone_id = None
    if state.current_landmark:
        for rs_id, rs_def in runestone_defs.items():
            if rs_def.get("landmark_id") == state.current_landmark:
                runestone_id = rs_id
                break
    
    # Update forest_act1 state
    from .forest_act1 import update_forest_act1_on_runestone_repair
    update_forest_act1_on_runestone_repair(
        state, runestone_id or state.current_landmark or "unknown", total_runestones
    )
    
    # Legacy compatibility: also update old fields
    state.act1_repaired_runestones = repaired_count
    
    # Update quest stage
    if repaired_count >= 1 and state.act1_quest_stage < 2:
        state.act1_quest_stage = 2
    
    # Update Kirin interest level
    if repaired_count >= 1 and state.kirin_interest_level < 1:
        state.kirin_interest_level = 1
    elif repaired_count >= 2 and state.kirin_interest_level < 2:
        state.kirin_interest_level = 2
    elif repaired_count >= 3 and state.kirin_interest_level < 3:
        state.kirin_interest_level = 3
    
    # Check for Act I completion (3 repaired stones)
    if repaired_count >= 3 and not state.act1_forest_stabilized:
        state.act1_quest_stage = 3
        state.act1_forest_stabilized = True


def is_runestone_repairable(state: GameState, landmark: Landmark) -> bool:
    """
    Check if a runestone can be repaired (alias for can_repair_runestone for consistency).
    
    Args:
        state: Current game state
        landmark: The landmark containing the runestone
        
    Returns:
        True if the runestone can be repaired
    """
    return can_repair_runestone(state, landmark)

