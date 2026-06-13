"""AI Vision Dashboard – Einstiegspunkt.

Verwendung:

    python main.py dashboard      # startet das Web-Dashboard (Streamlit)
    python main.py track          # headless im Terminal tracken (Strg+C zum Stoppen)

Optionen für "track":
    --duration N      Sekunden tracken und dann automatisch beenden
    --no-ai           erzwingt den heuristischen Modus (kein LLM-Aufruf)
    --interval N      Sekunden zwischen Screenshots (überschreibt .env)
    --export PFAD     beim Beenden Daten als CSV speichern
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_dashboard() -> int:
    """Startet das Streamlit-Dashboard als Unterprozess."""
    app_path = ROOT / "dashboard" / "app.py"
    print("🚀 Starte AI Vision Dashboard …  (Beenden mit Strg+C)")
    try:
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app_path)])
    except FileNotFoundError:
        print("❌ Streamlit nicht gefunden. Bitte zuerst:  pip install -r requirements.txt")
        return 1
    except KeyboardInterrupt:
        return 0


def run_track(args: argparse.Namespace) -> int:
    """Headless-Tracking im Terminal mit Live-Status."""
    from core.config import Config
    from core.engine import TrackingEngine
    from core.metrics import format_duration

    config = Config.from_env()
    if args.no_ai:
        config.anthropic_api_key = ""  # erzwingt Heuristik
    if args.interval:
        config.capture_interval = max(0.25, args.interval)

    engine = TrackingEngine(config)
    mode = f"Claude ({config.model})" if config.ai_enabled else "Heuristik"
    print(f"🧠 AI Vision Dashboard – Tracking gestartet | Modus: {mode} | "
          f"OCR: {'an' if engine.ocr.available else 'aus'}")
    print("   Strg+C zum Beenden.\n")

    engine.start()
    start = time.time()
    try:
        while True:
            time.sleep(2.0)
            snap = engine.snapshot()
            mt = snap["metrics"]
            now = datetime.now().strftime("%H:%M:%S")
            print(
                f"[{now}] {snap['current_app'][:22]:<22} | {snap['current_category']:<14} | "
                f"Fokus {int(round(mt['focus_score'])):3d}/100 | "
                f"Fokus {format_duration(mt['focus_seconds'])} / Ablenkung {format_duration(mt['distraction_seconds'])}"
            )
            print(f"          🤖 {snap['ai_description']}")
            if args.duration and (time.time() - start) >= args.duration:
                break
    except KeyboardInterrupt:
        print("\n⏹  Beende …")
    finally:
        engine.stop()

    if args.export:
        engine.export_csv(args.export)
        print(f"💾 Daten exportiert nach: {args.export}")
    print("✅ Fertig.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-vision-dashboard",
        description="AI Vision Dashboard – analysiert Bildschirm & Nutzungsverhalten in Echtzeit.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("dashboard", help="Web-Dashboard (Streamlit) starten")

    track = sub.add_parser("track", help="Headless im Terminal tracken")
    track.add_argument("--duration", type=int, default=0, help="Sekunden tracken, dann beenden")
    track.add_argument("--no-ai", action="store_true", help="heuristischer Modus (kein LLM)")
    track.add_argument("--interval", type=float, default=0.0, help="Sekunden zwischen Screenshots")
    track.add_argument("--export", type=str, default="", help="CSV-Pfad für den Export beim Beenden")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "dashboard":
        return run_dashboard()
    if args.command == "track":
        return run_track(args)

    parser.print_help()
    print("\nTipp:  python main.py dashboard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
