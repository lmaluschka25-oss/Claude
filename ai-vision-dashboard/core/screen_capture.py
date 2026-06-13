"""Screen Capture.

Nimmt mit ``mss`` effizient Screenshots des Hauptbildschirms auf. Bilder werden
ausschließlich im RAM gehalten – nichts wird dauerhaft gespeichert. Zusätzlich
gibt es Hilfsfunktionen zum Herunterskalieren (Vorschau) und zur leichtgewichtigen
Änderungs-Erkennung (damit OCR nicht unnötig läuft → CPU sparen).
"""

from __future__ import annotations

import io
from typing import Optional

import mss
import numpy as np
from PIL import Image


class ScreenCapture:
    """Dünner Wrapper um ``mss`` mit pro-Thread wiederverwendetem Handle.

    Wichtig: ``mss`` ist nicht thread-sicher. Das Handle wird daher *lazy* in
    dem Thread erzeugt, der ``grab()`` zuerst aufruft (in unserem Fall der
    Tracking-Loop). ``close()`` gibt es wieder frei, sodass nach einem Neustart
    sauber im neuen Thread initialisiert wird.
    """

    def __init__(self, monitor_index: int = 1) -> None:
        self.monitor_index = monitor_index
        self._sct: Optional["mss.base.MSSBase"] = None
        self._monitor: Optional[dict] = None

    def _ensure(self) -> None:
        if self._sct is None:
            self._sct = mss.mss()
            monitors = self._sct.monitors  # [0] = alle, [1] = Hauptbildschirm
            idx = self.monitor_index
            if idx < 0 or idx >= len(monitors):
                idx = 1 if len(monitors) > 1 else 0
            self._monitor = monitors[idx]

    def grab(self) -> Image.Image:
        """Liefert den aktuellen Bildschirm als RGB-``PIL.Image``."""
        self._ensure()
        raw = self._sct.grab(self._monitor)
        # mss liefert BGRA; .rgb konvertiert direkt zu RGB-Bytes.
        return Image.frombytes("RGB", raw.size, raw.rgb)

    def close(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
            self._monitor = None


# --- Hilfsfunktionen -------------------------------------------------------

def downscale(img: Image.Image, max_width: int) -> Image.Image:
    """Skaliert ein Bild proportional herunter, falls es breiter als ``max_width`` ist."""
    if img.width <= max_width:
        return img
    ratio = max_width / float(img.width)
    new_size = (max_width, max(1, int(img.height * ratio)))
    return img.resize(new_size, Image.BILINEAR)


def to_preview_jpeg(img: Image.Image, width: int = 480, quality: int = 70) -> bytes:
    """Erzeugt eine kleine JPEG-Vorschau (Bytes) für das Dashboard."""
    preview = downscale(img, width)
    buf = io.BytesIO()
    preview.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def frame_signature(img: Image.Image, size: tuple[int, int] = (64, 64)) -> np.ndarray:
    """Kleiner Graustufen-Fingerabdruck für die Änderungs-Erkennung."""
    thumb = img.convert("L").resize(size, Image.BILINEAR)
    return np.asarray(thumb, dtype=np.float32)


def frames_differ(a: Optional[np.ndarray], b: np.ndarray, threshold: float) -> bool:
    """True, wenn sich zwei Fingerabdrücke deutlich genug unterscheiden."""
    if a is None or a.shape != b.shape:
        return True
    return float(np.mean(np.abs(a - b))) >= threshold
