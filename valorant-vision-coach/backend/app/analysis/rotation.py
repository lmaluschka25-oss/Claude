"""Rotation estimation.

Given where an enemy was last seen and how long ago, estimate where they could
plausibly be now. The model is intentionally simple and transparent:

1. Bound reachable distance by ``movement_speed * elapsed_time``.
2. Walk the map's callout graph (Dijkstra) to find reachable callouts.
3. Score each candidate by three interpretable factors — how consistent the
   distance is with full-speed travel, how well it aligns with the enemy's last
   observed heading, and whether it leads onto a bomb site.

Nothing here peeks at hidden state; it is the same dead-reckoning a human coach
does from the same footage.
"""
from __future__ import annotations

import math

from ..config import Settings
from ..schemas import EnemyRotation, RotationCandidate
from ..vision.maps import GameMap
from .tracks import EnemyTrack

MAX_CANDIDATES = 5


def estimate_rotations(
    tracks: list[EnemyTrack],
    game_map: GameMap | None,
    at_seconds: float,
    settings: Settings,
) -> list[EnemyRotation]:
    if game_map is None or not game_map.callouts:
        return []

    speed = max(settings.movement_speed_norm, 1e-4)
    results: list[EnemyRotation] = []

    for track in tracks:
        origin = game_map.nearest_callout(track.last.x, track.last.y)
        if origin is None:
            continue
        elapsed = track.age(at_seconds)
        reach = speed * elapsed

        reachable = {
            cid: d
            for cid, d in game_map.reachable(origin.id, max(reach, 1e-6)).items()
            if cid != origin.id
        }
        if not reachable:
            # Too soon to have moved meaningfully: offer immediate neighbours as
            # the first places they could rotate toward.
            for nid in game_map.neighbors(origin.id):
                node = game_map.callouts.get(nid)
                if node is None:
                    continue
                reachable[nid] = math.hypot(node.x - origin.x, node.y - origin.y)
            reach = max(reach, max(reachable.values(), default=1e-6))

        heading = track.heading
        sigma = max(0.5 * reach, 1e-3)
        scored: list[tuple[float, RotationCandidate]] = []

        for cid, dist in reachable.items():
            node = game_map.callouts[cid]
            # Consistency with full-speed travel (frontier preference).
            w_progress = math.exp(-((reach - dist) ** 2) / (2 * sigma * sigma))
            # Heading alignment.
            w_head = 1.0
            if heading is not None:
                vx, vy = node.x - origin.x, node.y - origin.y
                vnorm = math.hypot(vx, vy)
                if vnorm > 1e-4:
                    cos = (heading[0] * vx + heading[1] * vy) / vnorm
                    w_head = 0.4 + 0.6 * (cos * 0.5 + 0.5)
            # Objective pull.
            leads_to_site = node.site if node.site in game_map.sites else None
            w_site = 1.3 if leads_to_site else 1.0

            score = w_progress * w_head * w_site
            scored.append(
                (
                    score,
                    RotationCandidate(
                        from_callout=origin.name,
                        to_callout=node.name,
                        to_x=node.x,
                        to_y=node.y,
                        distance_norm=round(dist, 4),
                        eta_seconds=round(dist / speed, 2),
                        likelihood=0.0,  # filled after normalization
                        leads_to_site=leads_to_site,
                    ),
                )
            )

        if not scored:
            continue
        # Rank by raw score, keep the strongest few, then normalize *those* into
        # a distribution so the displayed candidates sum to 1.
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:MAX_CANDIDATES]
        top_total = sum(s for s, _ in top) or 1.0
        candidates = []
        for s, cand in top:
            cand.likelihood = round(s / top_total, 4)
            candidates.append(cand)

        results.append(
            EnemyRotation(
                agent_name=track.agent_name,
                origin_callout=origin.name,
                age_seconds=round(elapsed, 2),
                candidates=candidates,
            )
        )

    return results
