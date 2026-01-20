"""
Lightweight text command parsing for Lost Hiker.

This module converts player text input into normalized commands that the
game engine can process. It handles aliases (synonyms) and extracts arguments.

## Key Concepts:
- Command: Normalized verb + arguments (e.g., "look" with args ["bag"])
- Aliases: Multiple text inputs mapped to same verb ("examine" → "look")
- Parser: Converts raw player text to Command objects

## For Content Editors:
To add new commands:
1. Add verb and aliases to CommandParser.__init__
2. Handle the verb in Engine (see engine.py)
3. Document in help text
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Command:
    """
    Normalized player command with verb and arguments.
    
    Player input is parsed into a canonical verb (action) and optional
    arguments. This allows multiple phrasings to map to the same action.
    
    ## Examples:
    - "look" → Command(verb="look", args=())
    - "examine bag" → Command(verb="look", args=("bag",))
    - "go north" → Command(verb="move", args=("north",))
    
    Attributes:
        verb: Canonical action verb (e.g., "look", "move", "camp")
        args: Additional arguments (direction, item name, etc.)
    """

    verb: str  # Canonical action name
    args: Tuple[str, ...] = ()  # Additional arguments from player input


class CommandParser:
    """
    Parse player text input into normalized commands.
    
    Converts free-form text into structured Command objects by:
    1. Lowercasing and tokenizing input
    2. Matching against alias dictionary
    3. Extracting verb and arguments
    
    ## Alias System:
    Multiple phrasings map to canonical verbs:
    - "examine", "inspect", "look" → "look"
    - "go", "move", "continue" → "move"
    - "inventory", "bag", "pack" → "bag"
    
    ## Multi-word Commands:
    Some commands are two words ("make camp", "hug echo").
    Parser checks for two-word matches before single-word matches.
    
    ## For Developers:
    To add a new command:
    1. Add aliases in __init__ (map variations to canonical verb)
    2. Implement handler in Engine._handle_command()
    3. Add to help text
    """

    def __init__(self, aliases: Dict[str, str] | None = None) -> None:
        """
        Initialize parser with command aliases.
        
        Args:
            aliases: Optional additional aliases to merge with base set
        """
        # Base command aliases (maps player input → canonical verb)
        # Format: "player_input": "canonical_verb"
        base_aliases: Dict[str, str] = {
            # Examination commands
            "look": "look",
            "examine": "look",
            "inspect": "look",
            "observe": "look",
            
            # Movement commands
            "move": "move",
            "go": "move",
            "continue": "move",
            "advance": "move",
            "press": "move",
            "walk": "move",
            
            # Rest/camp commands
            "camp": "camp",
            "make camp": "camp",
            "rest": "camp",
            
            # Navigation commands
            "return": "return",  # Return to Glade
            "back": "return",
            "leave": "leave",  # Leave current location
            "exit": "leave",
            "step out": "leave",
            "step outside": "leave",
            "go outside": "leave",
            
            # Communication commands
            "ping": "ping",  # Radio ping
            "radio": "ping",
            
            # Crafting commands
            "brew": "brew",  # Brew teas at camp
            
            # UI/info commands
            "status": "status",  # View character status
            "notebook": "status",
            "journal": "status",
            "bag": "bag",  # View inventory
            "inventory": "bag",
            "pack": "bag",
            "examine bag": "bag",
            "open bag": "bag",
            "help": "help",  # Show help
            
            # Time commands
            "wait": "wait",  # Pass time
            
            # Interaction commands
            "take": "take",  # Take item
            "pick": "take",
            "grab": "take",
            "get": "take",
            "gather": "gather",  # Gather resources
            "forage": "forage",  # Forage for food
            
            # Runestone commands
            "repair": "repair",  # Repair runestones
            "fix": "repair",
            "mend": "repair",
            "runes": "runes",  # Examine runes
            "inspect runes": "runes",
            "touch runes": "runes",
            
            # Survival commands
            "eat": "eat",  # Eat food
            "consume": "eat",
            "cook": "cook",  # Cook meals
            "drink": "drink",  # Drink water
            "fill": "fill",  # Fill water bottle
            
            # Navigation/wayfinding
            "landmarks": "landmarks",  # View discovered landmarks
            "paths": "landmarks",
            "wayfind": "wayfind",  # Wayfinding tea teleport
            "wayfind to": "wayfind",
            
            # Environmental commands
            "check sky": "check sky",  # Check time of day
            "sky": "check sky",
            "explore": "explore",  # Forest exploration
            
            # Echo interaction commands
            "hug echo": "hug echo",
            "boop echo": "boop echo",
            "pet echo": "pet echo",
            "talk echo": "talk echo",
            "talk to echo": "talk echo",
            "speak to echo": "speak to echo",
            
            # Belly interaction commands (if vore enabled)
            "rub": "rub",  # Rub stomach walls
            "request release": "request release",  # Ask to be let out
        }
        
        # Merge with any custom aliases
        if aliases:
            base_aliases.update({key.lower(): value for key, value in aliases.items()})
        
        self._aliases = base_aliases

    def parse(self, raw: str) -> Command | None:
        """
        Convert player text into a Command object.
        
        Handles multi-word commands (checks two-word matches first, then
        single-word matches). Extracts arguments from remaining tokens.
        
        Args:
            raw: Raw player input text
            
        Returns:
            Command object with verb and args, or None if input is empty
            
        ## Examples:
        - "look" → Command(verb="look", args=())
        - "examine bag" → Command(verb="look", args=("bag",))
        - "hug echo" → Command(verb="hug echo", args=())
        - "wayfind to glade" → Command(verb="wayfind", args=("to", "glade"))
        """
        # Normalize input (lowercase, trim whitespace)
        normalized = (raw or "").strip().lower()
        if not normalized:
            return None
        
        # Split into tokens
        tokens = normalized.split()
        
        # Check for two-word command match first
        first_two = " ".join(tokens[:2]) if len(tokens) >= 2 else ""
        if first_two and first_two in self._aliases:
            verb_key = first_two
            args = tuple(tokens[2:])  # Remaining tokens are arguments
        else:
            # Fall back to single-word command
            verb_key = tokens[0]
            args = tuple(tokens[1:])  # Remaining tokens are arguments
        
        # Look up canonical verb (or use raw verb if no alias found)
        verb = self._aliases.get(verb_key, verb_key)
        
        return Command(verb=verb, args=args)

    def known_verbs(self) -> Tuple[str, ...]:
        """
        Get list of canonical verbs recognized by this parser.
        
        Useful for generating help text or validating commands.
        
        Returns:
            Sorted tuple of canonical verb names
        """
        # Extract unique canonical verbs (alias values, not keys)
        canonical = {value for value in self._aliases.values()}
        return tuple(sorted(canonical))
