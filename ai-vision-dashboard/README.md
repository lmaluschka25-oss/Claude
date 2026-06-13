# 🧠 AI Vision Dashboard

Ein lokales Tool, das deinen **Windows-Bildschirm live analysiert** und dein
**Nutzungsverhalten** versteht. Es zeigt in einem Echtzeit-Dashboard, welche App
du nutzt, was auf dem Bildschirm passiert, wie fokussiert du bist – und liefert
eine AI-basierte Interpretation deiner aktuellen Tätigkeit.

> **Privacy first:** Screenshots bleiben ausschließlich im RAM und werden **nie**
> gespeichert. An die AI gehen **niemals Bilder**, sondern nur kompakte
> Metadaten (aktive App, ein paar Schlüsselwörter). Ohne API-Key läuft alles
> komplett offline im heuristischen Modus.

---

## ✨ Features

- **Screen Capture** – Screenshot des Hauptbildschirms (Standard: alle 1 s) via `mss`, nur im RAM.
- **App Detection** – aktives Fenster + Prozess über die Windows-API; App-Name, Zeit & Nutzungsdauer.
- **OCR** – relevanter Text via `pytesseract`; daraus werden kompakte Schlüsselwörter abgeleitet.
- **AI Interpretation** – Claude klassifiziert die Aktivität (`Coding`, `Browsing`, `Gaming`,
  `Watching Video`, `Messaging`) und liefert eine kurze, menschliche Beschreibung – als strukturiertes JSON.
- **Live Dashboard** – Dark-Mode, Auto-Refresh ohne Reload, Live-Vorschau, aktuelle App,
  AI-Status, Fokus-Score (0–100) und Start/Stop-Button.
- **Analytics** – Fokus- vs. Ablenkungszeit, App-Nutzung pro Stunde, Kategorien-Verteilung, Timeline.
- **CSV-Export** – alle Daten mit einem Klick exportieren.

---

## 🧱 Projektstruktur

