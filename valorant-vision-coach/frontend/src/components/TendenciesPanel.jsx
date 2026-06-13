import { agentInitials, pressureColor } from "../util.js";

// Post-match scouting report: where the enemy tended to go across rounds.
// Preparation/review material — not a live in-match overlay.
export default function TendenciesPanel({ report }) {
  const rounds = report?.rounds_analyzed || 0;

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Scouting · Tendenzen</h2>
        <span className="faint">{rounds} Runden</span>
      </div>
      <div className="panel-body">
        {rounds === 0 && (
          <div className="empty">
            Noch keine Runden-Tendenzen. Mehrere Runden (mit aktiviertem OCR für
            die Runden-Erkennung) liefern aussagekräftige Werte.
          </div>
        )}

        {rounds > 0 && (
          <>
            <div className="sub-label">Site-Tendenz (Anteil der Runden)</div>
            <div className="pressure-grid" style={{ marginBottom: 14 }}>
              {report.site_frequency.map((s) => (
                <div className="pressure-row" key={s.site}>
                  <div className="site-name">{s.site}</div>
                  <div className="bar">
                    <span
                      style={{
                        width: `${Math.round(s.share * 100)}%`,
                        background: pressureColor(s.share),
                      }}
                    />
                  </div>
                  <div className="mono faint" style={{ textAlign: "right" }}>
                    {Math.round(s.share * 100)}%
                  </div>
                </div>
              ))}
            </div>

            <div className="sub-label">Agent-Präferenz</div>
            {report.agent_site_preference.map((a, i) => (
              <div className="row" key={i}>
                <span className="agent-chip">
                  <span className="ic">{agentInitials(a.agent_name)}</span>
                  {a.agent_name || "Unknown"}
                </span>
                <div className="mono faint" style={{ textAlign: "right" }}>
                  {a.sites.map((s) => `${s.site} ${Math.round(s.share * 100)}%`).join(" · ")}
                  <div style={{ fontSize: 10 }}>{a.rounds_seen}× gesehen</div>
                </div>
              </div>
            ))}

            <div className="notice" style={{ marginTop: 12 }}>
              Vorbereitungs-Wissen aus ausgewerteten Aufnahmen — keine Live-Daten
              aus dem laufenden Spiel.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
