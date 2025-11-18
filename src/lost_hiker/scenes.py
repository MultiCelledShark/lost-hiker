"""Scene descriptions and examinables for Lost Hiker."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True)
class Examinable:
    """Inspectable object within a scene."""

    name: str
    aliases: Tuple[str, ...]
    descriptions: Tuple[str, ...]

    def describe(self) -> str:
        return random.choice(self.descriptions)


@dataclass(frozen=True)
class Scene:
    """Scene-level descriptive data."""

    look_default: Tuple[str, ...]
    look_by_depth: Mapping[str, Tuple[str, ...]]
    examinables: Mapping[str, Examinable]
    alias_map: Mapping[str, str]

    def describe(self, *, depth_band: str) -> Optional[str]:
        variants = self.look_by_depth.get(depth_band)
        if variants:
            return random.choice(variants)
        if self.look_default:
            return random.choice(self.look_default)
        return None

    def examine(self, alias: str) -> Optional[str]:
        key = self.alias_map.get(alias)
        if not key:
            return None
        examinable = self.examinables.get(key)
        if not examinable:
            return None
        return examinable.describe()

    def highlight_terms(self) -> Tuple[str, ...]:
        names = {examinable.name for examinable in self.examinables.values()}
        return tuple(sorted(names))


@dataclass
class SceneCatalog:
    """Lookup catalog for scenes keyed by zone."""

    scenes: Mapping[str, Scene]

    def describe(self, zone_id: str, *, depth_band: str) -> Optional[str]:
        scene = self.scenes.get(zone_id)
        if not scene:
            return None
        return scene.describe(depth_band=depth_band)

    def examine(self, zone_id: str, alias: str) -> Optional[str]:
        scene = self.scenes.get(zone_id)
        if not scene:
            return None
        return scene.examine(alias)

    def highlight_terms(self, zone_id: str) -> Tuple[str, ...]:
        scene = self.scenes.get(zone_id)
        if not scene:
            return ()
        return scene.highlight_terms()


def load_scene_catalog(data_dir: Path) -> SceneCatalog:
    """Load scene data from JSON."""
    path = data_dir / "scenes.json"
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    scenes: Dict[str, Scene] = {}
    for zone_id, payload in raw.items():
        look_payload = payload.get("look", {})
        look_default = tuple(look_payload.get("default", []))
        look_by_depth = {
            band: tuple(descriptions)
            for band, descriptions in look_payload.get("by_depth", {}).items()
        }

        examinables_payload = payload.get("examinables", {})
        examinables: Dict[str, Examinable] = {}
        alias_map: Dict[str, str] = {}
        for key, definition in examinables_payload.items():
            name = definition.get("name", key).lower()
            aliases: Iterable[str] = definition.get("aliases", [])
            descriptions = tuple(definition.get("descriptions", []))
            examinable = Examinable(
                name=name,
                aliases=tuple(alias.lower() for alias in aliases),
                descriptions=descriptions or (f"You study the {name}.",),
            )
            examinables[key] = examinable
            for alias in examinable.aliases:
                alias_map[alias] = key
            alias_map[name] = key

        scenes[zone_id] = Scene(
            look_default=look_default,
            look_by_depth=look_by_depth,
            examinables=examinables,
            alias_map=alias_map,
        )

    return SceneCatalog(scenes=scenes)
