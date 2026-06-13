"""AI Vision Dashboard – Streamlit Frontend.

Live-Dashboard mit Dark-Mode, Auto-Refresh (ohne manuelles Neuladen),
Start/Stop-Steuerung, Live-Vorschau, AI-Status, Fokus-Score, Charts und
CSV-Export.

Start:  streamlit run dashboard/app.py
   oder: python main.py dashboard
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import streamlit as st

# Projekt-Root in den Importpfad legen, damit "core" gefunden wird – egal von
# wo Streamlit gestartet wurde.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.engine import TrackingEngine  # noqa: E402
from core.metrics import format_duration  # noqa: E402

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    st_autorefresh = None


# --- Seitenkonfiguration ---------------------------------------------------
st.set_page_config(
    page_title="AI Vision Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
:root { --accent:#6C5CE7; --accent2:#00D9A3; --card:#161B26; --line:#262C3A; }
.block-container { padding-top: 1.4rem; max-width: 1500px; }
#MainMenu, footer { visibility: hidden; }

.hero {
  background: linear-gradient(120deg, rgba(108,92,231,.22), rgba(0,217,163,.14));
  border: 1px solid var(--line); border-radius: 18px;
  padding: 18px 24px; margin-bottom: 16px;
}
.hero h1 { margin:0; font-size: 1.6rem; letter-spacing:.3px; }
.hero p  { margin:.25rem 0 0; color:#9AA4B2; font-size:.92rem; }
.dot { height:10px; width:10px; border-radius:50%; display:inline-block; margin-right:7px; }
.dot.on  { background:var(--accent2); box-shadow:0 0 10px var(--accent2); }
.dot.off { background:#5a6072; }

.metric-card {
  background: var(--card); border:1px solid var(--line); border-radius:14px;
  padding:16px 18px; height:100%;
}
.metric-label { color:#8B93A7; font-size:.72rem; text-transform:uppercase; letter-spacing:.6px; }
.metric-value { font-size:1.5rem; font-weight:700; margin-top:4px; line-height:1.2; }
.metric-sub { color:#7b8194; font-size:.78rem; margin-top:4px; }

.ai-banner {
  background: linear-gradient(120deg, rgba(108,92,231,.16), rgba(22,27,38,.6));
  border:1px solid var(--line); border-left:4px solid var(--accent);
  border-radius:14px; padding:16px 20px; margin: 6px 0 4px;
}
.ai-banner .lbl { color:#8B93A7; font-size:.72rem; text-transform:uppercase; letter-spacing:.6px; }
.ai-banner .txt { font-size:1.15rem; font-weight:600; margin-top:4px; }

.badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.78rem; font-weight:600; }
.kw { display:inline-block; background:#1d2230; border:1px solid var(--line);
      color:#aab2c5; border-radius:8px; padding:2px 8px; margin:2px 4px 2px 0; font-size:.75rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --- Engine als Singleton (überlebt Streamlit-Reruns) ----------------------
@st.cache_resource(show_spinner=False)
def get_engine() -> TrackingEngine:
    return TrackingEngine()


engine = get_engine()

# Live-Aktualisierung ohne manuelles Neuladen.
if st_autorefresh is not None:
    st_autorefresh(interval=2000, key="aivd_refresh")

CATEGORY_COLORS = {
    "Coding": "#00D9A3",
    "Messaging": "#4DA3FF",
    "Browsing": "#6C5CE7",
    "Watching Video": "#FF9F43",
    "Gaming": "#FF6B6B",
    "Unknown": "#7b8194",
}


def badge(category: str) -> str:
    color = CATEGORY_COLORS.get(category, "#7b8194")
    safe = html.escape(category)
    return f'<span class="badge" style="background:{color}22;color:{color};border:1px solid {color}55">{safe}</span>'


def metric_card(label: str, value_html: str, sub: str = "") -> str:
    return (
        f'<div class="metric-card"><div class="metric-label">{html.escape(label)}</div>'
        f'<div class="metric-value">{value_html}</div>'
        f'<div class="metric-sub">{html.escape(sub)}</div></div>'
    )


# --- Sidebar: Steuerung ----------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Steuerung")
    snap = engine.snapshot()
    running = snap["running"]

    col_a, col_b = st.columns(2)
    if col_a.button("▶ Start", use_container_width=True, disabled=running, type="primary"):
        engine.start()
        st.rerun()
    if col_b.button("⏹ Stop", use_container_width=True, disabled=not running):
        engine.stop()
        st.rerun()

    state = "Aktiv" if running else "Gestoppt"
    dot = "on" if running else "off"
    st.markdown(f'<span class="dot {dot}"></span>{state}', unsafe_allow_html=True)

    st.divider()
    st.markdown("#### Status")
    ai_mode = f"Claude ({snap['model']})" if snap["ai_enabled"] else "Heuristik (kein API-Key)"
    st.markdown(f"**AI-Modus:** {ai_mode}")
    st.markdown(f"**OCR:** {'verfügbar ✅' if snap['ocr_available'] else 'nicht gefunden ⚠️'}")
    st.markdown(f"**Laufzeit:** {format_duration(snap['uptime'])}")
    st.markdown(f"**Datenpunkte:** {snap['metrics']['sample_count']}")
    if snap["error"]:
        st.warning(f"Letzter Fehler: {snap['error']}")

    st.divider()
    csv_data = engine.csv_string()
    st.download_button(
        "⬇️ CSV-Export",
        data=csv_data,
        file_name="ai_vision_dashboard.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=snap["metrics"]["sample_count"] == 0,
    )
    st.caption("Bilder werden nur im RAM gehalten und nie gespeichert.")


# --- Daten holen -----------------------------------------------------------
snap = engine.snapshot()
m = snap["metrics"]
running = snap["running"]

# --- Hero ------------------------------------------------------------------
dot = "on" if running else "off"
st.markdown(
    f"""
    <div class="hero">
      <h1>🧠 AI Vision Dashboard</h1>
      <p><span class="dot {dot}"></span>{'Live-Analyse läuft' if running else 'Bereit – klicke links auf Start'} ·
      analysiert App-Nutzung, Inhalte & Fokus in Echtzeit</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Kennzahlen-Reihe ------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.markdown(
    metric_card("Aktive App", html.escape(snap["current_app"]),
                (snap["current_title"] or "")[:42]),
    unsafe_allow_html=True,
)
c2.markdown(
    metric_card("Aktivität", badge(snap["current_category"]),
                f"Quelle: {snap['ai_source']}"),
    unsafe_allow_html=True,
)
focus = int(round(m["focus_score"]))
focus_color = "#00D9A3" if focus >= 66 else ("#FF9F43" if focus >= 40 else "#FF6B6B")
c3.markdown(
    metric_card("Fokus-Score", f'<span style="color:{focus_color}">{focus}</span><span style="font-size:.9rem;color:#7b8194">/100</span>',
                "0 = abgelenkt · 100 = fokussiert"),
    unsafe_allow_html=True,
)
c4.markdown(
    metric_card("Fokus / Ablenkung",
                f'{format_duration(m["focus_seconds"])} <span style="color:#7b8194">/</span> {format_duration(m["distraction_seconds"])}',
                f"gesamt {format_duration(m['total_seconds'])}"),
    unsafe_allow_html=True,
)
st.progress(min(100, max(0, focus)) / 100.0)

