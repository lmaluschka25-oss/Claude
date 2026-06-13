import { pct, rampColor } from "../util.js";

// The single most actionable output, big and central: where to attack next
// round and where the enemy is likely defending.
export default function NextRoundHero({ rec, probs = [], roundsAnalyzed = 0 }) {
  if (!rec || !rec.best_site) {
    return (
      <div className="panel hero">
        <div className="hero-empty">
          Add rounds to this match — the next-round read appears here once the
          system has analyzed at least one round.
        </div>
      </div>
    );
  }
  const enemyTop = probs[0];
  return (
    <div className="panel hero">
      <div className="hero-left">
        <div className="hero-label">ATTACK NEXT ROUND</div>
        <div className="hero-site">{rec.best_site}</div>
        <div className="hero-sub">least-defended site</div>
        <div className="hero-stats">
          <div><span className="hero-num good">{pct(rec.success_probability)}</span><span>success est.</span></div>
          <div><span className="hero-num amber">{pct(rec.confidence)}</span><span>{rec.confidence_label}</span></div>
        </div>
      </div>
      <div className="hero-right">
        <div className="hero-probs-label">
          WHERE ENEMIES LIKELY DEFEND {enemyTop ? `· top: ${enemyTop.site}` : ""}
        </div>
        <div className="bars big-bars">
          {probs.map((p) => (
            <div className="bar-row" key={p.site}>
              <span className="bar-label">{p.site}</span>
              <div className="bar tall">
                <span style={{ width: pct(p.probability), background: rampColor(p.probability) }} />
              </div>
              <span className="bar-val mono">{pct(p.probability)}</span>
            </div>
          ))}
        </div>
        {rec.reasons?.[0] && <div className="hero-reason">▸ {rec.reasons[0]}</div>}
        <div className="hero-foot muted small">{roundsAnalyzed} round(s) analyzed</div>
      </div>
    </div>
  );
}
