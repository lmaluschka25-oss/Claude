"""OCR-Texterkennung.

Extrahiert relevanten Text aus Screenshots mit ``pytesseract``. Es wird bewusst
nur "sauberer" Text behalten (kein Müll), und aus dem Text werden Schlüsselwörter
abgeleitet, die später kompakt an die AI gehen – niemals das Rohbild.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

import pytesseract
from PIL import Image

from .screen_capture import downscale

# Häufige Stoppwörter (DE + EN), die als Schlüsselwörter nichts aussagen.
_STOPWORDS = {
    # Englisch
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can", "her",
    "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "man",
    "new", "now", "old", "see", "two", "way", "who", "boy", "did", "its", "let",
    "put", "say", "she", "too", "use", "with", "this", "that", "from", "have",
    "your", "what", "when", "your", "will", "more", "they", "here", "than",
    # Deutsch
    "und", "der", "die", "das", "den", "dem", "ein", "eine", "mit", "von", "fuer",
    "ist", "sind", "auf", "aus", "bei", "war", "auch", "nicht", "sich", "noch",
    "wie", "wir", "ihr", "ich", "sie", "man", "nur", "oder", "aber", "dann",
    # generischer UI-Lärm
    "http", "https", "www", "com", "html", "file", "edit", "view", "help",
}


def _detect_available(cmd: Optional[str]) -> bool:
    """Prüft, ob Tesseract verfügbar ist (gesetzt + ausführbar)."""
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _clean_text(raw: str) -> str:
    """Macht aus rohem OCR-Output kompakten, sinnvollen Text."""
    lines: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if len(line) < 3:
            continue
        letters = sum(ch.isalnum() for ch in line)
        # Zeilen mit überwiegend Symbolen/Rauschen verwerfen.
        if letters < max(3, len(line) * 0.5):
            continue
        lines.append(line)

    # Deduplizieren, Reihenfolge erhalten.
    seen = set()
    unique = []
    for line in lines:
        key = line.lower()
        if key not in seen:
            seen.add(key)
            unique.append(line)

    text = "\n".join(unique)
    return text[:4000]  # harte Obergrenze gegen Ausreißer


class OCREngine:
    """OCR mit Vorverarbeitung, Cleaning und Keyword-Extraktion."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        lang: str = "eng",
        max_width: int = 1600,
    ) -> None:
        self.lang = lang
        self.max_width = max_width
        self.available = _detect_available(tesseract_cmd)

    def extract_text(self, img: Image.Image) -> str:
        """Extrahiert bereinigten Text aus einem Bild (leerer String bei Problemen)."""
        if not self.available:
            return ""
        try:
            small = downscale(img, self.max_width).convert("L")
            raw = pytesseract.image_to_string(small, lang=self.lang)
            return _clean_text(raw)
        except Exception:
            # Bewusst still: eine kaputte OCR darf das Tracking nicht stoppen.
            return ""

    def keywords(self, text: str, top: int = 25) -> List[str]:
        """Leitet die häufigsten aussagekräftigen Tokens aus einem Text ab."""
        if not text:
            return []
        tokens = re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9_]{2,}", text.lower())
        counter: Counter = Counter()
        for tok in tokens:
            if tok in _STOPWORDS or tok.isdigit():
                continue
            counter[tok] += 1
        return [word for word, _ in counter.most_common(top)]
