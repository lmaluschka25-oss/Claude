# Architecture

## Data flow

```
            recorded match (.mp4)
                    │
                    ▼
        ┌───────────────────────┐
        │  VideoProcessor       │  OpenCV capture + frame sampling
        │  (vision/)            │
        │   ├─ Detector (YOLO)  │  enemies / agents / minimap markers
        │   ├─ OcrEngine        │  timer / scoreboard / killfeed
        │   └─ MinimapCalibration  minimap px → normalized map coords
        └───────────┬───────────┘
                    │  DetectionRecord / KillfeedRecord / RoundRecord
                    ▼
        ┌───────────────────────┐
        │  Pipeline (services/) │  background worker, progress → DB
        └───────────┬───────────┘
                    ▼
                 SQLite  ◀── matches, rounds, detections, killfeed
                    │
                    ▼
        ┌───────────────────────┐
        │  Analysis (analysis/) │  pure functions over detections
        │   ├─ tracks           │  per-enemy sighting tracks
        │   ├─ last_known       │  decay / staleness
        │   ├─ rotation         │  graph dead-reckoning
        │   └─ site_pressure    │  recency × proximity
        └───────────┬───────────┘
                    ▼
              FastAPI REST  ──►  React dashboard (timeline + SVG map)
```

## Components

### Vision (`app/vision/`)

- **`detector.py`** — pluggable detection backends behind `BaseDetector`.
  `YoloDetector` wraps Ultralytics (lazy import, fails soft); `MockDetector`
  emits deterministic synthetic data so the whole system runs without weights.
  Labels (`mm_self`, `mm_enemy:<agent>`, `enemy:<agent>`, …) carry the semantics
  the processor interprets.
- **`calibration.py`** — `MinimapCalibration` maps minimap pixels to normalized
  `[0,1]` map coordinates, with per-side rotation/flip support.
- **`ocr.py`** — optional HUD OCR (EasyOCR/Tesseract) for timer, scoreboard, and
  killfeed; degrades to no-ops when unavailable.
- **`maps.py`** — loads map metadata (callouts, sites, adjacency) and provides
  geometry helpers: nearest callout, site centroid, and a Dijkstra `reachable`
  walk used by rotation estimation.
- **`video_processor.py`** — orchestrates capture → detect → OCR → coordinate
  resolution → round segmentation, yielding plain records.

### Analysis (`app/analysis/`)

Every function is **pure** and consumes only `Detection` rows.

- **`tracks.py`** — collapses many sightings into one `EnemyTrack` per agent
  (last position, previous position for heading, age). Tracks older than the TTL
  are dropped here — this is the "remove old sightings" rule.
- **`last_known_position.py`** — formats tracks into last-known rows with age and
  a `stale` flag.
- **`rotation.py`** — see the model below.
- **`site_pressure.py`** — see the model below.
- **`engine.py`** — assembles a full `AnalysisSnapshot` for a moment `T`.

### Services (`app/services/`)

- **`pipeline.py`** — a single-worker `ThreadPoolExecutor` processes uploads
  (serializing GPU/model access), streams progress into the DB, and persists
  results. Swap in Celery/RQ for scale without touching `run()`.
- **`match_service.py`** — query/persistence helpers.

### API (`app/api/`) & Frontend (`frontend/`)

FastAPI routers expose matches, detections, killfeed, maps, system info, and the
analysis endpoints. The React app polls processing status, then drives a
timeline scrubber that re-queries the snapshot endpoint (throttled to ~5/s) and
renders an SVG tactical map plus last-known / rotation / site-pressure panels.

## Data model

```
Match 1───* Round
  │           
  ├──* Detection   (timestamp, agent, team, source, confidence, map_x/y, callout, bbox)
  └──* KillfeedEvent (timestamp, killer, victim, weapon, headshot)
```

`Detection.source` is either `viewport` (seen in the 3D view; located by the
player's own position) or `minimap` (a revealed marker; located directly).

## The analysis models

### Last known position

For a query time `T` and TTL `τ`, take each enemy's most recent located sighting
with timestamp ≤ `T`. `age = T − last_seen`. Sightings with `age > τ` are
dropped (or flagged `stale` if `include_stale` is requested). Simple, and it
mirrors what a human remembers: "where did I last see them, and how long ago?"

### Rotation estimation

Transparent dead-reckoning over the callout graph:

1. **Reach** = `movement_speed × age` (normalized units). An enemy last seen
   longer ago could be further away.
2. **Reachable callouts** = Dijkstra from the last-seen callout, bounded by
   reach (edge weights = Euclidean distance between connected callouts).
3. **Score** each candidate by three interpretable factors:
   - *progress* — a Gaussian centered on the full-speed frontier (`reach`), so
     destinations consistent with continued movement rank higher;
   - *heading* — alignment with the enemy's last observed movement direction;
   - *objective* — a bonus for callouts that lead onto a bomb site.
4. Keep the top few, normalize into a likelihood distribution, and report ETA
   (`distance / speed`) per candidate.

No hidden state is used — it is the same reasoning a coach does from the footage.

### Site pressure

For each site, gather enemy sightings within the TTL window and within the site
radius. Each contributes `recency × proximity × confidence`, where recency is an
exponential decay and proximity falls off linearly to the radius edge. Multiple
sightings of one agent are de-duplicated to their strongest contribution, then
summed and squashed to `[0,1]` via `1 − e^(−raw/K)`. Output includes the
weighted headcount and the contributing callouts.

## Extension points

- **New detector** — implement `BaseDetector.detect` and wire it in
  `build_detector`.
- **New map** — add a JSON file under `data/maps/` (see SETUP.md).
- **New analysis** — add a pure function over detections and surface it via a
  route + dashboard panel.
- **Scale processing** — replace the thread-pool executor in `pipeline.py` with a
  task queue.
