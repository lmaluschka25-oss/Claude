# Setup guide

## Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Node 18+** (for the frontend)
- **Docker + Docker Compose** (optional, for the containerized stack)
- A trained YOLO model is only needed for *real* inference — the app runs out of
  the box with the built-in mock detector.

## Option A — Docker (recommended)

```bash
cp .env.example .env        # optional
docker compose up --build
```

| Service   | URL                          |
|-----------|------------------------------|
| Dashboard | http://localhost:5173        |
| API + docs| http://localhost:8000/docs   |

Data (uploads + SQLite DB) is persisted in the `vvc-data` Docker volume. Stop
with `docker compose down`; add `-v` to also wipe the data volume.

## Option B — Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt      # core + test tooling
uvicorn app.main:app --reload
```

The API serves on `http://localhost:8000`. Interactive docs at `/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite serves on `http://localhost:5173` and proxies `/api` to the backend, so no
CORS configuration is needed in development.

### Tests & lint

```bash
cd backend
pytest          # 18 tests, runs on the mock backend (no ML/GPU needed)
ruff check app tests
```

## Configuration

All backend settings are environment variables prefixed `VVC_` (see
`backend/app/config.py`). Common ones:

| Variable                    | Default            | Meaning                                       |
|-----------------------------|--------------------|-----------------------------------------------|
| `VVC_DETECTOR_BACKEND`      | `yolo`             | `yolo` (real) or `mock` (synthetic)           |
| `VVC_YOLO_MODEL_PATH`       | `data/models/valorant.pt` | Path to trained weights                |
| `VVC_YOLO_CONFIDENCE`       | `0.35`             | Detection confidence threshold                |
| `VVC_YOLO_DEVICE`           | `auto`             | `auto` / `cpu` / `cuda:0` …                   |
| `VVC_FRAME_SAMPLE_STRIDE`   | `6`                | Process 1 of every N frames                   |
| `VVC_OCR_BACKEND`           | `easyocr`          | `easyocr` / `tesseract` / `off`               |
| `VVC_SIGHTING_TTL_SECONDS`  | `12`               | Default last-known decay window               |
| `VVC_MOVEMENT_SPEED_NORM`   | `0.13`             | Enemy speed (normalized map units / second)   |
| `VVC_SITE_PRESSURE_RADIUS`  | `0.22`             | Pressure radius around a site (normalized)    |

> If `VVC_DETECTOR_BACKEND=yolo` but no weights are found, the app logs a clear
> warning and **falls back to the mock detector** so it still runs.

The frontend reads `VITE_API_BASE` (default `/api`).

## Real inference

1. **Install ML dependencies:**

   ```bash
   cd backend && pip install -r requirements-ml.txt   # ultralytics + easyocr
   ```

   For Docker: `INSTALL_ML=true docker compose build backend`.

2. **Provide a trained model** at `backend/data/models/valorant.pt`. See
   [`backend/data/models/README.md`](../backend/data/models/README.md) for the
   required label vocabulary and a training outline (sample frames → annotate →
   `yolo detect train …`).

3. **Enable the backends:**

   ```bash
   export VVC_DETECTOR_BACKEND=yolo
   export VVC_OCR_BACKEND=easyocr
   ```

4. **Calibrate the minimap** if your HUD layout differs from the 16:9 default.
   The minimap rectangle and any per-side rotation/flip are defined in
   `backend/app/vision/calibration.py` (`MinimapCalibration`). HUD OCR regions
   live in `backend/app/vision/ocr.py`.

## Adding a map

Drop a JSON file in `backend/data/maps/` following the schema of `ascent.json`:
callouts with normalized `x,y` in `[0,1]`, the three `sites`, and `edges`
between adjacent callouts (the rotation graph). Tag the bombsite anchor callouts
with their `site`. Restart the backend to pick it up.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Upload processes but no detections | Using mock? expected synthetic data. For real data, confirm weights load (`GET /api/system/info` → `detector_ready: true`). |
| `detector_ready: false` | Weights missing or `ultralytics` not installed; check the startup logs. |
| Video won't open | Install `ffmpeg`; confirm the file is a supported container (`.mp4/.mov/.mkv/.avi/.webm`). |
| OCR returns nothing | `ocr_ready: false` — install `easyocr`/`pytesseract`, or set `VVC_OCR_BACKEND=off`. |
| Enemies appear in the wrong map spot | Re-calibrate the minimap ROI for your resolution/HUD scale. |
