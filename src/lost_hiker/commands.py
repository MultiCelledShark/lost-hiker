"""Lightweight text command parsing for Lost Hiker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Command:
    """Represents a normalized player command."""

    verb: str
    args: Tuple[str, ...] = ()


class CommandParser:
    """Parse raw text into canonical verbs with positional arguments."""

    def __init__(self, aliases: Dict[str, str] | None = None) -> None:
        base_aliases: Dict[str, str] = {
            "look": "look",
            "examine": "look",
            "inspect": "look",
            "observe": "look",
            "move": "move",
            "go": "move",
            "continue": "move",
            "advance": "move",
            "press": "move",
            "walk": "move",
            "camp": "camp",
            "make camp": "camp",
            "return": "return",
            "back": "return",
            "leave": "leave",
            "exit": "leave",
            "step out": "leave",
            "step outside": "leave",
            "go outside": "leave",
            "ping": "ping",
            "radio": "ping",
            "brew": "brew",
            "status": "status",
            "notebook": "status",
            "journal": "status",
            "bag": "bag",
            "inventory": "bag",
            "pack": "bag",
            "help": "help",
            "examine bag": "bag",
            "open bag": "bag",
            "rest": "camp",
            "wait": "wait",
            "take": "take",
            "pick": "take",
            "grab": "take",
            "get": "take",
            "gather": "gather",
            "forage": "forage",
            "repair": "repair",
            "fix": "repair",
            "mend": "repair",
            "eat": "eat",
            "consume": "eat",
            "cook": "cook",
            "drink": "drink",
            "fill": "fill",
            "landmarks": "landmarks",
            "paths": "landmarks",
            "wayfind": "wayfind",
            "wayfind to": "wayfind",
            "check sky": "check sky",
            "sky": "check sky",
            "hug echo": "hug echo",
            "boop echo": "boop echo",
            "pet echo": "pet echo",
            "talk echo": "talk echo",
            "talk to echo": "talk echo",
            "speak to echo": "speak to echo",
            "rub": "rub",
            "request release": "request release",
            "runes": "runes",
            "inspect runes": "runes",
            "touch runes": "runes",
            "explore": "explore",
        }
        if aliases:
            base_aliases.update({key.lower(): value for key, value in aliases.items()})
        self._aliases = base_aliases

    def parse(self, raw: str) -> Command | None:
        """Convert user text into a `Command`, returning None for empty input."""
        normalized = (raw or "").strip().lower()
        if not normalized:
            return None
        tokens = normalized.split()
        first_two = " ".join(tokens[:2]) if len(tokens) >= 2 else ""
        if first_two and first_two in self._aliases:
            verb_key = first_two
            args = tuple(tokens[2:])
        else:
            verb_key = tokens[0]
            args = tuple(tokens[1:])
        verb = self._aliases.get(verb_key, verb_key)
        return Command(verb=verb, args=args)

    def known_verbs(self) -> Tuple[str, ...]:
        """Return canonical verbs the parser recognises."""
        canonical = {value for value in self._aliases.values()}
        return tuple(sorted(canonical))
