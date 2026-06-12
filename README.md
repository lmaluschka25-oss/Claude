# Der Weg — Tagesbegleiter

Ratgeber, Leitfaden und Tracker in einer einzigen Datei. Kein Server, kein Account, kein Build — `index.html` öffnen und loslegen.

## Öffnen

- **Am Rechner:** Doppelklick auf `index.html`.
- **Am Handy:** Datei z. B. per Cloud/Messenger aufs Handy schicken und im Browser öffnen — oder das Repo über GitHub Pages veröffentlichen (Settings → Pages → Branch wählen), dann ist die Seite unter einer festen URL erreichbar und lässt sich zum Homescreen hinzufügen.

## Die fünf Tabs

| Tab | Was er ist |
|---|---|
| **Heute** | Dein Tagesritual: Tageszitat + eigene Zeile, Gewohnheiten abhaken, Tag bewerten (1–5 Flammen), Abendjournal. Bis zu 4 Wochen zurückblätterbar. |
| **Der Weg** | Der Leitfaden — dein Plan mit allen Begründungen, deine aktuelle Routine, Restday, die zwei Regeln. |
| **Das Buch** | Dein Tagebuch, das sich von selbst schreibt (alle Zeilen und Einträge, durchsuchbar) + die Zitate-Sammlung mit Favoriten und eigenen Zeilen. |
| **Fortschritt** | Statistik, Heatmap (8 Wochen), Balken pro Gewohnheit, der Ratgeber („Was dir auffällt") und das Wochen-Review. |
| **Anpassen** | Gewohnheiten und Routine ändern, pausieren, erweitern. Jede Änderung landet im Logbuch — so siehst du, wie sich dein System entwickelt. Plus: Backup exportieren/einlesen. |

## Wie es gedacht ist

- **Morgens (2 Min):** Zitat lesen → eigene Zeile schreiben → erste Haken setzen.
- **Abends (3 Min):** Haken vervollständigen → Flammen → „Was hab ich GEMACHT" + eine ehrliche Zeile.
- **Sonntags (5 Min):** Wochen-Review im Fortschritt-Tab → EINE Stellschraube unter „Anpassen" drehen.

Es gibt absichtlich **keine Streaks**. Eine Lücke ist kein Rückschritt — was zählt, ist nur, dass du wiederkommst.

## Daten

Alles liegt im `localStorage` des Browsers (Schlüssel `derweg.v2`). Daten der alten Seitenversion werden beim ersten Start automatisch übernommen.

**Wichtig:** Einmal im Monat unter Anpassen → „Backup exportieren" klicken. Die JSON-Datei lässt sich auf jedem Gerät wieder einlesen.

## Projekt

- `index.html` — die komplette App (HTML + CSS + Vanilla-JS, keine Abhängigkeiten).
- `PROMPT.md` — der Prompt, mit dem dieses Projekt gebaut wurde.
