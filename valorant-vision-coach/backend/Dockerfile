# Backend image. By default installs only the core runtime (mock detector).
# Build with --build-arg INSTALL_ML=true to add YOLO + OCR for real inference.
FROM python:3.11-slim AS base

ARG INSTALL_ML=false
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System libs: ffmpeg for broad codec support, libGL/glib for OpenCV runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-ml.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install -r requirements-ml.txt; fi

COPY app ./app
COPY data ./data

# Read-only app assets (maps, models) live in /app/data and ship in the image.
# Writable state (uploads + sqlite db) goes to /app/var, which compose persists
# via a named volume — kept separate so a volume never shadows the bundled maps.
ENV VVC_UPLOAD_DIR=/app/var/uploads \
    VVC_DATABASE_URL=sqlite:////app/var/vision_coach.db
RUN mkdir -p /app/var

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
