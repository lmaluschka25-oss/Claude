"""AI Interpretation Layer.

Wandelt kompakte Metadaten (aktive App, letzte Apps, OCR-Schlüsselwörter) in eine
strukturierte Aktivitäts-Einschätzung um. Es werden **niemals Rohbilder** an die
AI gesendet – nur Text + Metadaten, kompakt und damit günstig.

Zwei Implementierungen mit identischer Schnittstelle:

* ``ClaudeAnalyzer``    – nutzt die Claude API (strukturiertes JSON).
* ``HeuristicAnalyzer`` – regelbasiert, ohne API-Key lauffähig (Fallback).

``build_analyzer(config)`` wählt automatisch die passende Variante.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List

from .config import CATEGORIES, FOCUS_WEIGHTS, Config


@dataclass
class AnalysisResult:
    """Strukturiertes Ergebnis einer Aktivitäts-Analyse."""

    category: str
    description: str
    focus: int          # 0–100 Einschätzung des Analyzers
    distracted: bool
    source: str         # "ai" | "heuristik"


# --- Heuristik (Prozess-/Keyword-basiert) ---------------------------------

_CODING_PROCS = {
    "code", "devenv", "pycharm", "pycharm64", "idea64", "webstorm64", "rider64",
    "clion64", "goland64", "studio64", "sublime_text", "notepad++", "windowsterminal",
    "wt", "cmd", "powershell", "pwsh", "gvim", "vim",
}
_BROWSER_PROCS = {
    "chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "iexplore",
}
_GAME_PROCS = {
    "steam", "steamwebhelper", "epicgameslauncher", "leagueclient", "leagueclientux",
    "valorant-win64-shipping", "csgo", "cs2", "dota2", "minecraft",
}
_VIDEO_PROCS = {"vlc", "mpv", "potplayermini64", "wmplayer", "mpc-hc64", "mpc-hc"}
_MSG_PROCS = {
    "discord", "slack", "teams", "ms-teams", "telegram", "whatsapp", "signal",
    "skype", "outlook", "thunderbird",
}

_VIDEO_KEYWORDS = {"youtube", "netflix", "twitch", "primevideo", "disney", "video", "stream"}
_MSG_KEYWORDS = {"whatsapp", "messenger", "discord", "chat", "inbox", "gmail", "posteingang"}
_CODING_KEYWORDS = {
    "github", "gitlab", "stackoverflow", "localhost", "python", "javascript",
    "function", "import", "def", "class", "const", "error", "traceback", "docs",
}


def _describe(category: str, app: str) -> str:
    """Kurze, menschliche Beschreibung pro Kategorie (Deutsch)."""
    templates = {
        "Coding": f"Du arbeitest konzentriert an Code in {app}.",
        "Browsing": f"Du surfst gerade im Web ({app}).",
        "Gaming": f"Du spielst gerade ({app}).",
        "Watching Video": f"Du schaust ein Video in {app}.",
        "Messaging": f"Du chattest / kommunizierst in {app}.",
        "Unknown": f"Aktivität in {app} – noch nicht eindeutig.",
    }
    return templates.get(category, templates["Unknown"])


class HeuristicAnalyzer:
    """Regelbasierte Klassifizierung ohne LLM."""

    is_ai = False

    def analyze(self, context: Dict) -> AnalysisResult:
        proc = (context.get("proc") or "").lower()
        title = (context.get("title") or "").lower()
        app = context.get("app") or "der App"
        keywords = set(context.get("keywords") or [])
        haystack = title + " " + " ".join(keywords)

        category = "Unknown"
        if proc in _CODING_PROCS:
            category = "Coding"
        elif proc in _GAME_PROCS:
            category = "Gaming"
        elif proc in _VIDEO_PROCS:
            category = "Watching Video"
        elif proc in _MSG_PROCS:
            category = "Messaging"
        elif proc in _BROWSER_PROCS:
            # Im Browser anhand von Titel/Keywords feiner unterscheiden.
            if any(k in haystack for k in _VIDEO_KEYWORDS):
                category = "Watching Video"
            elif any(k in haystack for k in _MSG_KEYWORDS):
                category = "Messaging"
            elif any(k in haystack for k in _CODING_KEYWORDS):
                category = "Coding"
            else:
                category = "Browsing"
        else:
            # Ohne Prozessinfo: nur über Keywords schätzen.
            if any(k in haystack for k in _CODING_KEYWORDS):
                category = "Coding"
            elif any(k in haystack for k in _VIDEO_KEYWORDS):
                category = "Watching Video"
            elif any(k in haystack for k in _MSG_KEYWORDS):
                category = "Messaging"

        focus = FOCUS_WEIGHTS.get(category, 50)
        return AnalysisResult(
            category=category,
            description=_describe(category, app),
            focus=focus,
            distracted=focus < 50,
            source="heuristik",
        )


# --- Claude-basierte Analyse ----------------------------------------------

_SYSTEM_PROMPT = (
    "Du bist ein Aktivitaets-Analyst. Du bekommst kompakte Metadaten ueber die "
    "aktuelle Bildschirmnutzung (aktive App, Fenstertitel, zuletzt genutzte Apps "
    "und Schluesselwoerter aus OCR). Ordne die Aktivitaet GENAU einer Kategorie zu: "
    "Coding, Browsing, Gaming, Watching Video, Messaging, Unknown. "
    "Antworte AUSSCHLIESSLICH mit kompaktem JSON, ohne Markdown, ohne Text drumherum. "
    'Schema: {"category": <eine Kategorie>, "description": <max 12 Woerter, Deutsch, '
    'was der Nutzer gerade tut>, "focus": <0-100 Integer wie produktiv/fokussiert>, '
    '"distracted": <true|false>}'
)


def _build_user_prompt(context: Dict) -> str:
    recent = ", ".join(context.get("recent_apps") or []) or "—"
    keywords = ", ".join((context.get("keywords") or [])[:25]) or "—"
    title = (context.get("title") or "").strip()[:160] or "—"
    return (
        f"Aktive App: {context.get('app', '—')}\n"
        f"Fenstertitel: {title}\n"
        f"Letzte Apps: {recent}\n"
        f"Schluesselwoerter: {keywords}"
    )


def _normalize_category(value: object) -> str:
    if not isinstance(value, str):
        return "Unknown"
    value = value.strip().lower()
    for cat in CATEGORIES:
        if cat.lower() == value:
            return cat
    return "Unknown"


def _extract_json(text: str) -> Dict:
    """Holt das erste JSON-Objekt robust aus einer Antwort."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class ClaudeAnalyzer:
    """Analyse via Claude API mit automatischem Heuristik-Fallback bei Fehlern."""

    is_ai = True

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic  # lokal importiert, damit das Paket nur bei Bedarf nötig ist

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._fallback = HeuristicAnalyzer()

    def analyze(self, context: Dict) -> AnalysisResult:
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_prompt(context)}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", "") == "text"
            )
            data = _extract_json(text)
            if not data:
                return self._fallback.analyze(context)

            category = _normalize_category(data.get("category"))
            description = str(data.get("description") or _describe(category, context.get("app", "der App")))
            try:
                focus = int(data.get("focus", FOCUS_WEIGHTS.get(category, 50)))
            except (TypeError, ValueError):
                focus = FOCUS_WEIGHTS.get(category, 50)
            focus = max(0, min(100, focus))
            distracted = bool(data.get("distracted", focus < 50))

            return AnalysisResult(
                category=category,
                description=description[:140],
                focus=focus,
                distracted=distracted,
                source="ai",
            )
        except Exception:
            # Netzwerkfehler, Rate-Limit, ungültige Antwort … – nie das Tracking blockieren.
            return self._fallback.analyze(context)


def build_analyzer(config: Config):
    """Wählt den passenden Analyzer (Claude wenn API-Key vorhanden, sonst Heuristik)."""
    if config.ai_enabled:
        try:
            return ClaudeAnalyzer(config.anthropic_api_key, config.model)
        except Exception:
            # z. B. anthropic nicht installiert → sauberer Fallback
            return HeuristicAnalyzer()
    return HeuristicAnalyzer()