```
ai-vision-dashboard/
├── core/
│   ├── config.py          # zentrale Konfiguration (.env / Umgebungsvariablen)
│   ├── screen_capture.py  # Screenshots (mss) + Vorschau + Änderungs-Erkennung
│   ├── app_tracker.py     # aktives Fenster / Prozess (Windows-API)
│   ├── ocr_engine.py      # OCR + Text-Cleaning + Keyword-Extraktion
│   ├── ai_analyzer.py     # Claude- & Heuristik-Analyzer (strukturiertes JSON)
│   ├── metrics.py         # Fokus-Score, Analytics, Timeline, CSV
│   └── engine.py          # orchestriert alles im Hintergrund-Thread
├── dashboard/
│   └── app.py             # Streamlit-Dashboard (UI)
├── main.py                # Einstiegspunkt (dashboard / track)
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Voraussetzungen

- **Windows 10/11**
- **Python 3.10+**
- **Tesseract OCR** (für die Texterkennung) – siehe Setup-Schritt 4
- Optional: ein **Claude API Key** für die echte AI-Analyse (sonst Heuristik)

---

## 🚀 Setup (Windows)

**1) Projekt holen & ins Verzeichnis wechseln**
```powershell
cd ai-vision-dashboard
```

**2) Virtuelle Umgebung anlegen & aktivieren**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**3) Abhängigkeiten installieren**
```powershell
pip install -r requirements.txt
```

**4) Tesseract OCR installieren**
- Installer (UB Mannheim Build): <https://github.com/UB-Mannheim/tesseract/wiki>
- Standardpfad `C:\Program Files\Tesseract-OCR\tesseract.exe` wird **automatisch** erkannt.
- Falls woanders installiert: in der `.env` `AIVD_TESSERACT_CMD` setzen.
- Deutsche Texterkennung: bei der Installation das Sprachpaket *German* mit auswählen
  und in der `.env` `AIVD_OCR_LANG=deu+eng` setzen.

**5) Konfiguration anlegen**
```powershell
copy .env.example .env
```
Dann in `.env` deinen `ANTHROPIC_API_KEY` eintragen (optional – ohne Key läuft die Heuristik).

**6) Starten** 🎉
```powershell
python main.py dashboard
```
Das Dashboard öffnet sich im Browser (Standard: <http://localhost:8501>).
Links auf **▶ Start** klicken.

---

## 🖥️ Nutzung

**Dashboard (empfohlen):**
```powershell
python main.py dashboard
```

**Headless im Terminal** (z. B. für Logging ohne UI):
```powershell
python main.py track                 # Strg+C zum Beenden
python main.py track --no-ai         # ohne LLM (nur Heuristik)
python main.py track --duration 60 --export daten.csv
```

---

## 🔧 Konfiguration (.env)

| Variable                    | Standard            | Beschreibung                                               |
|-----------------------------|---------------------|------------------------------------------------------------|
| `ANTHROPIC_API_KEY`         | –                   | Claude API Key. Leer = heuristischer Modus.                |
| `AIVD_MODEL`                | `claude-haiku-4-5`  | LLM-Modell. Für höhere Qualität: `claude-opus-4-8`.        |
| `AIVD_CAPTURE_INTERVAL`     | `1.0`               | Sekunden zwischen Screenshots.                             |
| `AIVD_AI_INTERVAL`          | `25`                | Sekunden zwischen LLM-Aufrufen (Kosten sparen).            |
| `AIVD_OCR_LANG`             | `eng`               | OCR-Sprache(n), z. B. `deu+eng`.                           |
| `AIVD_TESSERACT_CMD`        | autom.              | Pfad zu `tesseract.exe`, falls nicht im Standardpfad.      |
| `AIVD_MONITOR_INDEX`        | `1`                 | Welcher Monitor (1 = Hauptbildschirm).                     |
| `AIVD_PREVIEW_WIDTH`        | `480`               | Breite der Live-Vorschau (Downscaling).                    |

---

## 🧠 AI-Design (warum es günstig & sicher ist)

- **Keine Rohbilder** an die AI – nur App-Name, Fenstertitel, letzte Apps und die
  Top-Schlüsselwörter aus der OCR.
- **Gedrosselte Aufrufe**: standardmäßig nur alle 25 s ein LLM-Request (nicht pro Frame).
- **Kompaktes Prompting** + **strukturiertes JSON** als Output.
- **Günstiges Standardmodell** (`claude-haiku-4-5`) für die häufige Klassifizierung.
- **Robuster Fallback**: bei Netzwerk-/API-Fehlern wird automatisch die lokale
  Heuristik genutzt – das Tracking läuft immer weiter.

---

## 🏗️ Architektur (kurz)

`TrackingEngine` (in `core/engine.py`) läuft in einem **Hintergrund-Thread** und
führt pro Intervall aus:

```
Screenshot → aktives Fenster → (nur bei Bildänderung) OCR → Keywords
           → (alle 25 s) AI-Analyse → Metriken → geteilter Zustand
```

Das **Streamlit-Dashboard** hält die Engine über `st.cache_resource` als Singleton
(überlebt Reruns) und liest den Zustand per `engine.snapshot()`. Start/Stop steuert
nur den Thread – die UI bleibt reaktiv.

**Performance:** Eine leichte Bild-Differenz-Erkennung verhindert unnötige OCR-Läufe,
und das Intervall wird in kleinen Schritten abgewartet, statt die CPU zu blockieren.

---

## 🩹 Troubleshooting

- **„OCR: nicht gefunden“** → Tesseract installieren bzw. `AIVD_TESSERACT_CMD` setzen.
- **AI zeigt „Heuristik“** → kein `ANTHROPIC_API_KEY` gesetzt (oder ungültig).
- **Leere Vorschau** → links auf **▶ Start** klicken.
- **Falscher Monitor** → `AIVD_MONITOR_INDEX` anpassen (1 = Hauptbildschirm).
- **Hohe CPU-Last** → `AIVD_CAPTURE_INTERVAL` erhöhen (z. B. `2.0`).

---

## 📄 Hinweis

Dieses Tool ist für die Analyse des **eigenen** Bildschirms gedacht (persönliche
Produktivität, Self-Tracking). Setze es nur auf Geräten ein, für die du autorisiert bist.
