"""Optical character recognition for HUD text: timer, scoreboard, killfeed.

Backends are optional and lazily imported. If none is available (or
``VVC_OCR_BACKEND=off``), the engine degrades gracefully to no-ops so the rest
of the pipeline keeps working. All regions are expressed as fractions of the
frame so they adapt to any resolution.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..logging_config import get_logger

logger = get_logger(__name__)

# HUD regions as (x, y, w, h) fractions of the frame. Tuned for a standard
# 16:9 Valorant layout; override if your HUD scale differs.
REGION_TIMER = (0.46, 0.02, 0.08, 0.05)
REGION_SCORE = (0.40, 0.02, 0.20, 0.05)
REGION_KILLFEED = (0.70, 0.10, 0.29, 0.30)

_TIMER_RE = re.compile(r"(\d{1,2})[:.](\d{2})")
_SCORE_RE = re.compile(r"(\d{1,2})\D{1,3}(\d{1,2})")


@dataclass
class KillfeedLine:
    killer: str | None
    victim: str | None
    weapon: str | None
    headshot: bool


def crop_fractional(frame: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    h, w = frame.shape[:2]
    x, y, rw, rh = region
    x0, y0 = int(x * w), int(y * h)
    x1, y1 = int((x + rw) * w), int((y + rh) * h)
    return frame[max(y0, 0):y1, max(x0, 0):x1]


class OcrEngine:
    """Thin wrapper over an optional OCR backend."""

    def __init__(self, backend: str = "easyocr") -> None:
        self.backend = backend.lower()
        self._reader = None
        self.ready = False
        if self.backend != "off":
            self._init_backend()

    def _init_backend(self) -> None:
        if self.backend == "easyocr":
            try:
                import easyocr  # lazy import

                self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
                self.ready = True
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("easyocr unavailable (%s); OCR disabled.", exc)
        elif self.backend == "tesseract":
            try:
                import pytesseract  # noqa: F401

                self._reader = "tesseract"
                self.ready = True
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("pytesseract unavailable (%s); OCR disabled.", exc)
        else:
            logger.warning("Unknown OCR backend %r; OCR disabled.", self.backend)

    def read_text(self, image: np.ndarray) -> list[str]:
        if not self.ready or image.size == 0:
            return []
        try:
            if self.backend == "easyocr":
                return [str(t) for t in self._reader.readtext(image, detail=0)]
            if self.backend == "tesseract":
                import pytesseract

                text = pytesseract.image_to_string(image)
                return [line for line in text.splitlines() if line.strip()]
        except Exception as exc:  # pragma: no cover - runtime dependent
            logger.debug("OCR read failed: %s", exc)
        return []

    # ---- HUD-specific parsers -------------------------------------------
    def read_timer(self, frame: np.ndarray) -> float | None:
        """Return round time remaining in seconds, if legible."""
        for token in self.read_text(crop_fractional(frame, REGION_TIMER)):
            m = _TIMER_RE.search(token)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
        return None

    def read_score(self, frame: np.ndarray) -> str | None:
        """Return a normalized ``"A-B"`` score string, if legible."""
        for token in self.read_text(crop_fractional(frame, REGION_SCORE)):
            m = _SCORE_RE.search(token.replace(" ", ""))
            if m:
                return f"{m.group(1)}-{m.group(2)}"
        return None

    def read_killfeed(self, frame: np.ndarray) -> list[KillfeedLine]:
        """Best-effort parse of killfeed lines: ``KILLER weapon VICTIM``."""
        lines: list[KillfeedLine] = []
        for token in self.read_text(crop_fractional(frame, REGION_KILLFEED)):
            parts = [p for p in token.split() if p]
            if len(parts) < 2:
                continue
            lines.append(
                KillfeedLine(
                    killer=parts[0],
                    victim=parts[-1],
                    weapon=parts[1] if len(parts) > 2 else None,
                    headshot="headshot" in token.lower() or "hs" in [p.lower() for p in parts],
                )
            )
        return lines
