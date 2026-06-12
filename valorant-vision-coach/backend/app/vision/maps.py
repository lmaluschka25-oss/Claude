"""Map metadata: callouts, sites, and the rotation (adjacency) graph.

Maps are described by JSON files in ``data/maps``. Coordinates are normalized
to a ``[0, 1] x [0, 1]`` square so they are resolution-independent and can be
overlaid on any minimap image after a one-time calibration.

The adjacency graph powers rotation estimation: a Dijkstra walk bounded by
``movement_speed * elapsed_time`` yields the callouts an enemy could plausibly
have reached since they were last seen.
"""
from __future__ import annotations

import heapq
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import settings
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Callout:
    id: str
    name: str
    x: float
    y: float
    site: str | None = None


@dataclass
class GameMap:
    name: str
    display_name: str
    image: str | None
    sites: list[str]
    callouts: dict[str, Callout]
    # Adjacency list of callout id -> list of neighbour callout ids.
    adjacency: dict[str, list[str]] = field(default_factory=dict)

    # ---- Geometry helpers -------------------------------------------------
    @staticmethod
    def _dist(a: Callout, b: Callout) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    def nearest_callout(self, x: float, y: float) -> Callout | None:
        """Return the callout closest to a normalized point."""
        if not self.callouts:
            return None
        target = Callout("_q", "_q", x, y)
        return min(self.callouts.values(), key=lambda c: self._dist(c, target))

    def neighbors(self, callout_id: str) -> list[str]:
        return self.adjacency.get(callout_id, [])

    def site_centroid(self, site: str) -> tuple[float, float] | None:
        members = [c for c in self.callouts.values() if c.site == site]
        if not members:
            return None
        return (
            sum(c.x for c in members) / len(members),
            sum(c.y for c in members) / len(members),
        )

    def reachable(self, origin_id: str, max_distance: float) -> dict[str, float]:
        """Dijkstra from ``origin_id`` over the adjacency graph.

        Returns a mapping of callout id -> graph distance, including only nodes
        within ``max_distance`` (normalized units). Edge weights are Euclidean
        distances between connected callouts, approximating walkable paths.
        """
        if origin_id not in self.callouts:
            return {}
        dist: dict[str, float] = {origin_id: 0.0}
        heap: list[tuple[float, str]] = [(0.0, origin_id)]
        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, math.inf):
                continue
            if d > max_distance:
                continue
            for neighbour in self.neighbors(node):
                if neighbour not in self.callouts:
                    continue
                w = self._dist(self.callouts[node], self.callouts[neighbour])
                nd = d + w
                if nd <= max_distance and nd < dist.get(neighbour, math.inf):
                    dist[neighbour] = nd
                    heapq.heappush(heap, (nd, neighbour))
        return dist


def _maps_dir() -> Path:
    return settings.maps_dir


@lru_cache
def list_maps() -> list[str]:
    directory = _maps_dir()
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


@lru_cache
def load_map(name: str) -> GameMap | None:
    """Load and cache a map by its file stem (e.g. ``"ascent"``)."""
    if not name:
        return None
    path = _maps_dir() / f"{name.lower()}.json"
    if not path.exists():
        logger.warning("Map metadata not found: %s", path)
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    callouts = {
        c["id"]: Callout(
            id=c["id"],
            name=c["name"],
            x=float(c["x"]),
            y=float(c["y"]),
            site=c.get("site"),
        )
        for c in raw.get("callouts", [])
    }
    adjacency: dict[str, list[str]] = {cid: [] for cid in callouts}
    for a, b in raw.get("edges", []):
        if a in adjacency and b in callouts:
            adjacency[a].append(b)
        if b in adjacency and a in callouts:
            adjacency[b].append(a)
    return GameMap(
        name=raw["name"],
        display_name=raw.get("display_name", raw["name"].title()),
        image=raw.get("image"),
        sites=raw.get("sites", []),
        callouts=callouts,
        adjacency=adjacency,
    )
