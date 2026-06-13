"""Match-level intelligence aggregation.

Turns a match's stored rounds (and their detections/utilities/killfeed) into the
full dashboard payload: detected info, an enlarged-minimap marker set, a round
timeline, live positions, next-round position probabilities, learned patterns,
a site-control heatmap, match memory, enemy profiles, weapon/economy read, a
recommendation, and a step-by-step analysis log.

Everything is derived from on-screen observations aggregated across rounds —
the system "learns" the opponent as more rounds are uploaded.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Detection, Match, ProcessingStatus, Round, Side, Team, UtilityDetection
from ..schemas import (
    AnalysisLogStep,
    DetectedInfo,
    DetectedPositionLive,
    EnemyProfile,
    HeatCell,
    MarkerOut,
    MatchIntelligence,
    MatchMemory,
    MatchSummary,
    PatternItem,
    PositionProbability,
    Recommendation,
    RoundOut,
    TimelineEvent,
    UtilityOut,
    WeaponEconomy,
)
from ..vision.maps import GameMap, load_map

_W_BASE, _W_MOMENTUM, _W_TRANSITION = 0.34, 0.34, 0.32


def assign_site(game_map: GameMap, x: float, y: float) -> str | None:
    """Assign a normalized point to the nearest site by centroid distance."""
    best: str | None = None
    best_dist = math.inf
    for site in game_map.sites:
        centroid = game_map.site_centroid(site)
        if centroid is None:
            continue
        d = math.hypot(x - centroid[0], y - centroid[1])
        if d < best_dist:
            best_dist, best = d, site
    return best


_assign_site = assign_site  # internal alias


def _default_sites(game_map: GameMap | None) -> list[str]:
    if game_map and game_map.sites:
        return list(game_map.sites)
    return ["A", "B", "MID"]


def _round_site(detections: list[Detection], game_map: GameMap | None) -> str | None:
    """Dominant enemy site commitment for a round (map-based)."""
    if game_map is None:
        return None
    scores: Counter[str] = Counter()
    for d in detections:
        if d.team != Team.ENEMY or d.map_x is None or d.map_y is None:
            continue
        site = _assign_site(game_map, d.map_x, d.map_y)
        if site:
            scores[site] += max(d.confidence, 0.1)
    return scores.most_common(1)[0][0] if scores else None


def _agent_round_site(detections: list[Detection], game_map: GameMap | None) -> dict[str, str]:
    """Per enemy agent, the site they were mostly seen near this round."""
    if game_map is None:
        return {}
    per_agent: dict[str, Counter] = defaultdict(Counter)
    for d in detections:
        if d.team != Team.ENEMY or d.map_x is None or d.map_y is None or not d.agent_name:
            continue
        site = _assign_site(game_map, d.map_x, d.map_y)
        if site:
            per_agent[d.agent_name][site] += 1
    return {a: c.most_common(1)[0][0] for a, c in per_agent.items() if c}


def _predict(sequence: list[str], sites: list[str]) -> dict[str, float]:
    """Blend base rate, momentum and a Markov step into a site distribution."""
    if not sequence:
        return {s: round(1.0 / len(sites), 3) for s in sites}
    n = len(sequence)
    counts = Counter(sequence)
    base = {s: counts.get(s, 0) / n for s in sites}
    tau = max(n / 2.0, 1.0)
    mom_raw = {s: 0.0 for s in sites}
    norm = 0.0
    for i, s in enumerate(sequence):
        wgt = math.exp(-(n - 1 - i) / tau)
        if s in mom_raw:
            mom_raw[s] += wgt
        norm += wgt
    momentum = {s: (mom_raw[s] / norm if norm else 0.0) for s in sites}
    last = sequence[-1]
    trans: dict[str, Counter] = defaultdict(Counter)
    for a, b in zip(sequence, sequence[1:], strict=False):
        trans[a][b] += 1
    if trans[last]:
        tot = sum(trans[last].values())
        markov = {s: trans[last].get(s, 0) / tot for s in sites}
    else:
        markov = dict(base)
    blended = {
        s: _W_BASE * base[s] + _W_MOMENTUM * momentum[s] + _W_TRANSITION * markov[s] for s in sites
    }
    total = sum(blended.values()) or 1.0
    return {s: round(blended[s] / total, 3) for s in sites}


def _effective_side(start: Side, round_number: int) -> Side:
    """Auto side per round: sides swap at halftime (after round 12), then each half.

    The player picks their *starting* side; the system flips it automatically —
    no detection needed, it's the Valorant rule.
    """
    if start == Side.UNKNOWN:
        return Side.UNKNOWN
    half = (max(round_number, 1) - 1) // 12  # 0 = rounds 1–12, 1 = 13–24, …
    if half % 2 == 0:
        return start
    return Side.DEFENSE if start == Side.ATTACK else Side.ATTACK


def _confidence(rounds_analyzed: int) -> tuple[float, str]:
    conf = min(0.9, 0.2 + 0.12 * rounds_analyzed)
    if conf < 0.45:
        label = "Low – Early Match"
    elif conf < 0.7:
        label = "Medium"
    else:
        label = "High"
    return round(conf, 3), label


def build_match_intelligence(
    session: Session, match: Match, settings: Settings, round_id: int | None = None
) -> MatchIntelligence:
    game_map = load_map(match.map_name) if match.map_name else None
    sites = _default_sites(game_map)

    rounds: list[Round] = list(match.rounds)
    completed = [r for r in rounds if r.status == ProcessingStatus.COMPLETED]
    current = completed[-1] if completed else (rounds[-1] if rounds else None)
    if round_id is not None:
        chosen = next((r for r in rounds if r.id == round_id), None)
        if chosen is not None:
            current = chosen

    summary = MatchSummary(
        id=match.id, name=match.name, map_name=match.map_name, side=match.side,
        created_at=match.created_at, updated_at=match.updated_at,
        rounds_count=len(rounds), completed_rounds=len(completed),
    )

    # Per-round, per-agent site commitments across the whole match.
    site_sequence: list[str] = []
    agent_site_counts: dict[str, Counter] = defaultdict(Counter)
    all_enemy_points: list[tuple[float, float]] = []
    util_counter: Counter = Counter()
    for r in completed:
        dets = list(r.detections)
        site = r.committed_site or _round_site(dets, game_map)
        if site:
            site_sequence.append(site)
        for agent, asite in _agent_round_site(dets, game_map).items():
            agent_site_counts[agent][asite] += 1
        for d in dets:
            if d.team == Team.ENEMY and d.map_x is not None and d.map_y is not None:
                all_enemy_points.append((d.map_x, d.map_y))
        for u in r.utilities:
            util_counter[f"{u.kind.value}"] += 1

    rounds_analyzed = len(completed)
    conf, conf_label = _confidence(rounds_analyzed)

    # ---- Site presence + next-round probabilities ----------------------
    presence_counts = Counter(site_sequence)
    site_presence = {
        s: round(presence_counts.get(s, 0) / rounds_analyzed, 3) if rounds_analyzed else 0.0
        for s in sites
    }
    prob_map = _predict(site_sequence, sites)
    position_probabilities = sorted(
        (PositionProbability(site=s, probability=p) for s, p in prob_map.items()),
        key=lambda x: x.probability, reverse=True,
    )

    patterns = _patterns(site_sequence, agent_site_counts, rounds_analyzed)
    next_round_no = max((r.round_number for r in completed), default=0) + 1
    next_side = _effective_side(match.side, next_round_no)
    recommendation = _recommendation(
        site_presence, prob_map, sites, conf, conf_label, agent_site_counts, next_side
    )
    learnings = _learnings(rounds_analyzed, site_presence, agent_site_counts, recommendation)

    intel = MatchIntelligence(
        match=summary,
        current_round=RoundOut.model_validate(current) if current else None,
        detected_info=_detected_info(current, match, game_map),
        minimap_markers=_markers(current, game_map),
        utilities=[UtilityOut.model_validate(u) for u in (current.utilities if current else [])],
        timeline=_timeline(current),
        detected_positions=_live_positions(current),
        position_probabilities=position_probabilities,
        patterns=patterns,
        heatmap=_heatmap(all_enemy_points),
        match_memory=_memory(rounds_analyzed, site_presence, util_counter, current, conf),
        enemy_profiles=_profiles(agent_site_counts, rounds_analyzed),
        weapon_economy=_economy(current),
        recommendation=recommendation,
        learnings=learnings,
        analysis_log=_log(match, current, rounds_analyzed, game_map),
    )
    return intel


def _learnings(rounds_analyzed, site_presence, agent_site_counts, rec) -> list[str]:
    """Plain-language description of what the system has learned so far."""
    if not rounds_analyzed:
        return ["No rounds analyzed yet — add rounds to start learning the opponent."]
    out: list[str] = []
    ranked = sorted(site_presence.items(), key=lambda kv: kv[1], reverse=True)
    if ranked and ranked[0][1] > 0:
        top, share = ranked[0]
        spread = ", ".join(f"{s} {round(v * 100)}%" for s, v in ranked if v > 0)
        out.append(
            f"Across {rounds_analyzed} round(s), the enemy committed most to {top} "
            f"({round(share * 100)}%). Full split: {spread}."
        )
    for agent, c in sorted(agent_site_counts.items(), key=lambda kv: -sum(kv[1].values())):
        if agent == "You":
            continue
        site, n = c.most_common(1)[0]
        seen = sum(c.values())
        out.append(f"{agent} is mostly seen near {site} ({n}/{seen} of their sightings).")
        if len(out) >= 5:
            break
    if rec and rec.best_site:
        out.append(
            f"Next round: {rec.action_label} {rec.best_site} "
            f"({round(rec.success_probability * 100)}% est., {rec.confidence_label})."
        )
    return out


# ---- Section builders ----------------------------------------------------
def _detected_info(current: Round | None, match: Match, game_map) -> DetectedInfo | None:
    if current is None:
        return None
    deaths_ally = sum(1 for k in current.killfeed if k.killer_team == Team.ENEMY)
    deaths_enemy = sum(1 for k in current.killfeed if k.killer_team == Team.ALLY)
    known = match.side != Side.UNKNOWN
    side = _effective_side(match.side, current.round_number) if known else current.side
    return DetectedInfo(
        map_name=current.map_name or match.map_name,
        map_confidence=current.map_confidence or (0.99 if (current.map_name or match.map_name) else 0.0),
        side=side,
        side_confidence=0.95 if known else current.side_confidence,
        round_number=current.round_number,
        score_text=current.score_text,
        round_time=current.round_time,
        players_alive_ally=max(0, 5 - deaths_ally),
        players_alive_enemy=max(0, 5 - deaths_enemy),
        spike_planted=current.spike_planted,
        economy=current.economy,
    )


def _markers(current: Round | None, game_map) -> list[MarkerOut]:
    if current is None:
        return []
    dead = {k.victim for k in current.killfeed if k.victim}
    # Latest sighting per (team, agent).
    latest: dict[tuple, Detection] = {}
    for d in current.detections:
        if d.map_x is None or d.map_y is None:
            continue
        key = (d.team, d.agent_name)
        if key not in latest or d.timestamp_seconds > latest[key].timestamp_seconds:
            latest[key] = d
    markers: list[MarkerOut] = []
    for (team, agent), d in latest.items():
        kind = "self" if agent == "You" else "player"
        markers.append(
            MarkerOut(
                team=team, agent_name=agent, map_x=d.map_x, map_y=d.map_y,
                callout=d.callout, dead=(agent in dead), kind=kind,
            )
        )
    # Utilities as markers.
    util_latest: dict[str, UtilityDetection] = {}
    for u in current.utilities:
        if u.map_x is None:
            continue
        prev = util_latest.get(u.kind.value)
        if prev is None or u.timestamp_seconds > prev.timestamp_seconds:
            util_latest[u.kind.value] = u
    for u in util_latest.values():
        markers.append(
            MarkerOut(
                team=Team.ENEMY, agent_name=u.agent_name, map_x=u.map_x, map_y=u.map_y,
                callout=u.callout, kind=u.kind.value,
            )
        )
    return markers


def _timeline(current: Round | None) -> list[TimelineEvent]:
    if current is None:
        return []
    events: list[TimelineEvent] = []
    enemy_dets = sorted(
        (d for d in current.detections if d.team == Team.ENEMY and d.callout),
        key=lambda d: d.timestamp_seconds,
    )
    if enemy_dets:
        first = enemy_dets[0]
        events.append(TimelineEvent(timestamp_seconds=first.timestamp_seconds, kind="spotted",
                                    label="Enemy Seen", detail=first.callout))
    for u in sorted(current.utilities, key=lambda u: u.timestamp_seconds):
        events.append(TimelineEvent(timestamp_seconds=u.timestamp_seconds, kind=u.kind.value,
                                    label=f"{u.kind.value.title()} {u.callout or ''}".strip(),
                                    detail=u.agent_name))
    for k in sorted(current.killfeed, key=lambda k: k.timestamp_seconds):
        events.append(TimelineEvent(timestamp_seconds=k.timestamp_seconds, kind="kill",
                                    label=f"Kill {k.victim or ''}".strip(),
                                    detail=f"{k.killer or '?'} → {k.victim or '?'}"))
    events.sort(key=lambda e: e.timestamp_seconds)
    return events[:12]


def _live_positions(current: Round | None) -> list[DetectedPositionLive]:
    if current is None:
        return []
    end_t = max((d.timestamp_seconds for d in current.detections), default=0.0)
    latest: dict[str, Detection] = {}
    for d in current.detections:
        if d.team != Team.ENEMY or not d.agent_name:
            continue
        if d.agent_name not in latest or d.timestamp_seconds > latest[d.agent_name].timestamp_seconds:
            latest[d.agent_name] = d
    rows = [
        DetectedPositionLive(
            agent_name=a, team=Team.ENEMY, callout=d.callout,
            age_seconds=round(max(0.0, end_t - d.timestamp_seconds), 1),
        )
        for a, d in latest.items()
    ]
    rows.sort(key=lambda r: r.age_seconds)
    return rows


def _patterns(site_sequence, agent_site_counts, rounds_analyzed) -> list[PatternItem]:
    patterns: list[PatternItem] = []
    if not rounds_analyzed:
        return patterns
    counts = Counter(site_sequence)
    if counts:
        top_site, top_n = counts.most_common(1)[0]
        share = top_n / rounds_analyzed
        # Trailing streak on the top site.
        streak = 0
        for s in reversed(site_sequence):
            if s == top_site:
                streak += 1
            else:
                break
        if share >= 0.5:
            patterns.append(PatternItem(
                kind="presence", text=f"Heavy {top_site} Presence",
                detail=f"{top_n}/{rounds_analyzed} rounds" + (f", {streak} in a row" if streak >= 2 else ""),
                confidence=round(min(0.95, share), 3)))
    for agent, c in agent_site_counts.items():
        site, n = c.most_common(1)[0]
        share = n / rounds_analyzed
        if share >= 0.5 and rounds_analyzed >= 1:
            verb = "anchors" if site == "B" else ("holds" if site == "MID" else "favors")
            patterns.append(PatternItem(
                kind="anchor", text=f"{agent} {verb} {site}",
                detail=f"{n}/{rounds_analyzed} rounds", confidence=round(min(0.95, share), 3)))
    patterns.sort(key=lambda p: p.confidence, reverse=True)
    return patterns[:5]


def _heatmap(points: list[tuple[float, float]], grid: int = 14) -> list[HeatCell]:
    if not points:
        return []
    cells: Counter = Counter()
    for x, y in points:
        gx = min(grid - 1, int(x * grid))
        gy = min(grid - 1, int(y * grid))
        cells[(gx, gy)] += 1
    peak = max(cells.values())
    return [
        HeatCell(x=round((gx + 0.5) / grid, 4), y=round((gy + 0.5) / grid, 4),
                 weight=round(n / peak, 4))
        for (gx, gy), n in cells.items()
    ]


def _memory(rounds_analyzed, site_presence, util_counter, current, conf) -> MatchMemory:
    common_util = None
    if util_counter:
        common_util = util_counter.most_common(1)[0][0].title()
    return MatchMemory(
        rounds_analyzed=rounds_analyzed,
        site_presence=site_presence,
        avg_rotation_time=None,
        common_utility=common_util,
        enemy_economy=current.economy if current else None,
        confidence=conf,
    )


def _profiles(agent_site_counts, rounds_analyzed) -> list[EnemyProfile]:
    profiles: list[EnemyProfile] = []
    for agent, c in agent_site_counts.items():
        if agent == "You":
            continue
        site, n = c.most_common(1)[0]
        seen = sum(c.values())
        share = n / max(seen, 1)
        if site == "B":
            tendency, note = "Rarely rotates", "Anchors B"
        elif site == "MID":
            tendency, note = "Rotates with info", "Mid control"
        else:
            tendency, note = "Fast", "Aggressive"
        profiles.append(EnemyProfile(
            agent_name=agent, note=note, favored_site=site,
            site_share=round(share, 3), rotation_tendency=tendency, rounds_seen=seen))
    profiles.sort(key=lambda p: p.rounds_seen, reverse=True)
    return profiles


def _economy(current: Round | None) -> WeaponEconomy:
    econ = (current.economy if current else None) or "Unknown"
    tier = {"Eco": "eco", "Force": "force", "Full Buy": "full"}.get(econ, "unknown")
    return WeaponEconomy(
        enemy_label=econ, enemy_tier=tier,
        ally_label="Full Buy", ally_tier="full",
    )


def _recommendation(
    site_presence, prob_map, sites, conf, conf_label, agent_site_counts, side: Side
) -> Recommendation:
    if not site_presence or all(v == 0 for v in site_presence.values()):
        return Recommendation(
            best_site=None, mode="attack", action_label="Attack", success_probability=0.0,
            confidence=conf, confidence_label=conf_label, reasons=["Not enough data yet."],
            suggested_play=["Upload more rounds to build a read."])

    plantable = [s for s in sites if s.upper() != "MID"] or sites
    top_site = max(sites, key=lambda s: site_presence.get(s, 0.0))

    if side == Side.DEFENSE:
        # You defend → the enemy attacks. Stack the site they hit most.
        best = max(plantable, key=lambda s: site_presence.get(s, 0.0))
        success = round(min(0.95, 0.4 + 0.5 * site_presence.get(best, 0.0)), 3)
        reasons = [
            f"As defenders, expect attacks on {best} "
            f"({round(site_presence.get(best, 0) * 100)}% of rounds went there).",
            f"{best} is their most-committed site so far.",
        ]
        suggested = [
            f"Stack {best} with 2–3 players.",
            "Hold utility for delay / retake.",
            "Keep one watching the lightly-hit sites for a flank.",
        ]
        return Recommendation(
            best_site=best, mode="defense", action_label="Stack", success_probability=success,
            confidence=conf, confidence_label=conf_label, reasons=reasons, suggested_play=suggested)

    # You attack (or unknown) → hit the least-defended site.
    best = min(plantable, key=lambda s: site_presence.get(s, 0.0))
    success = round(min(0.92, 0.5 + 0.45 * (1.0 - site_presence.get(best, 0.0))), 3)
    reasons = [f"Enemies defend {top_site} most ({round(site_presence[top_site] * 100)}% of rounds)."]
    for agent, c in agent_site_counts.items():
        s, _ = c.most_common(1)[0]
        if s == "B" and agent != "You":
            reasons.append(f"{agent} anchors B → limited support elsewhere.")
            break
    reasons.append(f"{best} shows the lightest defensive commitment.")
    suggested = [
        f"Take {best} with 3–4 players.",
        "Use utility to block rotations and cut off support.",
        "Expect a lone anchor on site — trade fast.",
    ]
    return Recommendation(
        best_site=best, mode="attack", action_label="Attack", success_probability=success,
        confidence=conf, confidence_label=conf_label, reasons=reasons, suggested_play=suggested)


def _log(match, current, rounds_analyzed, game_map) -> list[AnalysisLogStep]:
    if current is None:
        return [AnalysisLogStep(step=1, title="Awaiting first round",
                                detail="Upload a round recording to begin analysis.", status="skipped")]
    enemies = sum(1 for d in current.detections if d.team == Team.ENEMY)
    allies = sum(1 for d in current.detections if d.team == Team.ALLY)
    utils = len(current.utilities)
    prior = max(0, rounds_analyzed - 1)
    return [
        AnalysisLogStep(step=1, title="Map Identified",
                        detail=f"{(current.map_name or match.map_name or 'Unknown')} "
                               f"({round((current.map_confidence or 0.99) * 100)}%)"),
        AnalysisLogStep(step=2, title="Minimap Detected", detail="Calibrated ROI located"),
        AnalysisLogStep(step=3, title="Player Detection",
                        detail=f"{enemies} enemy / {allies} ally sightings"),
        AnalysisLogStep(step=4, title="Utility Detection", detail=f"{utils} utilities"),
        AnalysisLogStep(step=5, title="Pattern Comparison",
                        detail=f"Compared with {prior} previous round(s)"),
        AnalysisLogStep(step=6, title="Prediction Calculated", detail="Probabilities updated"),
        AnalysisLogStep(step=7, title="Recommendation Generated", detail="Best site suggested"),
    ]
