"""Next-round site-commitment prediction (post-match scouting model).

The map is the primary source: for each analyzed round we derive which site the
enemy committed to from where their *minimap-revealed* presence concentrated
(viewport sightings count less). From that sequence of commitments we predict
the next round as a blend of interpretable components:

* **base rate**   — how often each site is hit overall (prior),
* **momentum**    — recency-weighted recent behaviour,
* **transition**  — a first-order Markov step from the last committed site,
* **streak**      — a small repeat bias when they keep hitting one site.

It is a transparent probabilistic model, not a black box — every number can be
explained back to the rounds it came from. This is preparation material; it
never runs live or reveals current positions.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from ..config import Settings
from ..models import DetectionSource, Team
from ..schemas import (
    NextRoundPrediction,
    PredictionFactor,
    SitePrediction,
)
from ..vision.maps import GameMap
from .tendencies import _assign_site
from .tracks import DetectionLike

# The map is the main source: a revealed minimap marker counts double a
# viewport sighting when deciding a round's committed site.
_SOURCE_WEIGHT = {DetectionSource.MINIMAP: 1.0, DetectionSource.VIEWPORT: 0.5}

# Blend weights for the prediction components.
_W_BASE = 0.34
_W_MOMENTUM = 0.34
_W_TRANSITION = 0.32


def _round_commitment(
    dets: list[DetectionLike], game_map: GameMap
) -> tuple[str | None, float]:
    """Return the site the enemy committed to this round and how decisive it was."""
    scores: Counter[str] = Counter()
    for d in dets:
        if d.map_x is None or d.map_y is None:
            continue
        site = _assign_site(game_map, d.map_x, d.map_y)
        if site is None:
            continue
        scores[site] += _SOURCE_WEIGHT.get(d.source, 0.5) * max(d.confidence, 0.1)
    if not scores:
        return None, 0.0
    total = sum(scores.values())
    site, value = scores.most_common(1)[0]
    return site, value / total


def _empty(match_id: int, map_name: str | None) -> NextRoundPrediction:
    return NextRoundPrediction(
        match_id=match_id,
        map_name=map_name,
        rounds_analyzed=0,
        predicted_sites=[],
        confidence=0.0,
        top_factor=None,
        factors=[],
        last_committed_site=None,
        per_round_commitment=[],
    )


def predict_next_round(
    detections: list[DetectionLike],
    rounds: list,
    match_id: int,
    map_name: str | None,
    game_map: GameMap | None,
    settings: Settings,
) -> NextRoundPrediction:
    if game_map is None or not game_map.sites:
        return _empty(match_id, map_name)

    sites = game_map.sites
    round_number = {r.id: r.round_number for r in rounds}

    # Group located enemy sightings per round.
    by_round: dict[object, list[DetectionLike]] = defaultdict(list)
    for d in detections:
        if d.team != Team.ENEMY or d.map_x is None or d.map_y is None:
            continue
        by_round[getattr(d, "round_id", None)].append(d)

    ordered_rounds = sorted(by_round.keys(), key=lambda rid: round_number.get(rid, 1_000_000))
    sequence: list[str] = []
    decisiveness: list[float] = []
    for rid in ordered_rounds:
        site, decisive = _round_commitment(by_round[rid], game_map)
        if site is not None:
            sequence.append(site)
            decisiveness.append(decisive)

    n = len(sequence)
    if n == 0:
        return _empty(match_id, map_name)

    # --- Component 1: base rate ------------------------------------------
    counts = Counter(sequence)
    base = {s: counts.get(s, 0) / n for s in sites}

    # --- Component 2: momentum (recency-weighted) ------------------------
    tau = max(n / 2.0, 1.0)
    momentum_raw = {s: 0.0 for s in sites}
    norm = 0.0
    for i, s in enumerate(sequence):
        w = math.exp(-(n - 1 - i) / tau)
        momentum_raw[s] += w
        norm += w
    momentum = {s: (momentum_raw[s] / norm if norm else 0.0) for s in sites}

    # --- Component 3: first-order transition from the last site ----------
    last = sequence[-1]
    transitions: dict[str, Counter[str]] = defaultdict(Counter)
    for a, b in zip(sequence, sequence[1:], strict=False):
        transitions[a][b] += 1
    if transitions[last]:
        tot = sum(transitions[last].values())
        transition = {s: transitions[last].get(s, 0) / tot for s in sites}
    else:
        transition = dict(base)

    # --- Blend + streak bias ---------------------------------------------
    final = {
        s: _W_BASE * base[s] + _W_MOMENTUM * momentum[s] + _W_TRANSITION * transition[s]
        for s in sites
    }
    streak = 1
    for s in reversed(sequence[:-1]):
        if s == last:
            streak += 1
        else:
            break
    if streak >= 2:
        final[last] *= 1.0 + 0.15 * min(streak, 3)

    total = sum(final.values()) or 1.0
    final = {s: final[s] / total for s in sites}

    predicted = sorted(
        (SitePrediction(site=s, probability=round(p, 3)) for s, p in final.items()),
        key=lambda sp: sp.probability,
        reverse=True,
    )
    top_site = predicted[0].site

    # --- Explainability: which component drove the top pick? -------------
    contributions = {
        "Grundtendenz": _W_BASE * base[top_site],
        "Momentum": _W_MOMENTUM * momentum[top_site],
        "Abfolge": _W_TRANSITION * transition[top_site],
    }
    driver = max(contributions, key=contributions.get)
    contrib_total = sum(contributions.values()) or 1.0

    factors = [
        PredictionFactor(
            label="Grundtendenz",
            detail=" · ".join(f"{s} {round(base[s] * 100)}%" for s in sites if base[s] > 0),
            weight=round(contributions["Grundtendenz"] / contrib_total, 3),
        ),
        PredictionFactor(
            label="Momentum (letzte Runden)",
            detail=" · ".join(
                f"{s} {round(momentum[s] * 100)}%" for s in sites if momentum[s] > 0.01
            ),
            weight=round(contributions["Momentum"] / contrib_total, 3),
        ),
        PredictionFactor(
            label=f"Abfolge nach {last}",
            detail=" · ".join(
                f"{s} {round(transition[s] * 100)}%" for s in sites if transition[s] > 0
            ),
            weight=round(contributions["Abfolge"] / contrib_total, 3),
        ),
    ]
    if streak >= 2:
        factors.append(
            PredictionFactor(
                label="Serie",
                detail=f"{streak}× in Folge {last}",
                weight=round(min(0.15 * min(streak, 3), 0.45), 3),
            )
        )

    driver_text = {
        "Grundtendenz": f"über alle Runden meist {top_site}",
        "Momentum": f"zuletzt verstärkt {top_site}",
        "Abfolge": f"nach {last} folgt oft {top_site}",
    }[driver]
    if streak >= 2 and top_site == last:
        driver_text = f"{streak}× in Folge {last} — Serie hält oft an"

    mean_decisive = sum(decisiveness) / len(decisiveness) if decisiveness else 0.0
    confidence = round(min(1.0, (n / (n + 3.0)) * (0.5 + 0.5 * mean_decisive)), 3)

    return NextRoundPrediction(
        match_id=match_id,
        map_name=map_name,
        rounds_analyzed=n,
        predicted_sites=predicted,
        confidence=confidence,
        top_factor=driver_text,
        factors=factors,
        last_committed_site=last,
        per_round_commitment=sequence,
    )
