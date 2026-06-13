import { useMemo } from "react";
import { pressureColor } from "../util.js";

// The single output of the app: predicted enemy site commitment for the next
// round, as a scouting card. Post-match preparation material — not live.
export default function PredictionCard({ prediction, mapMeta }) {
  const siteCentroids = useMemo(() => {
    const groups = {};
    (mapMeta?.callouts || []).forEach((c) => {
      if (c.site) (groups[c.site] = groups[c.site] || []).push(c);
    });
    const out = {};
    Object.entries(groups).forEach(([site, cs]) => {
      out[site] = {
        x: cs.reduce((a, c) => a + c.x, 0) / cs.length,
        y: cs.reduce((a, c) => a + c.y, 0) / cs.length,
      };
    });
    return out;
  }, [mapMeta]);

  if (!prediction) return null;

  const {
    rounds_analyzed,
    predicted_sites,
    confidence,
    top_factor,
    factors,
    per_round_commitment,
    last_committed_site,
  } = prediction;

  if (!rounds_analyzed) {
    return (
      <div className="panel predict">
        <div className="panel-body empty">
          Noch keine Runden-Tendenzen. Nimm ein paar Runden auf (mit aktiviertem
          OCR für die Runden-Erkennung), dann erscheint hier die Vorhersage.
        </div>
      </div>
    );
  }

  const top = predicted_sites[0];
  const probBySite = Object.fromEntries(predicted_sites.map((s) => [s.site, s.probability]));

  return (
    <div className="panel predict">
      <div className="panel-header">
        <h2>Wahrscheinliche Site — nächste Runde</h2>
        <span className="faint">aus {rounds_analyzed} Runden</span>
      </div>
      <div className="panel-body">
        <div className="predict-hero">
          <div className="predict-top">
            <div className="predict-top-site" style={{ color: pressureColor(top.probability) }}>
              {top.site}
            </div>
            <div className="predict-top-pct">{Math.round(top.probability * 100)}%</div>
          </div>
          {mapMeta && Object.keys(siteCentroids).length > 0 && (
            <svg className="predict-map" viewBox="0 0 100 100" aria-label="Site-Karte">
              <rect x="0" y="0" width="100" height="100" rx="6" fill="#0e1420" />
              {Object.entries(siteCentroids).map(([site, c]) => {
                const p = probBySite[site] || 0;
                return (
                  <g key={site}>
                    <circle
                      cx={c.x * 100}
                      cy={c.y * 100}
                      r={6 + p * 22}
                      fill={pressureColor(p)}
                      opacity={0.25 + p * 0.55}
                    />
                    <text
                      x={c.x * 100}
                      y={c.y * 100 + 2}
                      fontSize="7"
                      fontWeight="800"
                      fill="#fff"
                      textAnchor="middle"
                    >
                      {site}
                    </text>
                    <text
                      x={c.x * 100}
                      y={c.y * 100 + 12}
                      fontSize="5.5"
                      fill="#aeb9c9"
                      textAnchor="middle"
                    >
                      {Math.round(p * 100)}%
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        <div className="predict-bars">
          {predicted_sites.map((s) => (
            <div className="predict-bar-row" key={s.site}>
              <div className="predict-bar-site">{s.site}</div>
              <div className="bar">
                <span
                  style={{
                    width: `${Math.round(s.probability * 100)}%`,
                    background: pressureColor(s.probability),
                  }}
                />
              </div>
              <div className="predict-bar-pct mono">{Math.round(s.probability * 100)}%</div>
            </div>
          ))}
        </div>

        <div className="predict-meta">
          <div>
            <span className="muted">Sicherheit</span>
            <div className="bar" style={{ marginTop: 4 }}>
              <span style={{ width: `${Math.round(confidence * 100)}%`, background: "#19c3a6" }} />
            </div>
          </div>
          <div className="mono faint" style={{ minWidth: 48, textAlign: "right" }}>
            {Math.round(confidence * 100)}%
          </div>
        </div>

        {top_factor && (
          <div className="predict-reason">
            <span className="muted">Hauptgrund:</span> {top_factor}
          </div>
        )}

        {factors?.length > 0 && (
          <div className="predict-factors">
            {factors.map((f, i) => (
              <div className="predict-factor" key={i}>
                <div className="pf-head">
                  <span>{f.label}</span>
                  <span className="faint mono">{Math.round(f.weight * 100)}%</span>
                </div>
                <div className="faint">{f.detail}</div>
              </div>
            ))}
          </div>
        )}

        {per_round_commitment?.length > 0 && (
          <div className="predict-seq">
            <span className="muted">Verlauf:</span>
            {per_round_commitment.map((s, i) => (
              <span
                key={i}
                className="seq-chip"
                style={{
                  borderColor:
                    i === per_round_commitment.length - 1 ? "var(--accent)" : "var(--border)",
                }}
              >
                {s}
              </span>
            ))}
            {last_committed_site && (
              <span className="faint"> · zuletzt {last_committed_site}</span>
            )}
          </div>
        )}

        <div className="notice" style={{ marginTop: 12 }}>
          Scouting aus deinen Aufnahmen — Vorbereitungs-Wissen, keine Live-Daten
          aus dem laufenden Spiel.
        </div>
      </div>
    </div>
  );
}
