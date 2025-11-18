"""NPC definitions and management for Lost Hiker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class NPC:
    """Data structure for an NPC."""

    npc_id: str
    name: str
    description: str
    landmark_ids: tuple[str, ...]
    tags: tuple[str, ...]

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "NPC":
        """Create an NPC from JSON data."""
        landmark_ids = data.get("landmark_ids", [])
        if isinstance(landmark_ids, list):
            landmark_ids = tuple(str(lm) for lm in landmark_ids)
        else:
            landmark_ids = ()
        tags = data.get("tags", [])
        if isinstance(tags, list):
            tags = tuple(str(t) for t in tags)
        else:
            tags = ()
        return cls(
            npc_id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            landmark_ids=landmark_ids,
            tags=tags,
        )


class NPCCatalog:
    """Catalog of all NPCs."""

    def __init__(self, npcs: List[NPC]):
        self.npcs = npcs
        self._by_id: Dict[str, NPC] = {npc.npc_id: npc for npc in npcs}
        self._by_landmark: Dict[str, List[NPC]] = {}
        for npc in npcs:
            for landmark_id in npc.landmark_ids:
                if landmark_id not in self._by_landmark:
                    self._by_landmark[landmark_id] = []
                self._by_landmark[landmark_id].append(npc)

    def get(self, npc_id: str) -> Optional[NPC]:
        """Get an NPC by ID."""
        return self._by_id.get(npc_id)

    def get_npcs_at_landmark(self, landmark_id: str) -> List[NPC]:
        """Get all NPCs present at a landmark."""
        return self._by_landmark.get(landmark_id, [])


def load_npc_catalog(data_dir: Path, filename: str = "npcs_forest.json") -> NPCCatalog:
    """Load NPCs from a JSON file."""
    path = data_dir / filename
    if not path.exists():
        return NPCCatalog([])
    
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    
    npcs = [
        NPC.from_dict(entry)
        for entry in raw.get("npcs", [])
    ]
    
    return NPCCatalog(npcs)

