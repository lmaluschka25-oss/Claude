# Valorant Match Intelligence

A **persistent, post-match Valorant analysis platform**. It is not a one-shot
screenshot tool: every recording you add belongs to a **match**, and the system
builds a growing **Match Memory** that learns the opponent round by round —
surfacing patterns, position probabilities, and a next-round recommendation,
with every reasoning step shown in the UI.

> **Scope & fair play.** This is strictly **post-match**. It analyzes recordings
> *after* you play and reads **only what was visible on your own screen**
> (minimap, viewport, killfeed, scoreboard, timer). No real-time overlay, no
> game-memory reads, no packet inspection, no hidden-info reveal, no input
> automation. See [docs/ETHICS.md](docs/ETHICS.md).

## What it does

- **Match management** — create matches, add rounds (record screen in-browser
  or upload), reopen history; everything persisted in SQLite.
- **Per-round analysis pipeline** — detect minimap markers (enemies/allies/you),
  utilities, killfeed; resolve callouts; derive the round's committed site and
  HUD metadata; show a step-by-step **Analysis Log**.
- **Match Memory & pattern learning** — across rounds: site presence, agent site
  preferences ("Killjoy anchors B", "Heavy A Presence"), enemy profiles,
  economy read; **confidence rises** as more rounds are analyzed.
- **Prediction & recommendation** — next-round **position probabilities**
  (A/B/Mid …) from a base-rate + momentum + Markov blend, and a **best-site
  recommendation** with reasons and a suggested play.
- **Visual workspace** — enlarged tactical minimap, original round video, round
  timeline, heatmap (site control), and all of the above as a professional
  dashboard.

## Tech stack

| Layer     | Tech                                                  |
|-----------|-------------------------------------------------------|
| Backend   | Python · FastAPI · SQLAlchemy · SQLite                |
| Vision    | OpenCV · color-based minimap detector · YOLO (optional) · EasyOCR (optional) |
| Frontend  | React · Vite (vector dashboard, no game assets)       |
| Packaging | Docker · docker-compose                               |

## Quick start (Docker)

```bash
cp .env.example .env          # optional
docker compose up --build
```

- Dashboard → http://localhost:5173
- API docs  → http://localhost:8000/docs

Boots with the **mock detector** so the whole dashboard is explorable
immediately. For real footage set `VVC_DETECTOR_BACKEND=minimap` (no ML needed)
and calibrate in the **Settings** tab; see [docs/SETUP.md](docs/SETUP.md).

## Quick start (local)

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

Tests: `cd backend && pytest`

## Using it

1. **MATCHES** tab → create a match (pick the map / side).
2. Open it (**ANALYSIS** tab) → **Record round** or **Upload recording** in the
   sidebar. Each upload becomes a round and is analyzed in the background.
3. As rounds complete, the dashboard fills in: minimap, timeline, live
   positions, probabilities, patterns, heatmap, match memory, enemy profiles,
   recommendation, and the analysis log.
4. **LEARNINGS** shows what the system has learned across the match;
   **SETTINGS** has system info + minimap calibration.

## Detector backends

| `VVC_DETECTOR_BACKEND` | What it does |
|------------------------|--------------|
| `minimap`              | Classical CV — reads revealed **red enemy dots** off your minimap. Real, no training. Calibrate the ROI in Settings. |
| `yolo`                 | Full detection incl. agents — needs trained weights (`requirements-ml.txt`). |
| `mock` (default)       | Deterministic synthetic match data for demos/tests. |

## Documentation

- [docs/SETUP.md](docs/SETUP.md) — install, configuration, calibration, training.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — model, pipeline, intelligence.
- [docs/API.md](docs/API.md) — REST endpoints.
- [docs/ETHICS.md](docs/ETHICS.md) — scope and fair-play boundary.

## Project layout

```
valorant-vision-coach/
├── backend/   FastAPI app
│   └── app/
│       ├── vision/      detector (mock / minimap-CV / YOLO), OCR, calibration, maps
│       ├── analysis/    intelligence aggregation (memory, patterns, prediction)
│       ├── services/    round-processing pipeline + persistence
│       └── api/routes/  matches, rounds, intelligence, maps, system
├── frontend/  React dashboard (TopNav · Analysis · Learnings · Settings)
└── docker-compose.yml
```

Not affiliated with or endorsed by Riot Games.
