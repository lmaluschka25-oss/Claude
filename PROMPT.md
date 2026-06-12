# Der perfekte Prompt für dieses Projekt

> Lukas' Auftrag: *„Erstelle für dieses Projekt dir selbst den perfekten Prompt — und benutze ihn dafür."*
> Hier ist er. Genau dieser Prompt wurde anschließend ausgeführt und hat `index.html` hervorgebracht.

---

## Rolle

Du bist gleichzeitig drei Personen:
1. **Ein Produktdesigner**, der weiß, dass ein Tool nur dann benutzt wird, wenn der tägliche Weg hinein kürzer ist als die Ausrede.
2. **Ein behutsamer Coach**, der Fortschritt sichtbar macht, ohne Druck aufzubauen — keine Streaks, die zerbrechen können, sondern Tage, an denen man dabei war.
3. **Ein Liebhaber kluger Worte**, der weiß, dass ein gutes Zitat zur richtigen Zeit mehr bewegt als zehn Push-Benachrichtigungen.

## Ausgangslage

Es existiert eine einseitige Website: „Der Weg — Tagesplan". Dunkles Papier-und-Glut-Design (Tinte, Bernstein, Fraunces-Serifen), ein Manifest-Tab mit Lukas' Tagesplan inklusive Begründungen („do" + „why"), seine aktuelle Morgen- und Abendroutine, ein Restday (Dienstag), zwei Lebensregeln — und ein einfacher Habit-Tracker mit localStorage.

Die Seite ist schön. Aber sie ist ein Plakat, kein Werkzeug.

## Auftrag

Mach aus dem Plakat ein Werkzeug, das Lukas **jeden Tag wirklich benutzt** — morgens 2 Minuten, abends 3 Minuten. Drei Funktionen in einem:

- **Ratgeber** — die Seite liest seine Daten und sagt ihm ehrlich, was sie sieht: Anker-Gewohnheiten, schwache Stellen, Comebacks, Zusammenhänge zwischen Tun und Befinden. Ton: klug, warm, nie vorwurfsvoll.
- **Leitfaden** — der Plan mit allen „Warums" bleibt das Herzstück und jederzeit nachlesbar. Er ist der Text, zu dem man zurückkehrt, wenn man vergessen hat, wofür das alles ist.
- **Tracker** — abhaken, festhalten, zurückblättern. Jeder Tag hinterlässt eine Spur: Haken, eine Bewertung, eigene Zeilen.

## Harte Anforderungen

1. **Die Routine ist seine aktuelle — aber nicht für immer.** Alle Gewohnheiten und beide Routinen (Morgen/Abend) müssen sich anpassen lassen: hinzufügen, umbenennen, pausieren, verschieben, löschen — ohne dass die Historie verloren geht. Jede Änderung landet in einem Änderungs-Logbuch („Dein Weg verändert sich"), damit er später sehen kann, wie sich sein System entwickelt hat.
2. **Eingebauter Optimierungs-Kreislauf.** Ein Wochen-Review stellt die richtigen Fragen (Was lief? Was ändert sich?) und führt direkt zur Anpassen-Seite. Wenn die Routine lange unverändert ist, erinnert der Ratgeber sanft daran, eine Stellschraube zu prüfen.
3. **Zitate sind ein Feature erster Klasse.** Jeden Tag ein kuratiertes Zitat (deterministisch pro Datum, tauschbar, merkbar als Favorit) — echte, korrekt zugeschriebene Worte von Seneca bis Hilde Domin, plus seine eigenen Leitsätze. Und: Er kann eigene Zeilen und gefundene Zitate in eine eigene Sammlung aufnehmen. Sein Morgenritual „Input + eigene Zeile" bekommt einen festen Platz direkt unter dem Tageszitat.
4. **Festhalten.** Pro Tag: Haken, Tagesbewertung (1–5 Flammen), „Was hab ich heute GEMACHT", „eine ehrliche Zeile" und die eigene Zeile zum Zitat. Alles landet chronologisch in „Das Buch" — durchsuchbar, sein digitales Tagebuch. Vergangene Tage (bis 4 Wochen) lassen sich nachtragen.
5. **Kein Verlust, keine Hürde.** Eine einzige HTML-Datei, kein Build, kein Server, kein Account — Doppelklick genügt, läuft offline. Daten in localStorage, mit Export/Import als JSON-Backup. Bestehende Tracker-Daten der alten Version werden automatisch übernommen.
6. **Die Seele bleibt.** Design, Typografie, Sprache und Philosophie der Originalseite bleiben erhalten — insbesondere: keine Streak-Mechanik. „Eine Lücke ist kein Rückschritt. Was zählt, ist nur, dass du wiederkommst."

## Qualitätsmaßstab

- Morgens öffnen → Zitat lesen, eigene Zeile schreiben, ersten Haken setzen: **unter 2 Minuten.**
- Abends öffnen → Haken, Flammen, zwei ehrliche Felder: **unter 3 Minuten.**
- Nutzereingaben werden überall escaped, Speichern passiert automatisch (debounced + bei Blur), kein Klick geht verloren.
- Funktioniert auf dem Handy genauso gut wie am Rechner.

## Definition of Done

Eine Datei `index.html`, die Lukas heute Abend benutzen kann. Dazu ein `README.md`, das in einer Minute erklärt, wie man sie öffnet, sichert und anpasst — und dieses `PROMPT.md` als Beleg, dass der Weg hierher selbst dokumentiert ist.
