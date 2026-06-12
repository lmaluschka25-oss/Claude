# Valorant Vision Coach

A **post-match** coaching tool that analyzes your *recorded* Valorant gameplay
with computer vision and turns it into a tactical review dashboard. It reads
**only what was visible on your own screen** — the 3D viewport, your minimap,
the killfeed, the scoreboard, and the round timer — and never anything else.

> **Scope & fair play.** This project deliberately does **not** do anything that
> runs alongside a live game or touches privileged data. No real-time overlay,
> no game-memory reads, no packet inspection, no reading of hidden/unseen
> enemies, no input automation. It ingests a video file *after* the match, the
> same footage a coach would scrub through. See [docs/ETHICS.md](docs/ETHICS.md)
> for the full boundary and why it was drawn here.

## What it does

Upload a match recording and the pipeline produces, frame by frame:

- **Enemy & agent detections** — agent name, team, confidence, timestamp.
- **Location on the map** — from revealed enemy markers on *your* minimap, or
  your own position as an engagement proxy for viewport sightings.
- **Killfeed / scoreboard / timer** parsing (when OCR is enabled), used to
  segment rounds.
- A **Last Known Enemy Position** system with a configurable decay (old
  sightings drop off after a TTL you choose).
- **Rotation estimates** — transparent dead-reckoning over a map callout graph,
  bounded by how far an enemy could have moved since you last saw them.
- **Site pressure** — recency/proximity-weighted enemy presence per bomb site.

…all surfaced in a modern tactical dashboard with a round-by-round timeline
scrubber. Everything runs locally; nothing is uploaded anywhere.

## Tech stack

| Layer      | Tech                                            |
|------------|-------------------------------------------------|
| Backend    | Python · FastAPI · SQLAlchemy · SQLite          |
| Vision     | OpenCV · Ultralytics YOLO · EasyOCR (optional)  |
| Frontend   | React · Vite (SVG tactical map, no game assets) |
| Packaging  | Docker · docker-compose                         |

## Quick start (Docker)

```bash
cp .env.example .env          # optional; defaults are fine
docker compose up --build
```

- Dashboard → http://localhost:5173
- API docs  → http://localhost:8000/docs

This boots with the **mock detector** so you can explore the whole app
immediately — no GPU or trained weights required. To run real inference, see
[docs/SETUP.md](docs/SETUP.md#real-inference).

## Quick start (local, no Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload          # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

Run the tests:

```bash
cd backend && pytest
```

## Documentation

- [docs/SETUP.md](docs/SETUP.md) — install, configuration, training a model.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the pipeline and analysis work.
- [docs/API.md](docs/API.md) — REST endpoints.
- [docs/ETHICS.md](docs/ETHICS.md) — scope, fair-play boundary, and limitations.

## Project layout

```
valorant-vision-coach/
├── backend/         FastAPI app, vision pipeline, analysis, tests
│   ├── app/
│   │   ├── vision/      detector, OCR, minimap calibration, map metadata
│   │   ├── analysis/    last-known positions, rotation, site pressure
│   │   ├── services/    processing pipeline + persistence helpers
│   │   └── api/         REST routes
│   └── data/maps/       callout graphs (Ascent, Bind)
├── frontend/        React + Vite tactical dashboard
├── docs/            setup, architecture, API, ethics
└── docker-compose.yml
```
