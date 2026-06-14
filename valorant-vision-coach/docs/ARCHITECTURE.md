# Architecture

## Data flow

```
        recording (one round)
               │  POST /matches/{id}/rounds
               ▼
   ┌───────────────────────┐
   │ Pipeline (services/)  │  background worker, per round
   │  └ VideoProcessor     │  OpenCV sample → Detector → OCR
   │       ├ Detector      │  mock | minimap-CV | YOLO
   │       └ calibration   │  minimap px → normalized map coords
   └───────────┬───────────┘
               │ detections / utilities / killfeed + committed site
               ▼
            SQLite   Match 1──* Round 1──* {Detection, UtilityDetection, KillfeedEvent}
               │
               ▼  GET /matches/{id}/intelligence
   ┌───────────────────────┐
   │ intelligence.py       │  aggregate across all rounds of the match
   │  memory · patterns ·  │
   │  probabilities ·      │
   │  heatmap · profiles · │
   │  recommendation · log │
   └───────────┬───────────┘
               ▼
        React dashboard (Analysis · Learnings · Settings)
```

## Data model (`models.py`)

```
Match (competitive match: map, side, memory)
  └─* Round (one uploaded recording = one round; status, committed_site, score, economy …)
        ├─* Detection        (agent/enemy/ally/you sighting; team, source, map_x/y, callout)
        ├─* UtilityDetection (smoke/recon/turret/… marker)
        └─* KillfeedEvent    (killer, victim, weapon, headshot)
```

A round is processed once; its rows are immutable. Match-level intelligence is
computed **on read** from all completed rounds, so confidence and patterns
improve automatically as rounds are added.

## Vision (`app/vision/`)

- **`detector.py`** — `BaseDetector` with three backends:
  - `MinimapColorDetector` — classical HSV segmentation of revealed red enemy
    markers on the minimap (no model needed); ROI/colors are configurable.
  - `MockDetector` — round-aware synthetic scene (enemies/allies/you/utilities +
    HUD metadata) so the full dashboard runs without weights.
  - `YoloDetector` — Ultralytics inference (lazy import, fails soft).
- **`calibration.py`** — minimap-pixel → normalized `[0,1]` map coordinates.
- **`maps.py`** — callouts, sites, and the rotation graph (11 maps); geometry
  helpers incl. site centroids used to assign a sighting to a site.
- **`ocr.py`** — optional HUD OCR (timer/score/killfeed).
- **`video_processor.py`** — orchestrates capture → detect → OCR → coordinate
  resolution, emitting plain records.

## Intelligence (`app/analysis/intelligence.py`)

`build_match_intelligence(session, match, settings, round_id=None)` computes the
whole dashboard payload:

- **Per-round committed site** — dominant enemy site from map-assigned sightings.
- **Match memory** — site-presence shares, common utility, economy; confidence
  scales with rounds (`0.2 + 0.12·rounds`, capped).
- **Position probabilities** — next-round site distribution from a blend of base
  rate, recency **momentum**, and a first-order **Markov** step.
- **Patterns** — "Heavy A Presence", per-agent anchors ("Killjoy anchors B").
- **Heatmap** — enemy positions binned to a normalized grid.
- **Enemy profiles** — favored site + rotation tendency per agent.
- **Recommendation** — the bomb site enemies commit to *least*, with reasons.
- **Analysis log** — the 7 pipeline steps with real counts.
- **Per-round scene** — minimap markers, timeline, live positions, detected info
  (driven by the selected/`current` round).

## Services & API

- **`pipeline.py`** — single-worker `ThreadPoolExecutor`; `run(round_id)`
  processes a round, persists records, derives `committed_site` + metadata.
- **`api/routes/matches.py`** — match CRUD, round upload, intelligence, plus
  `rounds_router` for per-round detail/detections/video/minimap-preview.

## Frontend (`frontend/src/`)

- **TopNav** → MATCHES / ANALYSIS / LEARNINGS / SETTINGS.
- **ANALYSIS** composes the dashboard: `MatchSidebar` (match info + rounds +
  uploader), `EnlargedMinimap`, `RoundVideo`, `RoundTimeline`, `Heatmap`, and the
  panels in `panels.jsx` (detected info, utilities, live positions,
  probabilities, patterns, match memory, enemy profiles, economy,
  recommendation, reasoning, analysis log).
- Polls `/intelligence` while rounds are processing.

## Extending

- **New detector** → implement `BaseDetector.detect`, wire into `build_detector`.
- **New map** → add JSON under `data/maps/` (see SETUP.md).
- **New analysis** → add a section builder in `intelligence.py` + a panel.
- **Scale** → swap the thread-pool for Celery/RQ; `run(round_id)` is unchanged.
