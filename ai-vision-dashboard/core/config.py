"""Zentrale Konfiguration.

Liest Einstellungen aus Umgebungsvariablen / .env und stellt sie als
typisiertes ``Config``-Objekt bereit. Hier liegen außerdem die globalen
Konstanten (Kategorien, Fokus-Gewichte), damit sie projektweit konsistent sind.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

# .env laden, falls vorhanden (optional – kein harter Fehler ohne python-dotenv)
try:  # pragma: no cover - rein optionaler Komfort
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


# --- Aktivitäts-Kategorien, die das Tool unterscheidet --------------------
CATEGORIES = ["Coding", "Browsing", "Gaming", "Watching Video", "Messaging", "Unknown"]

# Gewichtung jeder Kategorie für den Fokus-Score (0–100). Produktive Tätigkeiten
# bekommen einen hohen Wert, ablenkende einen niedrigen.
FOCUS_WEIGHTS = {
    "Coding": 95,
    "Messaging": 60,
    "Browsing": 55,
    "Watching Video": 25,
    "Gaming": 15,
    "Unknown": 50,
}

# Günstig & schnell – ideal für eine häufige, strukturierte Klassifizierung.
# Für höhere Qualität kann via AIVD_MODEL z. B. "claude-opus-4-8" gesetzt werden.
DEFAULT_MODEL = "claude-haiku-4-5"


def _get(name: str, default=None):
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, ""))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, "")))
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _detect_tesseract() -> Optional[str]:
    """Sucht tesseract.exe an den üblichen Windows-Installationspfaden."""
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@dataclass
class Config:
    """Alle Laufzeit-Einstellungen an einem Ort."""

    # AI
    anthropic_api_key: str = ""
    model: str = DEFAULT_MODEL

    # Timing
    capture_interval: float = 1.0  # Sekunden pro Screenshot
    ai_interval: float = 25.0      # Sekunden zwischen LLM-Aufrufen (Kosten sparen)

    # Vorschau / Screen
    preview_width: int = 480
    monitor_index: int = 1

    # OCR
    ocr_enabled: bool = True
    ocr_lang: str = "eng"
    ocr_max_width: int = 1600
    ocr_change_threshold: float = 6.0  # ab welcher Bildänderung neu ge-OCR-t wird
    tesseract_cmd: Optional[str] = None

    # Metriken / Fokus-Score
    max_samples: int = 50000
    focus_threshold: float = 50.0       # >= gilt als "fokussiert"
    switch_penalty_per: float = 5.0     # Abzug pro App-Wechsel (letzte Minute)
    max_switch_penalty: float = 30.0
    focus_ema_alpha: float = 0.2        # Glättung des Fokus-Scores

    @classmethod
    def from_env(cls) -> "Config":
        """Erzeugt eine Konfiguration aus Umgebungsvariablen / .env."""
        return cls(
            anthropic_api_key=_get("ANTHROPIC_API_KEY", "") or "",
            model=_get("AIVD_MODEL", DEFAULT_MODEL),
            capture_interval=max(0.25, _get_float("AIVD_CAPTURE_INTERVAL", 1.0)),
            ai_interval=max(5.0, _get_float("AIVD_AI_INTERVAL", 25.0)),
            preview_width=_get_int("AIVD_PREVIEW_WIDTH", 480),
            monitor_index=_get_int("AIVD_MONITOR_INDEX", 1),
            ocr_enabled=_get_bool("AIVD_OCR_ENABLED", True),
            ocr_lang=_get("AIVD_OCR_LANG", "eng"),
            ocr_max_width=_get_int("AIVD_OCR_MAX_WIDTH", 1600),
            ocr_change_threshold=_get_float("AIVD_OCR_CHANGE_THRESHOLD", 6.0),
            tesseract_cmd=_get("AIVD_TESSERACT_CMD", None) or _detect_tesseract(),
        )

    @property
    def ai_enabled(self) -> bool:
        """True, wenn ein API-Key gesetzt ist (LLM statt Heuristik)."""
        return bool(self.anthropic_api_key)