# --- AI-Status-Banner ------------------------------------------------------
st.markdown(
    f'<div class="ai-banner"><div class="lbl">AI-Interpretation</div>'
    f'<div class="txt">{html.escape(snap["ai_description"])}</div></div>',
    unsafe_allow_html=True,
)

# --- Vorschau + Schlüsselwörter / Charts -----------------------------------
left, right = st.columns([5, 7])

with left:
    st.markdown("#### 🖥️ Live-Vorschau")
    if snap["preview_jpeg"]:
        st.image(snap["preview_jpeg"], use_container_width=True)
    else:
        st.info("Noch keine Vorschau – Tracking starten.")

    st.markdown("#### 🔎 Erkannte Schlüsselwörter")
    if snap["keywords"]:
        chips = "".join(f'<span class="kw">{html.escape(k)}</span>' for k in snap["keywords"])
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("Noch keine relevanten Begriffe erkannt.")

with right:
    st.markdown("#### 📈 Fokus-Verlauf")
    series = m["focus_series"]
    if pd is not None and series:
        df = pd.DataFrame(series).set_index("Zeit")
        st.line_chart(df, height=220, color="#00D9A3")
    else:
        st.caption("Verlauf erscheint, sobald genügend Daten vorliegen.")

    st.markdown("#### 🗂️ App-Nutzung (Minuten)")
    if pd is not None and m["app_usage"]:
        app_df = (
            pd.DataFrame(
                [{"App": a, "Minuten": round(s / 60, 2)} for a, s in m["app_usage"].items()]
            )
            .sort_values("Minuten", ascending=False)
            .head(8)
            .set_index("App")
        )
        st.bar_chart(app_df, height=240, color="#6C5CE7")
    else:
        st.caption("Noch keine App-Daten.")

# --- Untere Charts ---------------------------------------------------------
b1, b2 = st.columns(2)

with b1:
    st.markdown("#### 🎯 Kategorien-Verteilung (Minuten)")
    if pd is not None and m["category_usage"]:
        cat_df = (
            pd.DataFrame(
                [{"Kategorie": c, "Minuten": round(s / 60, 2)} for c, s in m["category_usage"].items()]
            )
            .sort_values("Minuten", ascending=False)
            .set_index("Kategorie")
        )
        st.bar_chart(cat_df, height=240, color="#00D9A3")
    else:
        st.caption("Noch keine Kategorie-Daten.")

with b2:
    st.markdown("#### ⏱️ Nutzung pro Stunde (Minuten)")
    per_hour = m["per_hour"]
    if pd is not None and per_hour:
        rows = []
        for hour, cats in per_hour.items():
            row = {"Stunde": f"{int(hour):02d}:00"}
            for cat, sec in cats.items():
                row[cat] = round(sec / 60, 2)
            rows.append(row)
        hour_df = pd.DataFrame(rows).fillna(0).set_index("Stunde")
        st.bar_chart(hour_df, height=240)
    else:
        st.caption("Noch keine Stunden-Daten.")

# --- Activity Timeline -----------------------------------------------------
st.markdown("#### 🧭 Aktivitäts-Timeline")
segments = m["segments"]
if pd is not None and segments:
    tl = pd.DataFrame(
        [
            {
                "Von": s["start"],
                "Bis": s["end"],
                "App": s["app"],
                "Kategorie": s["category"],
                "Dauer": format_duration(s["seconds"]),
            }
            for s in segments
        ]
    )
    st.dataframe(tl, use_container_width=True, hide_index=True)
else:
    st.caption("Die Timeline füllt sich, sobald das Tracking läuft.")

st.caption("AI Vision Dashboard · lokal · Screenshots verlassen nie deinen Rechner (nur Text/Metadaten gehen optional an die AI).")
