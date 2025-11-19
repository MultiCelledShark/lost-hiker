"""Belly interaction system for Lost Hiker - Phase 1.

This module handles the belly interaction loop that occurs when the player
is swallowed by a predator (non-lethal) or Echo (shelter). The system provides
simple text-based commands: soothe, struggle, relax, and call (if HT radio available).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .encounter_outcomes import (
    EncounterOutcome as EncounterOutcomeEnum,
    OutcomeContext,
    UI,
    resolve_encounter_outcome,
)
from .vore import is_vore_enabled
from .rapport import change_rapport, get_rapport

if TYPE_CHECKING:
    from .character import Character
    from .state import GameState

ECHO_ID = "echo"
_races_cache: Optional[dict[str, dict[str, object]]] = None


def _load_races_if_needed() -> Optional[dict[str, dict[str, object]]]:
    """Load races data if not already cached."""
    global _races_cache
    if _races_cache is not None:
        return _races_cache
    try:
        # Try to find data directory relative to this module
        from . import main
        data_dir, _ = main.resolve_paths()
        races_path = data_dir / "races.json"
        if races_path.exists():
            with races_path.open("r", encoding="utf-8") as handle:
                _races_cache = json.load(handle)
                return _races_cache
    except Exception:
        pass
    return None


def _get_echo_belly_race_flavor(race_id: str) -> Optional[str]:
    """
    Get race-aware flavor text for Echo's belly interactions.
    
    Returns Echo's race-aware comments when the player is in her belly.
    These are flavor-only lines that can be sprinkled into existing belly text.
    
    Args:
        race_id: Player's race ID
        
    Returns:
        Optional race-aware flavor text, or None if no race-specific variant exists
    """
    race_flavor_map = {
        "human": "You fit easily. Soft. Rest — I'll carry you.",
        "wolf_kin": "All that fur. Warm… stop thrashing, you're fluffing my throat.",
        "cow_kin": "Heavy, but pleasant. Settle in. I'll tighten the coils.",
        "elf": "You hum against me. Is that magic, or nerves?",
        "dwarf": "Dense little thing. Like a river stone. Don't wedge yourself.",
        "lizard_folk": "Cool scales. I'll warm you up. Don't worry.",
        "deer_kin": "Your heartbeat flutters. Calm — nothing will reach you in here.",
        "fox_kin": "Twitchy tail. You're impossible to hold still. Let me squeeze closer…",
        "gryphon_folk": "Feathers everywhere. I should have expected that. I can manage.",
        "dragonborn": "You radiate heat. Strange, but pleasant. Stay as long as you like.",
    }
    
    return race_flavor_map.get(race_id)


def _get_echo_belly_tag_family_flavor(character: "Character") -> Optional[str]:
    """
    Get tag family-aware flavor text for Echo's belly interactions.
    
    Returns Echo's comments about tag families (fungal, ooze, synth, elemental, psionic)
    when the player is in her belly. These reinforce the Forest's size-bending lore.
    
    Args:
        character: Player character with flavor_tags
        
    Returns:
        Optional tag family-aware flavor text, or None
    """
    from .dialogue import is_fungal, is_ooze, is_synth, is_elemental, is_psionic
    
    if is_fungal(character):
        return random.choice([
            "You spread evenly inside me—mycelial, earthy. The Forest feels you more vividly here. The ground recognizes you as kin.",
            "Spores drift in the warmth. The Forest watches through you, even in here. You're connected to something deeper.",
        ])
    
    if is_ooze(character):
        return random.choice([
            "You flow and adjust—slippery, but the Forest makes space. You spread evenly, fitting where you need to fit.",
            "Your form shifts and adapts. The Forest stretches my belly to accommodate you. Physics doesn't apply here.",
        ])
    
    if is_synth(character):
        return random.choice([
            "Your resonance hums against me—mechanical, but warm. The Forest accepted you, and so do I. You fit perfectly.",
            "There's a steady pulse, a vibration. Not flesh, but alive. The Forest doesn't care about such distinctions.",
        ])
    
    if is_elemental(character):
        player_tags = set(character.flavor_tags)
        if "emberheart" in player_tags:
            return "You radiate warmth—gentle heat that spreads through me. The Forest amplifies it. Comforting."
        elif "frostbreath" in player_tags:
            return "A cool presence, but not unpleasant. The chill is gentle, balanced. The Forest moderates everything."
        elif "stormtouched" in player_tags or "mistborne" in player_tags:
            return "There's a tingle, a crackle—elemental energy. The Forest channels it safely. You're safe here."
        return "Elemental power flows through you. The Forest recognizes it, channels it. You're safe here."
    
    if is_psionic(character):
        return random.choice([
            "Your thoughts brush against mine—faint impressions, shared dreams. The Forest bends minds as easily as space. We're connected.",
            "Mental echoes resonate. The radio translates some of it, but there's more. The Forest makes strange connections.",
        ])
    
    return None


def _get_echo_belly_body_type_flavor(character: "Character") -> Optional[str]:
    """
    Get body type-aware flavor text for Echo's belly interactions.
    
    Returns Echo's comments about body types (taur, naga, quadruped) when the player
    is in her belly. These reinforce how the Forest bends size and space.
    
    Args:
        character: Player character with body_type
        
    Returns:
        Optional body type-aware flavor text, or None
    """
    body_type = character.body_type
    
    if body_type == "naga":
        return random.choice([
            "You coil inside me—familiar, serpentine. Your coils fold and curl, fitting perfectly. The Forest recognizes our kinship.",
            "Two serpents, one inside the other. Your coils settle naturally. The Forest makes space for what belongs together.",
        ])
    
    if body_type == "taur":
        return random.choice([
            "Your bulk is substantial, but the Forest stretches space. You fit where you shouldn't. Size is just a suggestion here.",
            "Four legs, strong frame—but you settle in comfortably. The Forest makes room. It always does.",
        ])
    
    if body_type == "quadruped":
        return random.choice([
            "You curl up inside me—four legs tucked close. The Forest accepts all forms. You fit perfectly.",
            "Your quadruped form compresses naturally. The Forest doesn't care about how many limbs you have—you're safe here.",
        ])
    
    return None


def _get_race_belly_flavor(
    race_id: str,
    races: dict[str, dict[str, object]],
    action: str,  # "enter", "soothe", "struggle", "relax"
) -> Optional[str]:
    """
    Get optional race-specific flavor text for non-Echo belly interactions.
    
    Args:
        race_id: The player's race ID
        races: Full races.json data
        action: The belly action being performed
        
    Returns:
        Optional flavor text string, or None
    """
    from .race_flavor import get_belly_flavor
    races_data = races or {}
    return get_belly_flavor(race_id, races_data, action)


def is_belly_active(state: GameState) -> bool:
    """Check if the player is currently in belly interaction mode."""
    return (
        state.belly_state is not None
        and state.belly_state.get("active", False)
    )


def enter_belly_state(
    state: GameState,
    creature_id: str,
    mode: str,  # "predator", "echo", or "friend"
    ui: Optional[UI] = None,
) -> None:
    """
    Enter belly interaction state.
    
    Args:
        state: Current game state
        creature_id: ID of the creature that swallowed the player
        mode: Belly mode ("predator", "echo", or "friend")
        ui: Optional UI interface for displaying messages
    """
    # Record current location
    depth_before = state.zone_depths.get(state.active_zone, 0)
    landmark_before = state.current_landmark
    
    state.belly_state = {
        "active": True,
        "creature_id": creature_id,
        "mode": mode,
        "depth_before": depth_before,
        "landmark_before": landmark_before,
        "turns_inside": 0,
    }
    
    # Set sheltered flag
    state.is_sheltered = True
    
    # Show initial description
    if ui:
        if mode == "echo":
            base_text = (
                "\nYou find yourself in a warm, dark space. "
                "Echo's presence surrounds you—gentle, protective, safe. "
                "The rhythmic pulse of her breathing is steady and calming.\n"
            )
            # Add optional race-aware flavor (keep old system for Echo's radio comments)
            race_flavor = _get_echo_belly_race_flavor(state.character.race_id)
            if race_flavor and random.random() < 0.5:  # 50% chance to show race flavor
                ui.echo(f"[RADIO] {race_flavor}\n")
            
            # Add optional tag family-aware flavor (prioritize tag families over body type)
            tag_family_flavor = _get_echo_belly_tag_family_flavor(state.character)
            if tag_family_flavor and random.random() < 0.4:  # 40% chance
                ui.echo(f"[RADIO] {tag_family_flavor}\n")
            elif not tag_family_flavor:
                # If no tag family flavor, try body type flavor
                body_type_flavor = _get_echo_belly_body_type_flavor(state.character)
                if body_type_flavor and random.random() < 0.3:  # 30% chance
                    ui.echo(f"[RADIO] {body_type_flavor}\n")
            
            ui.echo(base_text)
            
            # Add optional tag-based belly flavor
            try:
                from .flavor_profiles import get_belly_flavor
                flavor_text = get_belly_flavor(state.character, "enter", is_predator=False)
                if flavor_text:
                    ui.echo(f"{flavor_text}\n")
            except Exception:
                pass
        elif mode == "predator":
            creature_name = creature_id.replace("_", " ").title()
            base_text = (
                f"\nYou're pulled into darkness, warmth, and a crushing pressure "
                f"that's somehow not suffocating. The {creature_name} carries you "
                "through the forest, and you're helpless but safe—for now.\n"
            )
            ui.echo(base_text)
            
            # Add optional tag-based belly flavor
            try:
                from .flavor_profiles import get_belly_flavor
                flavor_text = get_belly_flavor(state.character, "enter", is_predator=False)
                if flavor_text:
                    ui.echo(f"{flavor_text}\n")
            except Exception:
                pass
        else:  # friend mode
            creature_name = creature_id.replace("_", " ").title()
            base_text = (
                f"\nThe {creature_name} has taken you in, offering warmth and shelter. "
                "You're safe here, though the experience is still disorienting.\n"
            )
            ui.echo(base_text)
            
            # Add optional tag-based belly flavor
            try:
                from .flavor_profiles import get_belly_flavor
                flavor_text = get_belly_flavor(state.character, "enter", is_predator=False)
                if flavor_text:
                    ui.echo(f"{flavor_text}\n")
            except Exception:
                pass


def exit_belly_state(state: GameState) -> None:
    """Exit belly interaction state."""
    state.belly_state = None
    state.is_sheltered = False


def handle_belly_action(
    state: GameState,
    action: str,  # "soothe", "struggle", "relax", "call"
    ui: UI,
    creatures: dict[str, dict[str, object]],
) -> bool:
    """
    Handle a belly interaction action.
    
    Args:
        state: Current game state
        action: Action to perform
        ui: UI interface
        creatures: Creature data dictionary
        
    Returns:
        True if the belly interaction should end, False to continue
    """
    if not is_belly_active(state):
        return True
    
    belly = state.belly_state
    creature_id = belly["creature_id"]
    mode = belly["mode"]
    belly["turns_inside"] = belly.get("turns_inside", 0) + 1
    
    creature_data = creatures.get(creature_id, {})
    creature_name = creature_data.get("name", creature_id.replace("_", " ").title())
    
    if action == "soothe":
        return _handle_soothe(state, creature_id, mode, creature_name, ui, creatures)
    elif action == "struggle":
        return _handle_struggle(state, creature_id, mode, creature_name, ui, creatures)
    elif action == "relax":
        return _handle_relax(state, creature_id, mode, creature_name, ui, creatures)
    elif action == "call":
        return _handle_call(state, creature_id, mode, creature_name, ui)
    else:
        ui.echo("Unknown action. Try: soothe, struggle, relax, or call.\n")
        return False


def _handle_soothe(
    state: GameState,
    creature_id: str,
    mode: str,
    creature_name: str,
    ui: UI,
    creatures: dict[str, dict[str, object]],
) -> bool:
    """Handle soothe action in belly."""
    if mode == "echo":
        # Echo is already calm
        base_text = (
            "[RADIO] A warm, contented pulse. Echo's presence is already calm and gentle. "
            "You feel safe and protected here.\n"
        )
        # Optional race-aware flavor
        race_flavor = _get_echo_belly_race_flavor(state.character.race_id)
        if race_flavor and random.random() < 0.3:  # 30% chance to show race flavor
            ui.echo(f"[RADIO] {race_flavor}\n")
        
        # Add optional tag family or body type flavor
        tag_family_flavor = _get_echo_belly_tag_family_flavor(state.character)
        if tag_family_flavor and random.random() < 0.3:  # 30% chance
            ui.echo(f"[RADIO] {tag_family_flavor}\n")
        elif not tag_family_flavor:
            body_type_flavor = _get_echo_belly_body_type_flavor(state.character)
            if body_type_flavor and random.random() < 0.25:  # 25% chance
                ui.echo(f"[RADIO] {body_type_flavor}\n")
        
        ui.echo(base_text)
        return False
    
    # For predators, attempt to calm them
    creature_data = creatures.get(creature_id, {})
    is_friendly_belly = creature_data.get("is_friendly_belly", False)
    
    # Base success chance - friendly bellies are easier to soothe
    success_chance = 0.5 if is_friendly_belly else 0.3
    
    # Rapport bonus (if creature has rapport)
    rapport = get_rapport(state, creature_id)
    if rapport > 0:
        success_chance += min(0.2, rapport * 0.05)
    
    if random.random() < success_chance:
        # Success: creature calms and releases nearby
        ui.echo(
            f"The {creature_name} seems to respond to your gentle presence. "
            "The pressure around you eases, and you feel movement. "
            "Slowly, carefully, you're released back into the forest.\n"
        )
        
        # Small rapport/comfort gain
        if rapport < 3:
            change_rapport(state, creature_id, 1)
        
        # Release at nearby location (same depth band)
        _release_at_nearby_location(state, creature_id, ui, transported=False)
        exit_belly_state(state)
        return True
    else:
        # Failed: jostled, stamina cost
        stamina_max = state.character.get_stat(
            "stamina_max",
            timed_modifiers=state.timed_modifiers,
            current_day=state.day,
        )
        stamina_cost = max(1.0, stamina_max * 0.05)  # 5% of max stamina
        state.stamina = max(0.0, state.stamina - stamina_cost)
        
        ui.echo(
            f"The {creature_name} shifts restlessly. Your attempts to calm it "
            "only seem to make it more agitated. You're jostled around, "
            "and the movement costs you some energy.\n"
        )
        return False


def _handle_struggle(
    state: GameState,
    creature_id: str,
    mode: str,
    creature_name: str,
    ui: UI,
    creatures: dict[str, dict[str, object]],
) -> bool:
    """Handle struggle action in belly."""
    if mode == "echo":
        # Echo gently pins player
        ui.echo(
            "[RADIO] A soft, amused pulse. Echo's warmth tightens slightly—not threatening, "
            "but clearly indicating you should stay still. She's not letting you go yet.\n"
        )
        return False
    
    # For predators, attempt to force release
    creature_data = creatures.get(creature_id, {})
    threat_tier = creature_data.get("threat_tier", 2)
    size_class = creature_data.get("size_class", "medium")
    
    # Strong predators (threat_tier 3+, large/huge) are harder to escape from
    is_strong = threat_tier >= 3 or size_class in ("large", "huge")
    
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    
    if is_strong:
        # Strong predators: mostly just jostling and transport
        stamina_cost = max(2.0, stamina_max * 0.15)  # 15% of max stamina
        state.stamina = max(0.0, state.stamina - stamina_cost)
        
        ui.echo(
            f"The {creature_name} barely notices your struggles. You're shaken up "
            "and tossed around, but it's clear you're not getting out this way. "
            "The creature seems to be relocating you instead.\n"
        )
        
        # Transport to nearby landmark
        _release_at_nearby_location(state, creature_id, ui, transported=True)
        exit_belly_state(state)
        return True
    else:
        # Weaker predators: chance of early release
        success_chance = 0.5
        stamina_cost = max(1.5, stamina_max * 0.10)  # 10% of max stamina
        state.stamina = max(0.0, state.stamina - stamina_cost)
        
        if random.random() < success_chance:
            # Success: forced release
            ui.echo(
                f"Your struggles pay off! The {creature_name} seems surprised by your "
                "resistance and releases you. You tumble out, landing roughly but free.\n"
            )
            _release_at_nearby_location(state, creature_id, ui, transported=False)
            exit_belly_state(state)
            return True
        else:
            # Failed: jostled
            ui.echo(
                f"You struggle, but the {creature_name} holds firm. You're shaken around "
                "and exhausted, though still trapped.\n"
            )
            return False


def _handle_relax(
    state: GameState,
    creature_id: str,
    mode: str,
    creature_name: str,
    ui: UI,
    creatures: dict[str, dict[str, object]],
) -> bool:
    """Handle relax action in belly."""
    if mode == "echo":
        # Echo mode: restful night at Glade
        # Optional race-aware flavor before the main text
        race_flavor = _get_echo_belly_race_flavor(state.character.race_id)
        if race_flavor and random.random() < 0.5:  # 50% chance to show race flavor
            ui.echo(f"[RADIO] {race_flavor}\n")
        
        # Add optional tag family or body type flavor with size-bending lore
        tag_family_flavor = _get_echo_belly_tag_family_flavor(state.character)
        if tag_family_flavor and random.random() < 0.4:  # 40% chance
            ui.echo(f"[RADIO] {tag_family_flavor}\n")
        elif not tag_family_flavor:
            body_type_flavor = _get_echo_belly_body_type_flavor(state.character)
            if body_type_flavor and random.random() < 0.35:  # 35% chance
                ui.echo(f"[RADIO] {body_type_flavor}\n")
        
        # Occasionally reinforce Forest size-bending lore
        if random.random() < 0.2:  # 20% chance
            size_lore = random.choice([
                "[RADIO] The Forest stretches bellies to fit its stories. You fit perfectly, regardless of size.",
                "[RADIO] Size means nothing here. The Forest makes space where it needs to.",
            ])
            ui.echo(f"{size_lore}\n")
        
        ui.echo(
            "You give in to the warmth and safety. Time passes in a blur of gentle "
            "movement and steady breathing. When awareness returns, you find yourself "
            "back at the Glade, well-rested and safe.\n"
        )
        
        # Apply Glade rest recovery
        from .encounter_outcomes import OutcomeContext
        context = OutcomeContext(
            source_id=ECHO_ID,
            was_safe_shelter=True,
            metadata={"echo_belly": True, "vore": True},
        )
        resolve_encounter_outcome(
            state,
            EncounterOutcomeEnum.SHELTERED,
            context=context,
            ui=ui,
        )
        
        # Move to Glade
        state.active_zone = "glade"
        state.current_landmark = None
        
        exit_belly_state(state)
        return True
    
    # For predators: accept being carried
    creature_data = creatures.get(creature_id, {})
    is_friendly_belly = creature_data.get("is_friendly_belly", False)
    
    # Get tag-based belly flavor
    try:
        from .flavor_profiles import get_belly_flavor
        flavor_text = get_belly_flavor(state.character, "relax", is_predator=False)
    except Exception:
        flavor_text = None
    
    if is_friendly_belly:
        base_text = (
            f"You relax into the {creature_name}'s warmth. "
            "Time passes peacefully as you're carried through the forest. "
            "The creature seems to understand you mean no harm, and the journey is gentle.\n"
        )
        if flavor_text:
            ui.echo(base_text.rstrip() + f" {flavor_text}\n")
        else:
            ui.echo(base_text)
    else:
        base_text = (
            f"You stop fighting and let the {creature_name} carry you. "
            "Time blurs as you're moved through the forest. "
            "When awareness returns, you find yourself somewhere else.\n"
        )
        if flavor_text:
            ui.echo(base_text.rstrip() + f" {flavor_text}\n")
        else:
            ui.echo(base_text)
    
    # Transport to nearby landmark
    _release_at_nearby_location(state, creature_id, ui, transported=True)
    
    # Minor stamina recovery for friendly bellies
    if is_friendly_belly:
        stamina_max = state.character.get_stat(
            "stamina_max",
            timed_modifiers=state.timed_modifiers,
            current_day=state.day,
        )
        stamina_recovery = max(1.0, stamina_max * 0.1)  # 10% of max stamina
        state.stamina = min(stamina_max, state.stamina + stamina_recovery)
        ui.echo("The warm rest has restored some of your energy.\n")
    
    exit_belly_state(state)
    return True


def _handle_call(
    state: GameState,
    creature_id: str,
    mode: str,
    creature_name: str,
    ui: UI,
) -> bool:
    """Handle call action in belly (HT radio contact with Echo)."""
    # Check if player has HT radio
    if "ht_radio" not in state.inventory:
        ui.echo("You don't have a radio to call with.\n")
        return False
    
    if mode == "echo":
        # Echo mode: flavor only
        base_text = (
            "[RADIO] A warm, contented pulse. Echo's voice is already with you— "
            "you're inside her, after all. The radio thrums with gentle reassurance.\n"
        )
        # Optional race-aware flavor
        race_flavor = _get_echo_belly_race_flavor(state.character.race_id)
        if race_flavor and random.random() < 0.3:  # 30% chance to show race flavor
            ui.echo(f"[RADIO] {race_flavor}\n")
        
        # Add optional tag family or body type flavor
        tag_family_flavor = _get_echo_belly_tag_family_flavor(state.character)
        if tag_family_flavor and random.random() < 0.3:  # 30% chance
            ui.echo(f"[RADIO] {tag_family_flavor}\n")
        elif not tag_family_flavor:
            body_type_flavor = _get_echo_belly_body_type_flavor(state.character)
            if body_type_flavor and random.random() < 0.25:  # 25% chance
                ui.echo(f"[RADIO] {body_type_flavor}\n")
        
        ui.echo(base_text)
        return False
    
    # Predator mode: contact Echo for reassurance
    ui.echo(
        "[RADIO] You fumble for your radio and manage to key it. "
        "Static, then a familiar voice—Echo.\n\n"
        "[ECHO] I can sense you're being carried deeper. Stay calm. "
        "You're safe for now. I'll find you when you're released.\n\n"
        "The radio cuts out, but the reassurance helps. You feel a small boost "
        "to your morale and energy.\n"
    )
    
    # Small stamina/morale bump
    stamina_max = state.character.get_stat(
        "stamina_max",
        timed_modifiers=state.timed_modifiers,
        current_day=state.day,
    )
    stamina_bump = max(0.5, stamina_max * 0.05)  # 5% of max stamina
    state.stamina = min(stamina_max, state.stamina + stamina_bump)
    
    return False


def _release_at_nearby_location(
    state: GameState,
    creature_id: str,
    ui: UI,
    transported: bool,
) -> None:
    """
    Release player at a nearby location.
    
    Args:
        state: Current game state
        creature_id: ID of the creature
        ui: UI interface
        transported: If True, use TRANSPORTED outcome; if False, use SHELTERED
    """
    belly = state.belly_state
    depth_before = belly.get("depth_before", 0)
    landmark_before = belly.get("landmark_before")
    zone_before = state.active_zone
    
    # Determine release location (same depth band, nearby landmark if available)
    # For now, keep same zone and depth, but clear landmark
    state.current_landmark = None
    
    # Use appropriate outcome
    from .encounter_outcomes import OutcomeContext
    
    context = OutcomeContext(
        source_id=creature_id,
        was_safe_shelter=not transported,
        metadata={"vore": True, "predator_id": creature_id},
    )
    
    if transported:
        resolve_encounter_outcome(
            state,
            EncounterOutcomeEnum.TRANSPORTED,
            context=context,
            ui=ui,
        )
    else:
        resolve_encounter_outcome(
            state,
            EncounterOutcomeEnum.SHELTERED,
            context=context,
            ui=ui,
        )


def resolve_belly_on_load(state: GameState, ui: Optional[UI] = None) -> None:
    """
    Resolve belly state on game load (Phase 1: safe resolution).
    
    If the player loads a save while in belly state, resolve it to a safe
    "spit-out" at a nearby landmark instead of resuming the loop.
    
    Args:
        state: Current game state
        ui: Optional UI interface
    """
    if not is_belly_active(state):
        return
    
    belly = state.belly_state
    creature_id = belly.get("creature_id", "unknown")
    mode = belly.get("mode", "predator")
    
    if ui:
        if mode == "echo":
            ui.echo(
                "\n[On load: Resolving belly state] "
                "You find yourself back at the Glade, having been released by Echo.\n"
            )
            state.active_zone = "glade"
            state.current_landmark = None
        else:
            creature_name = creature_id.replace("_", " ").title()
            ui.echo(
                f"\n[On load: Resolving belly state] "
                f"You find yourself released by the {creature_name} at a nearby location.\n"
            )
            # Keep same zone but clear landmark
            state.current_landmark = None
    
    exit_belly_state(state)

