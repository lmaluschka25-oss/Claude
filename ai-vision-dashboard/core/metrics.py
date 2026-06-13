"""Analytics & Metriken.

Aggregiert die Tracking-Daten zu auswertbaren Kennzahlen:

* Fokuszeit vs. Ablenkungszeit
* App-Nutzung (gesamt) und App-/Kategorie-Nutzung pro Stunde
* gleitender Fokus-Score (0–100) inkl. Strafe für häufiges App-Wechseln
* eine Aktivitäts-Timeline (zusammenhängende Segmente)
* CSV-Export

Der Zugriff wird vom ``TrackingEngine`` serialisiert (ein Lock), daher kommt
diese Klasse selbst ohne Lock aus.
"""

from __future__ import annotations

import csv
import io
import time
from collections import Counter, deque
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

from .config import FOCUS_WEIGHTS, Config


def format_duration(seconds: float) -> str:
    """Formatiert Sekunden als ``1h 23m`` / ``5m 12s`` / ``42s``."""
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class MetricsTracker:
    """Sammelt und verdichtet alle Tracking-Kennzahlen."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.reset()

    def reset(self) -> None:
        self.total_seconds = 0.0
        self.focus_seconds = 0.0
        self.distraction_seconds = 0.0
        self.focus_score = 50.0  # gleitender Mittelwert (EMA)

        self.app_usage: Counter = Counter()
        self.category_usage: Counter = Counter()
        # Stunde (0-23) -> {Kategorie -> Sekunden}
        self.per_hour: Dict[int, Counter] = {}

        self._samples: List[dict] = []
        self._segments: List[dict] = []

        # App-Wechsel-Verlauf (für Fokus-Strafe), nur letzte ~2 Minuten.
        self._app_events: Deque[Tuple[float, str]] = deque()
        self._last_app: Optional[str] = None

    # --- Aufzeichnung ----------------------------------------------------

    def _switch_penalty(self, now: float, app: str) -> float:
        """Abzug auf den Fokus, je nach App-Wechseln in der letzten Minute."""
        if app != self._last_app:
            self._app_events.append((now, app))
            self._last_app = app
        # Ereignisse älter als 60s verwerfen.
        cutoff = now - 60.0
        while self._app_events and self._app_events[0][0] < cutoff:
            self._app_events.popleft()
        switches = max(0, len(self._app_events) - 1)
        return min(self.config.max_switch_penalty, switches * self.config.switch_penalty_per)

    def record(self, dt: float, app: str, category: str) -> None:
        """Verbucht ein Tracking-Intervall von ``dt`` Sekunden."""
        now = time.time()
        weight = FOCUS_WEIGHTS.get(category, 50)
        penalty = self._switch_penalty(now, app)
        instant = max(0.0, min(100.0, weight - penalty))
        focused = instant >= self.config.focus_threshold

        # Summen
        self.total_seconds += dt
        self.app_usage[app] += dt
        self.category_usage[category] += dt
        if focused:
            self.focus_seconds += dt
        else:
            self.distraction_seconds += dt

        # Pro Stunde
        hour = datetime.now().hour
        self.per_hour.setdefault(hour, Counter())[category] += dt

        # Gleitender Fokus-Score
        alpha = self.config.focus_ema_alpha
        self.focus_score = alpha * instant + (1 - alpha) * self.focus_score

        # Sample
        ts = datetime.now()
        sample = {
            "ts": ts.isoformat(timespec="seconds"),
            "clock": ts.strftime("%H:%M:%S"),
            "app": app,
            "category": category,
            "instant_focus": round(instant, 1),
            "focus_score": round(self.focus_score, 1),
            "focused": focused,
        }
        self._samples.append(sample)
        if len(self._samples) > self.config.max_samples:
            # Älteste verwerfen (Speicher begrenzen).
            self._samples = self._samples[-self.config.max_samples :]

        # Timeline-Segmente (zusammenhängende gleiche App+Kategorie)
        if self._segments and self._segments[-1]["app"] == app and self._segments[-1]["category"] == category:
            seg = self._segments[-1]
            seg["end"] = sample["clock"]
            seg["seconds"] += dt
        else:
            self._segments.append(
                {"start": sample["clock"], "end": sample["clock"], "app": app, "category": category, "seconds": dt}
            )

    # --- Auswertung ------------------------------------------------------

    def focus_series(self, max_points: int = 240) -> List[dict]:
        """Gleitender Fokus-Score über die Zeit (für den Verlaufs-Chart)."""
        if not self._samples:
            return []
        step = max(1, len(self._samples) // max_points)
        return [
            {"Zeit": s["clock"], "Fokus": s["focus_score"]}
            for s in self._samples[::step]
        ]

    def top_apps(self, limit: int = 8) -> List[Tuple[str, float]]:
        return self.app_usage.most_common(limit)

    def recent_segments(self, limit: int = 12) -> List[dict]:
        return list(reversed(self._segments[-limit:]))

    def snapshot(self) -> dict:
        """Kompakter Zustand für das Dashboard."""
        return {
            "total_seconds": self.total_seconds,
            "focus_seconds": self.focus_seconds,
            "distraction_seconds": self.distraction_seconds,
            "focus_score": round(self.focus_score, 1),
            "app_usage": dict(self.app_usage),
            "category_usage": dict(self.category_usage),
            "per_hour": {h: dict(c) for h, c in sorted(self.per_hour.items())},
            "focus_series": self.focus_series(),
            "top_apps": self.top_apps(),
            "segments": self.recent_segments(),
            "sample_count": len(self._samples),
        }

    # --- Export ----------------------------------------------------------

    def to_csv_string(self) -> str:
        """Alle Samples als CSV-Text (für den Download-Button im Dashboard)."""
        buf = io.StringIO()
        fieldnames = ["ts", "app", "category", "instant_focus", "focus_score", "focused"]
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for sample in self._samples:
            writer.writerow(sample)
        return buf.getvalue()

    def to_csv(self, path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(self.to_csv_string())
