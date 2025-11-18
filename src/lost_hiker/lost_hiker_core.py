# Lost Hiker — Core Runtime (`lost_hiker_core.py`)
# Architecture, data loading, scene orchestration, and save/load.
# Game content is in /data as JSON defined in lost_hiker_design.md.

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Callable, Optional, Tuple


# ---------- Data Repository ----------
class DataRepo:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.cache: Dict[str, Dict[str, Any]] = {}

    def load(self, name: str) -> Dict[str, Any]:
        if name in self.cache:
            return self.cache[name]
        path = os.path.join(self.data_dir, f"{name}.json")
        with open(path, "r", encoding="utf-8") as f:
            self.cache[name] = json.load(f)
        return self.cache[name]

    # Convenience getters
    def beasts(self) -> Dict[str, Any]:
        return self.load("beasts")["beasts"]

    def scenes(self) -> Dict[str, Any]:
        return self.load("scenes")

    def items(self) -> Dict[str, Any]:
        return self.load("items")["items"]

    def runes(self) -> Dict[str, Any]:
        return self.load("runes")["runes"]

    def settings(self) -> Dict[str, Any]:
        return self.load("settings")


# ---------- Display Abstraction ----------
class Display:
    def write(self, text: str) -> None:
        raise NotImplementedError

    def read(self, prompt: str = "> ") -> str:
        raise NotImplementedError


class StdIODisplay(Display):
    def write(self, text: str) -> None:
        print(text, end="" if text.endswith("\n") else "\n")

    def read(self, prompt: str = "> ") -> str:
        return input(prompt)


# ---------- Game State ----------
@dataclass
class GameState:
    day: int = 1
    season_day: int = 0
    season: str = "spring"
    slots_left: int = 4
    exhaustion: float = 0.0
    meals: int = 15
    exploration_loops: int = 0
    location: str = "charred_tree"
    vore_enabled: bool = False
    player_pred: bool = False
    phone_battery: int = 10
    ht_battery: int = 10
    pack_days: int = 0
    recall_timer: int = 0
    runes: List[str] = field(default_factory=list)
    channels: List[str] = field(default_factory=list)
    rapport: Dict[str, int] = field(default_factory=dict)
    inventory: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "backpack": [],
            "self": ["belt knife", "phone", "ht_radio"],
        }
    )

    def next_season_name(self, seasons: List[str]) -> str:
        i = seasons.index(self.season)
        return seasons[(i + 1) % len(seasons)]


# ---------- Save/Load ----------
class SaveSystem:
    def __init__(self, path: str = "savegame.json"):
        self.path = path

    def save(self, state: GameState) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)

    def load(self) -> Optional[GameState]:
        if not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GameState(**data)


# ---------- Parser ----------
class Parser:
    def parse(self, raw: str) -> Tuple[str, List[str]]:
        raw = (raw or "").strip().lower()
        if not raw:
            return ("", [])
        parts = raw.split()
        cmd, args = parts[0], parts[1:]
        return (cmd, args)


