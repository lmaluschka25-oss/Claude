"""App-/Fenster-Erkennung.

Ermittelt das aktuell aktive Fenster über die Windows-API (pywin32) und den
Prozessnamen (psutil). Außerhalb von Windows wird ein neutraler Fallback
geliefert, damit das Projekt auch zu Entwicklungszwecken importierbar bleibt.
"""

from __future__ import annotations

from typing import Dict

# Windows-spezifische Imports defensiv kapseln.
try:  # pragma: no cover - plattformabhängig
    import win32gui
    import win32process

    _HAS_WIN32 = True
except Exception:  # pragma: no cover
    _HAS_WIN32 = False

try:
    import psutil

    _HAS_PSUTIL = True
except Exception:  # pragma: no cover
    _HAS_PSUTIL = False


# Prozessname (ohne ".exe", klein) -> schöner Anzeigename.
FRIENDLY_NAMES = {
    "chrome": "Google Chrome",
    "msedge": "Microsoft Edge",
    "firefox": "Firefox",
    "brave": "Brave",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
    "iexplore": "Internet Explorer",
    "code": "VS Code",
    "devenv": "Visual Studio",
    "pycharm64": "PyCharm",
    "pycharm": "PyCharm",
    "idea64": "IntelliJ IDEA",
    "webstorm64": "WebStorm",
    "rider64": "Rider",
    "clion64": "CLion",
    "goland64": "GoLand",
    "studio64": "Android Studio",
    "sublime_text": "Sublime Text",
    "notepad++": "Notepad++",
    "notepad": "Editor",
    "windowsterminal": "Windows Terminal",
    "wt": "Windows Terminal",
    "cmd": "Eingabeaufforderung",
    "powershell": "PowerShell",
    "pwsh": "PowerShell",
    "discord": "Discord",
    "slack": "Slack",
    "teams": "Microsoft Teams",
    "ms-teams": "Microsoft Teams",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "signal": "Signal",
    "skype": "Skype",
    "outlook": "Outlook",
    "thunderbird": "Thunderbird",
    "steam": "Steam",
    "steamwebhelper": "Steam",
    "epicgameslauncher": "Epic Games",
    "valorant-win64-shipping": "VALORANT",
    "leagueclient": "League of Legends",
    "leagueclientux": "League of Legends",
    "csgo": "Counter-Strike",
    "cs2": "Counter-Strike 2",
    "dota2": "Dota 2",
    "minecraft": "Minecraft",
    "vlc": "VLC",
    "mpv": "mpv",
    "potplayermini64": "PotPlayer",
    "wmplayer": "Windows Media Player",
    "spotify": "Spotify",
    "explorer": "Explorer",
    "obs64": "OBS Studio",
    "photoshop": "Photoshop",
    "excel": "Excel",
    "winword": "Word",
    "powerpnt": "PowerPoint",
    "acrobat": "Acrobat",
    "acrord32": "Adobe Reader",
}


def _friendly(proc_base: str) -> str:
    if not proc_base:
        return "Unbekannt"
    if proc_base in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[proc_base]
    # Fallback: ".exe" entfernen, hübsch machen.
    return proc_base.replace("-", " ").replace("_", " ").title()


class AppTracker:
    """Liefert Infos zum aktiven Fenster."""

    def active_window(self) -> Dict[str, str]:
        """Gibt ``{"app", "title", "proc"}`` für das aktive Fenster zurück.

        - ``app``   : schöner Anzeigename (z. B. "VS Code")
        - ``title`` : Fenstertitel
        - ``proc``  : Prozess-Basisname ohne ".exe" (z. B. "code")
        """
        if _HAS_WIN32:
            return self._active_window_windows()
        return {"app": "Unbekannt", "title": "", "proc": ""}

    def _active_window_windows(self) -> Dict[str, str]:  # pragma: no cover - Windows
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return {"app": "Unbekannt", "title": "", "proc": ""}

        proc_base = ""
        if _HAS_PSUTIL:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid:
                    name = psutil.Process(pid).name()  # z. B. "chrome.exe"
                    proc_base = name.lower()
                    if proc_base.endswith(".exe"):
                        proc_base = proc_base[:-4]
            except Exception:
                proc_base = ""

        app = _friendly(proc_base) if proc_base else (title.split(" - ")[-1].strip() or "Unbekannt")
        return {"app": app, "title": title, "proc": proc_base}
