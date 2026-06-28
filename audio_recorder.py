#!/usr/bin/env python3
"""
🎙  Audio Recorder — deluxe edition
====================================

Ein kleiner, robuster Aufnahme-Player fürs Terminal. Aus dem ursprünglichen
„Zahl eingeben → aufnehmen → speichern → abspielen"-Skript wird ein echtes
Werkzeug:

    1) IMPORT      – saubere Imports, alles getypt und dokumentiert
    2) AUFNEHMEN   – feste Dauer ODER „bis Enter", mit Live-Pegelanzeige (VU)
    3) SPEICHERN   – Zeitstempel-Dateinamen (nichts wird überschrieben),
                     wählbares Format (wav / flac / ogg)
    4) ABSPIELEN   – jede gespeicherte Aufnahme wieder abspielen

Bedienung (Menü):
    <Zahl>     Sekunden aufnehmen (z. B. 5)
    <Enter>    aufnehmen, bis du erneut Enter drückst
    l          Aufnahmen auflisten
    p          letzte Aufnahme abspielen   ·   p 3  →  Aufnahme Nr. 3
    d          Audiogeräte anzeigen
    h          Hilfe
    stop / q   beenden

Start:
    python audio_recorder.py
    python audio_recorder.py --seconds 5          # direkt 5 s aufnehmen
    python audio_recorder.py --format flac --dir aufnahmen
    python audio_recorder.py --list-devices

Abhängigkeiten:  sounddevice · soundfile · numpy   (siehe requirements.txt)
"""

from __future__ import annotations

# ============================ 1) IMPORT ============================

import argparse
import queue
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
except ModuleNotFoundError as exc:  # pragma: no cover - freundlicher Hinweis
    missing = exc.name
    sys.exit(
        f"Fehlende Abhängigkeit: {missing!r}\n"
        "Bitte installieren mit:\n"
        "    pip install sounddevice soundfile numpy"
    )


# ============================ Konfiguration ============================

# Format -> (Dateiendung, Subtype für soundfile)
FORMATS: dict[str, tuple[str, str]] = {
    "wav": ("wav", "PCM_16"),
    "flac": ("flac", "PCM_16"),
    "ogg": ("ogg", "VORBIS"),
}


@dataclass
class Config:
    """Alle Einstellungen an einer Stelle."""

    samplerate: int = 48_000
    channels: int = 1
    input_device: int | None = None
    output_device: int | None = None
    out_dir: Path = Path("recordings")
    fmt: str = "wav"
    blocksize: int = 1024
    color: bool = True

    def __post_init__(self) -> None:
        if self.fmt not in FORMATS:
            raise ValueError(
                f"Unbekanntes Format {self.fmt!r}. "
                f"Erlaubt: {', '.join(FORMATS)}"
            )


# ============================ Terminal-Optik ============================


class Ansi:
    """Kleine ANSI-Farbhilfe — schaltet sich bei Bedarf selbst ab."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled and sys.stdout.isatty()

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def dim(self, t: str) -> str:
        return self._wrap("2", t)

    def bold(self, t: str) -> str:
        return self._wrap("1", t)

    def red(self, t: str) -> str:
        return self._wrap("91", t)

    def green(self, t: str) -> str:
        return self._wrap("92", t)

    def yellow(self, t: str) -> str:
        return self._wrap("93", t)

    def cyan(self, t: str) -> str:
        return self._wrap("96", t)


def frame(lines: list[str], width: int = 46) -> str:
    """Rahmt Textzeilen in eine hübsche Box (nur ASCII-breite Zeichen)."""
    top = "╔" + "═" * width + "╗"
    bottom = "╚" + "═" * width + "╝"
    body = [f"║ {line:<{width - 2}} ║" for line in lines]
    return "\n".join([top, *body, bottom])


HERO = r"""
   ___       _   _        ___                       _
  / _ \ _  _| |_(_)___   | _ \___ __ ___ _ _ __  ___| |_
 | (_) | || |  _| / _ \  |   / -_) _/ _ \ '_/ _` / -_)  _|
  \__/_\\_,_|\__|_\___/  |_|_\___\__\___/_| \__,_\___|\__|
