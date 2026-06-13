"""Tracking-Engine.

Orchestriert den gesamten Ablauf in einem Hintergrund-Thread:

    Screenshot -> aktives Fenster -> (bei Änderung) OCR -> Keywords
                -> (gedrosselt) AI-Analyse -> Metriken -> geteilter Zustand

Der geteilte Zustand wird über ein Lock geschützt und vom Dashboard / CLI per
``snapshot()`` gelesen. Bilder bleiben ausschließlich im RAM.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Optional

from .ai_analyzer import build_analyzer
from .app_tracker import AppTracker
from .config import Config
from .metrics import MetricsTracker
from .ocr_engine import OCREngine
from .screen_capture import ScreenCapture, frame_signature, frames_differ, to_preview_jpeg


class TrackingEngine:
    """Steuert Start/Stop des Trackings und hält den Live-Zustand."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config.from_env()

        # Komponenten
        self.capture = ScreenCapture(self.config.monitor_index)
        self.tracker = AppTracker()
        self.ocr = OCREngine(
            tesseract_cmd=self.config.tesseract_cmd,
            lang=self.config.ocr_lang,
            max_width=self.config.ocr_max_width,
        )
        self.analyzer = build_analyzer(self.config)
        self.metrics = MetricsTracker(self.config)

        # Thread-Steuerung
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started_at: Optional[float] = None

        # Interner Loop-Zustand (nur im Loop-Thread benutzt)
        self._last_sig = None
        self._last_text = ""
        self._last_ai_ts = 0.0

        # Geteilter Zustand (Lock-geschützt)
        self._preview_jpeg: Optional[bytes] = None
        self._current_app = "—"
        self._current_title = ""
        self._current_category = "Unknown"
        self._ai_description = "Tracking noch nicht gestartet."
        self._ai_source = "heuristik"
        self._recent_apps: Deque[str] = deque(maxlen=8)
        self._last_keywords: list = []
        self._last_error: Optional[str] = None

    # --- Lebenszyklus ----------------------------------------------------

    def is_running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        if self.is_running():
            return
        self._running.set()
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._loop, name="aivd-tracking", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        # mss-Handle freigeben, damit ein Neustart sauber im neuen Thread initialisiert.
        self.capture.close()
        with self._lock:
            self._ai_description = "Tracking gestoppt."

    # --- Haupt-Loop ------------------------------------------------------

    def _loop(self) -> None:
        interval = self.config.capture_interval
        while self._running.is_set():
            t0 = time.time()
            try:
                self._tick()
            except Exception as exc:  # nie den Loop sterben lassen
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
            # Restzeit bis zum nächsten Intervall in kleinen Schritten warten,
            # damit Stop schnell greift (kein CPU-Spam durch busy-loop).
            deadline = t0 + interval
            while self._running.is_set() and time.time() < deadline:
                time.sleep(min(0.1, max(0.0, deadline - time.time())))

    def _tick(self) -> None:
        now = time.time()

        # 1) Screenshot + aktives Fenster
        img = self.capture.grab()
        window = self.tracker.active_window()
        app = window["app"]
        title = window["title"]

        # 2) Änderungs-Erkennung → OCR nur bei nennenswerter Veränderung (CPU sparen)
        sig = frame_signature(img)
        changed = frames_differ(self._last_sig, sig, self.config.ocr_change_threshold)
        self._last_sig = sig
        if self.config.ocr_enabled and changed:
            self._last_text = self.ocr.extract_text(img)
        keywords = self.ocr.keywords(self._last_text) if self._last_text else self._last_keywords

        # 3) Vorschau (klein, im RAM)
        preview = to_preview_jpeg(img, self.config.preview_width)

        # 4) "Recent Apps" pflegen
        if not self._recent_apps or self._recent_apps[-1] != app:
            self._recent_apps.append(app)
        recent = list(self._recent_apps)

        # 5) AI-Analyse gedrosselt (Kosten/Performance)
        result = None
        if (now - self._last_ai_ts) >= self.config.ai_interval or self._current_category == "Unknown":
            context: Dict = {
                "app": app,
                "title": title,
                "proc": window.get("proc", ""),
                "recent_apps": recent,
                "keywords": keywords,
            }
            result = self.analyzer.analyze(context)
            self._last_ai_ts = now

        # 6) Zustand & Metriken aktualisieren (Lock-geschützt)
        with self._lock:
            category = result.category if result else self._current_category
            self.metrics.record(self.config.capture_interval, app, category)

            self._preview_jpeg = preview
            self._current_app = app
            self._current_title = title
            self._current_category = category
            self._last_keywords = keywords
            if result:
                self._ai_description = result.description
                self._ai_source = result.source
            self._last_error = None

    # --- Auslesen --------------------------------------------------------

    def snapshot(self) -> dict:
        """Kompletter Live-Zustand für Dashboard / CLI."""
        with self._lock:
            return {
                "running": self.is_running(),
                "current_app": self._current_app,
                "current_title": self._current_title,
                "current_category": self._current_category,
                "ai_description": self._ai_description,
                "ai_source": self._ai_source,
                "ai_enabled": getattr(self.analyzer, "is_ai", False),
                "ocr_available": self.ocr.available,
                "model": self.config.model if getattr(self.analyzer, "is_ai", False) else "—",
                "recent_apps": list(self._recent_apps),
                "keywords": list(self._last_keywords)[:15],
                "preview_jpeg": self._preview_jpeg,
                "error": self._last_error,
                "uptime": (time.time() - self._started_at) if self._started_at else 0.0,
                "metrics": self.metrics.snapshot(),
            }

    # --- Export ----------------------------------------------------------

    def csv_string(self) -> str:
        with self._lock:
            return self.metrics.to_csv_string()

    def export_csv(self, path: str) -> None:
        with self._lock:
            self.metrics.to_csv(path)