# ---------- Scene System ----------
class SceneManager:
    def __init__(self, repo: DataRepo, disp: Display, state: GameState):
        self.repo, self.disp, self.state = repo, disp, state
        self.handlers: Dict[str, Callable[[str, List[str]], None]] = {
            "charred_tree": self.scene_charred_tree,
            "glade": self.scene_glade,
            "forest": self.scene_forest,
            "plains": self.scene_plains,
        }
        self.parser = Parser()

    # Main loop
    def run(self) -> None:
        self.disp.write("Welcome to Lost Hiker Beta. Type 'start' to begin.\n")
        while True:
            cmd, args = self.parser.parse(self.disp.read("> "))
            if cmd in ("quit", "exit"):
                break
            if cmd == "save":
                SaveSystem().save(self.state)
                self.disp.write("Saved.\n")
                continue
            if cmd == "load":
                loaded = SaveSystem().load()
                if loaded:
                    self.state = loaded
                    self.disp.write("Loaded.\n")
                else:
                    self.disp.write("No save found.\n")
                continue
            if cmd == "start":
                self.state.location = "charred_tree"
                self.handlers[self.state.location](cmd, args)
                continue
            # route to current scene
            self.handlers.get(self.state.location, self.unknown_scene)(cmd, args)

    def unknown_scene(self, cmd: str, args: List[str]) -> None:
        self.disp.write(f"(Unknown scene: {self.state.location})\n")

    # ----- Scenes -----
    def scene_charred_tree(self, cmd: str, args: List[str]) -> None:
        self.disp.write("You're in a charred black hollow. Unburned backpack nearby.\n")
        self.disp.write("Examinables: walls, backpack, knife, runes.\n")
        while self.state.location == "charred_tree":
            cmd, args = self.parser.parse(self.disp.read("> "))
            if cmd == "examine" and args:
                what = " ".join(args)
                if what == "backpack":
                    for item in [
                        "tent",
                        "blanket",
                        "pad",
                        "pillow",
                        "trowel",
                        "clothes",
                        "food bars x10",
                        "first aid kit",
                        "fire starter",
                        "bottle",
                        "tea",
                        "soap",
                        "towel",
                    ]:
                        self.state.inventory["backpack"].append(item)
                    self.disp.write("Backpack loaded: camp supplies, food, etc.\n")
                elif what == "knife":
                    if "belt knife" not in self.state.inventory["self"]:
                        self.state.inventory["self"].append("belt knife")
                    self.disp.write("Knife secured.\n")
                else:
                    self.disp.write("Ancient carvings catch the light.\n")
            elif cmd in ("leave", "exit", "go"):
                self.state.location = "glade"
            elif cmd == "help":
                self.disp.write("Try: examine backpack | examine knife | leave\n")
            else:
                self.disp.write("Thirst presses. Perhaps leave?\n")
        # fallthrough
        self.handlers["glade"](cmd, args)

    def scene_glade(self, cmd: str, args: List[str]) -> None:
        desc = {
            "winter": "Bare trees, snow on ground, frozen stream silent.",
            "spring": "Flowering trees; stream audibly south.",
            "summer": "Lush green; warm air; murmuring water.",
            "fall": "Gold grasses; quiet stream until forest entry.",
        }
        self.disp.write(
            f"Glade: {desc.get(self.state.season, 'Green hush')}. Paths: north(plains), south(forest), west(mountain), east(lake).\n"
        )
        while self.state.location == "glade":
            cmd, args = self.parser.parse(self.disp.read("> "))
            if cmd == "explore" and args:
                where = args[0]
                if where == "forest":
                    self.state.location = "forest"
                elif where == "plains":
                    self.state.location = "plains"
                else:
                    self.disp.write("That path is currently blocked.\n")
                    continue
                break
            elif cmd == "charge_solar":
                if self.state.season in ("spring", "summer"):
                    gain = (
                        random.randint(1, 3)
                        if self.state.season == "spring"
                        else random.randint(2, 5)
                    )
                    self.state.phone_battery = min(10, self.state.phone_battery + gain)
                    self.state.ht_battery = min(10, self.state.ht_battery + gain)
                    self.state.slots_left -= 1
                    self.disp.write(
                        f"Solar charged. Phone {self.state.phone_battery}/10, HT {self.state.ht_battery}/10\n"
                    )
                else:
                    self.disp.write("Clouds smother the sun. No charge.\n")
            elif cmd == "help":
                self.disp.write(
                    "explore forest | explore plains | charge_solar | save | load | quit\n"
                )
            else:
                self.disp.write("The wind tugs at your sleeve.\n")
        # fallthrough to next scene
        self.handlers[self.state.location](cmd, args)

    def scene_forest(self, cmd: str, args: List[str]) -> None:
        data = self.repo.scenes()
        entries = data["scenes"]["forest"]["entries"]
        forage_rate = data["scenes"]["forest"]["forage_rate"]
        self.disp.write("Forest air cools the mind.\n")
        # One-step demo; expand to loops
        entry = random.choice(entries)
        self.disp.write(f"Scene: {entry}\n")
        if random.random() < forage_rate:
            herb = data["entries"][entry].get("herb")
            if herb:
                self.state.inventory["backpack"].append(herb)
                self.disp.write(f"Foraged {herb}.\n")
        self._encounter("forest")
        self.state.location = "glade"
        self.handlers["glade"](cmd, args)

    def scene_plains(self, cmd: str, args: List[str]) -> None:
        data = self.repo.scenes()
        entries = data["scenes"]["plains"]["entries"]
        self.disp.write("Heat shimmers off the flats.\n")
        entry = random.choice(entries)
        self.disp.write(f"Scene: {entry}\n")
        self._encounter("plains")
        self.state.location = "glade"
        self.handlers["glade"](cmd, args)

    # ----- Encounters -----
    def _encounter(self, biome: str) -> None:
        beasts = {
            k: v for k, v in self.repo.beasts().items() if v.get("biome") == biome
        }
        if not beasts:
            return
        choices, weights = zip(
            *[
                (k, max(0.001, v.get("encounter_weight", 1.0)))
                for k, v in beasts.items()
            ]
        )
        breed = random.choices(choices, weights=weights, k=1)[0]
        self.disp.write(f"Encounter: {breed}\n")
        # Stub: either try to tame or lose pack
        b = beasts[breed]
        if self.state.vore_enabled and b.get("vore_roles", {}).get("pred"):
            self.disp.write("A shadow looms—high-stakes choice (stub).\n")
        else:
            if random.random() < b.get("pack_hold", 0.0):
                self.disp.write(f"{breed} snatches your pack! (stub recovery)\n")


# ---------- Entry Point ----------
if __name__ == "__main__":
    repo = DataRepo(os.environ.get("LOST_HIKER_DATA", "data"))
    disp = StdIODisplay()
    state = SaveSystem().load() or GameState()
    SceneManager(repo, disp, state).run()