""".rstrip("\n")


# ============================ Recorder-Kern ============================


class Recorder:
    """Nimmt auf, speichert und spielt ab — mit Live-Pegelanzeige."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.c = Ansi(cfg.color)

    # ---------- 2) AUFNEHMEN ----------

    def _capture(self, stop_when) -> np.ndarray:
        """Liest Audio blockweise ein, bis ``stop_when(elapsed)`` True ist.

        ``stop_when`` bekommt die verstrichene Zeit in Sekunden und gibt
        zurück, ob gestoppt werden soll. Währenddessen läuft eine VU-Anzeige.
        """
        frames: list[np.ndarray] = []
        q: queue.Queue[np.ndarray] = queue.Queue()
        clipped = False

        def callback(indata, _frames, _time, status) -> None:
            if status:
                # z. B. Input-Overflow — nicht fatal, nur vermerken
                sys.stderr.write(f"\n{self.c.yellow('⚠ ' + str(status))}\n")
            q.put(indata.copy())

        try:
            with sd.InputStream(
                samplerate=self.cfg.samplerate,
                channels=self.cfg.channels,
                device=self.cfg.input_device,
                blocksize=self.cfg.blocksize,
                dtype="float32",
                callback=callback,
            ):
                start = time.monotonic()
                while True:
                    elapsed = time.monotonic() - start
                    if stop_when(elapsed):
                        break
                    try:
                        block = q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    frames.append(block)
                    if float(np.max(np.abs(block))) >= 0.999:
                        clipped = True
                    self._draw_meter(block, elapsed)
        except KeyboardInterrupt:
            print(self.c.yellow("\n  ⏹  Aufnahme abgebrochen."))
        finally:
            sys.stdout.write("\r" + " " * 70 + "\r")
            sys.stdout.flush()

        if clipped:
            print(self.c.yellow("  ⚠  Übersteuert (Clipping) — etwas leiser aufnehmen."))

        if not frames:
            return np.empty((0, self.cfg.channels), dtype="float32")
        return np.concatenate(frames, axis=0)

    def record_fixed(self, seconds: float) -> np.ndarray:
        """Nimmt genau ``seconds`` Sekunden auf."""
        print(self.c.red(f"  ● REC  ·  {seconds:g}s  (Strg+C bricht ab)"))
        return self._capture(lambda elapsed: elapsed >= seconds)

    def record_until_enter(self) -> np.ndarray:
        """Nimmt auf, bis der Nutzer Enter drückt (oder Strg+C)."""
        print(self.c.red("  ● REC  ·  Enter drücken zum Stoppen"))
        stop = threading.Event()

        def waiter() -> None:
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass
            stop.set()

        threading.Thread(target=waiter, daemon=True).start()
        return self._capture(lambda _elapsed: stop.is_set())

    def _draw_meter(self, block: np.ndarray, elapsed: float) -> None:
        """Zeichnet eine einfache VU-Anzeige (Spitzenpegel) auf eine Zeile."""
        peak = float(np.max(np.abs(block)))
        bar_len = 28
        filled = min(bar_len, int(peak * bar_len * 1.6))
        if peak < 0.4:
            color = self.c.green
        elif peak < 0.8:
            color = self.c.yellow
        else:
            color = self.c.red
        bar = color("█" * filled) + self.c.dim("·" * (bar_len - filled))
        sys.stdout.write(f"\r  {elapsed:5.1f}s │{bar}│ {peak:4.2f} ")
        sys.stdout.flush()

    # ---------- 3) SPEICHERN ----------

    def save(self, audio: np.ndarray) -> Path | None:
        """Speichert mit Zeitstempel-Namen. Gibt den Pfad zurück (oder None)."""
        if audio.size == 0:
            print(self.c.yellow("  Nichts aufgenommen — nichts gespeichert."))
            return None

        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        ext, subtype = FORMATS[self.cfg.fmt]
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = self.cfg.out_dir / f"aufnahme_{ts}.{ext}"

        sf.write(path, audio, self.cfg.samplerate, subtype=subtype)

        secs = len(audio) / self.cfg.samplerate
        kb = path.stat().st_size / 1024
        print(self.c.green(f"  ✓ gespeichert: {path}  ({secs:.1f}s · {kb:.0f} KB)"))
        return path

    # ---------- 4) ABSPIELEN ----------

    def play(self, path: Path) -> None:
        """Spielt eine Audiodatei ab."""
        if not path.exists():
            print(self.c.red(f"  ✗ Datei nicht gefunden: {path}"))
            return
        try:
            data, sr = sf.read(path, dtype="float32")
            print(self.c.cyan(f"  ▶ {path.name}"))
            sd.play(data, sr, device=self.cfg.output_device)
            sd.wait()
            print(self.c.green("  ✓ fertig."))
        except KeyboardInterrupt:
            sd.stop()
            print(self.c.yellow("\n  ⏹  Wiedergabe gestoppt."))

    # ---------- Hilfsfunktionen ----------

    def recordings(self) -> list[Path]:
        """Alle gespeicherten Aufnahmen, neueste zuletzt."""
        if not self.cfg.out_dir.exists():
            return []
        exts = {f".{e}" for e, _ in FORMATS.values()}
        files = [p for p in self.cfg.out_dir.iterdir() if p.suffix in exts]
        return sorted(files, key=lambda p: p.stat().st_mtime)

    def list_recordings(self) -> None:
        files = self.recordings()
        if not files:
            print(self.c.dim("  (noch keine Aufnahmen)"))
            return
        print(self.c.bold(f"  Aufnahmen in {self.cfg.out_dir}/:"))
        for i, p in enumerate(files, 1):
            try:
                info = sf.info(p)
                meta = f"{info.duration:5.1f}s · {info.samplerate} Hz"
            except Exception:
                meta = "?"
            kb = p.stat().st_size / 1024
            print(f"   {i:>2}. {p.name:<32} {meta} · {kb:5.0f} KB")


