"""Enemy site-tendency aggregation (post-match scouting report).

Across the rounds of an analyzed match, summarize *where the enemy tended to
go* — the share of rounds each site was committed to, and each agent's site
preference. This is study/preparation material derived purely from observed
sightings; it is not a live overlay and reveals nothing about current positions.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from ..models import Team
from ..schemas import (
    AgentSitePreference,
    AgentSiteShare,
    SiteFrequency,
    TendencyReport,
)
from ..vision.maps import GameMap
from .tracks import DetectionLike


def _assign_site(game_map: GameMap, x: float, y: float) -> str | None:
    """Assign a point to the nearest site by centroid distance."""
    best: str | None = None
    best_dist = math.inf
    for site in game_map.sites:
        centroid = game_map.site_centroid(site)
        if centroid is None:
            continue
        d = math.hypot(x - centroid[0], y - centroid[1])
        if d < best_dist:
            best_dist = d
            best = site
    return best


def build_tendencies(
    detections: list[DetectionLike],
    match_id: int,
    map_name: str | None,
    game_map: GameMap | None,
) -> TendencyReport:
    empty = TendencyReport(
        match_id=match_id,
        map_name=map_name,
        rounds_analyzed=0,
        site_frequency=[],
        agent_site_preference=[],
    )
    if game_map is None or not game_map.sites:
        return empty

    # Group located enemy sightings by round.
    by_round: dict[object, list[DetectionLike]] = defaultdict(list)
    for d in detections:
        if d.team != Team.ENEMY or d.map_x is None or d.map_y is None:
            continue
        by_round[getattr(d, "round_id", None)].append(d)

    round_dominant: list[str] = []
    agent_round_site: dict[str, list[str]] = defaultdict(list)

    for dets in by_round.values():
        site_counts: Counter[str] = Counter()
        agent_counts: dict[str, Counter[str]] = defaultdict(Counter)
        for d in dets:
            site = _assign_site(game_map, d.map_x, d.map_y)
            if site is None:
                continue
            site_counts[site] += 1
            agent_counts[d.agent_name or "Unknown"][site] += 1
        if not site_counts:
            continue
        round_dominant.append(site_counts.most_common(1)[0][0])
        for agent, counts in agent_counts.items():
            agent_round_site[agent].append(counts.most_common(1)[0][0])

    rounds_analyzed = len(round_dominant)
    if rounds_analyzed == 0:
        return empty

    freq = Counter(round_dominant)
    site_frequency = [
        SiteFrequency(
            site=site,
            rounds=freq.get(site, 0),
            share=round(freq.get(site, 0) / rounds_analyzed, 3),
        )
        for site in game_map.sites
    ]
    site_frequency.sort(key=lambda s: s.share, reverse=True)

    agent_pref: list[AgentSitePreference] = []
    for agent, sites in agent_round_site.items():
        n = len(sites)
        counts = Counter(sites)
        shares = [
            AgentSiteShare(site=site, share=round(counts[site] / n, 3))
            for site in game_map.sites
            if counts.get(site, 0) > 0
        ]
        shares.sort(key=lambda s: s.share, reverse=True)
        agent_pref.append(
            AgentSitePreference(
                agent_name=None if agent == "Unknown" else agent,
                rounds_seen=n,
                sites=shares,
            )
        )
    agent_pref.sort(key=lambda a: a.rounds_seen, reverse=True)

    return TendencyReport(
        match_id=match_id,
        map_name=map_name,
        rounds_analyzed=rounds_analyzed,
        site_frequency=site_frequency,
        agent_site_preference=agent_pref,
    )