# ============================ Geräte ============================


def list_devices() -> None:
    """Listet verfügbare Audiogeräte auf."""
    print(sd.query_devices())
    try:
        default_in, default_out = sd.default.device
        print(f"\nStandard:  Eingang #{default_in}  ·  Ausgang #{default_out}")
    except Exception:
        pass


# ============================ Menü / REPL ============================


def run_menu(rec: Recorder) -> None:
    c = rec.c
    print(c.cyan(HERO))
    print(
        frame(
            [
                "<Zahl>   Sekunden aufnehmen      l   Aufnahmen auflisten",
                "<Enter>  aufnehmen bis Enter     p   abspielen (p <n>)",
                "d        Geräte anzeigen         h   Hilfe",
                "stop/q   beenden",
            ]
        )
    )

    while True:
        try:
            raw = input(c.bold("\n  ➜  ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        cmd = raw.lower()

        if cmd in {"stop", "q", "quit", "exit"}:
            break

        if cmd in {"h", "help", "?"}:
            print(
                "  <Zahl> aufnehmen · <Enter> bis-Enter · l listen · "
                "p[ n] abspielen · d Geräte · stop beenden"
            )
            continue

        if cmd == "d":
            list_devices()
            continue

        if cmd == "l":
            rec.list_recordings()
            continue

        if cmd.startswith("p"):
            files = rec.recordings()
            if not files:
                print(c.dim("  (noch keine Aufnahmen)"))
                continue
            rest = raw[1:].strip()
            if rest:
                if not rest.isdigit() or not (1 <= int(rest) <= len(files)):
                    print(c.red(f"  ✗ Bitte 'p 1'..'p {len(files)}'."))
                    continue
                rec.play(files[int(rest) - 1])
            else:
                rec.play(files[-1])  # letzte
            continue

        # Aufnehmen ----------------------------------------------------
        if raw == "":
            audio = rec.record_until_enter()
            rec.save(audio)
            continue

        if raw.isdigit():
            seconds = int(raw)
            if seconds <= 0:
                print(c.red("  ✗ Bitte eine Zahl größer als 0."))
                continue
            audio = rec.record_fixed(seconds)
            rec.save(audio)
            continue

        print(c.red("  ✗ Keine Zahl. Tipp: 'h' für Hilfe."))

    print(c.cyan("\n  ╭─────────────╮\n  │  Abbruch.   │\n  ╰─────────────╯\n"))


# ============================ CLI ============================


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="🎙  Audio Recorder — aufnehmen, speichern, abspielen.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--seconds", type=float, default=None,
                   help="Direkt N Sekunden aufnehmen und beenden")
    p.add_argument("--samplerate", type=int, default=48_000, help="Abtastrate (Hz)")
    p.add_argument("--channels", type=int, default=1, help="Kanäle (1=mono, 2=stereo)")
    p.add_argument("--input-device", type=int, default=None, help="Index Eingabegerät")
    p.add_argument("--output-device", type=int, default=None, help="Index Ausgabegerät")
    p.add_argument("--dir", type=Path, default=Path("recordings"),
                   help="Zielordner für Aufnahmen")
    p.add_argument("--format", choices=list(FORMATS), default="wav",
                   help="Speicherformat")
    p.add_argument("--no-color", action="store_true", help="Farben deaktivieren")
    p.add_argument("--list-devices", action="store_true",
                   help="Audiogeräte auflisten und beenden")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.list_devices:
        list_devices()
        return 0

    cfg = Config(
        samplerate=args.samplerate,
        channels=args.channels,
        input_device=args.input_device,
        output_device=args.output_device,
        out_dir=args.dir,
        fmt=args.format,
        color=not args.no_color,
    )
    rec = Recorder(cfg)

    # Direktmodus: aufnehmen, speichern, abspielen, fertig.
    if args.seconds is not None:
        if args.seconds <= 0:
            print("--seconds muss größer als 0 sein.", file=sys.stderr)
            return 2
        audio = rec.record_fixed(args.seconds)
        path = rec.save(audio)
        if path:
            rec.play(path)
        return 0

    run_menu(rec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
