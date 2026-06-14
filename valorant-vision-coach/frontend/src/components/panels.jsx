import { KIND_ICON, agentInitials, cx, pct, rampColor } from "../util.js";

function Panel({ title, extra, children, className }) {
  return (
    <div className={cx("panel", className)}>
      <div className="panel-head">
        <h3>{title}</h3>
        {extra != null && <span className="panel-extra">{extra}</span>}
      </div>
      <div className="panel-body">{children}</div>
    </div>
  );
}

export function DetectedInfo({ info }) {
  if (!info) return <Panel title="DETECTED INFO"><div className="empty small">—</div></Panel>;
  const alive = info.players_alive_ally != null;
  return (
    <Panel title="DETECTED INFO">
      <dl className="kv">
        <div><dt>Map</dt><dd>{info.map_name || "—"} <em>({pct(info.map_confidence)})</em></dd></div>
        <div><dt>Side</dt><dd className="cap">{info.side} <em>({pct(info.side_confidence)})</em></dd></div>
        <div><dt>Round</dt><dd>{info.round_number}</dd></div>
        <div><dt>Score</dt><dd>{info.score_text || "—"}</dd></div>
        <div><dt>Time</dt><dd>{info.round_time || "—"}</dd></div>
        <div><dt>Alive</dt><dd>{alive ? `${info.players_alive_ally} vs ${info.players_alive_enemy}` : "—"}</dd></div>
        <div><dt>Spike</dt><dd>{info.spike_planted ? "Planted" : "Not planted"}</dd></div>
        <div><dt>Economy</dt><dd>{info.economy || "—"}</dd></div>
      </dl>
    </Panel>
  );
}

export function UtilityDetected({ utilities = [] }) {
  return (
    <Panel title="UTILITY DETECTED">
      {utilities.length === 0 && <div className="empty small">No utility detected.</div>}
      {utilities.slice(0, 6).map((u, i) => (
        <div className="util-row" key={i}>
          <span className="util-ico">{KIND_ICON[u.kind] || "✦"}</span>
          <span className="util-name">
            {u.kind[0].toUpperCase() + u.kind.slice(1)} {u.callout || ""}
          </span>
          <span className="muted">{u.agent_name || ""}</span>
        </div>
      ))}
    </Panel>
  );
}

export function DetectedPositions({ positions = [] }) {
  return (
    <Panel title="DETECTED POSITIONS (LIVE)">
      {positions.length === 0 && <div className="empty small">No enemies located.</div>}
      {positions.map((p, i) => (
        <div className="pos-row" key={i}>
          <span className="agent-chip">
            <span className="ic enemy">{agentInitials(p.agent_name)}</span>
            Enemy {p.agent_name || "?"}
          </span>
          <span className="pos-callout">{p.callout || "—"}</span>
        </div>
      ))}
    </Panel>
  );
}

export function PositionProbabilities({ probs = [] }) {
  return (
    <Panel title="POSITION PROBABILITIES">
      <div className="bars">
        {probs.map((p) => (
          <div className="bar-row" key={p.site}>
            <span className="bar-label">{p.site}</span>
            <div className="bar">
              <span style={{ width: pct(p.probability), background: rampColor(p.probability) }} />
            </div>
            <span className="bar-val mono">{pct(p.probability)}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function PatternRecognition({ patterns = [] }) {
  return (
    <Panel title="PATTERN RECOGNITION">
      {patterns.length === 0 && <div className="empty small">Learning… upload rounds.</div>}
      {patterns.map((p, i) => (
        <div className="pattern-row" key={i}>
          <span className="pattern-ico">◆</span>
          <div>
            <div className="pattern-text">{p.text}</div>
            <div className="muted small">{p.detail}</div>
          </div>
          <span className="pattern-conf mono">{pct(p.confidence)}</span>
        </div>
      ))}
    </Panel>
  );
}

const SITE_KEYS = ["A", "B", "C", "MID"];

export function MatchMemory({ memory }) {
  if (!memory) return null;
  return (
    <Panel title="MATCH MEMORY (SO FAR)">
      <dl className="kv wide">
        <div><dt>Rounds Analyzed</dt><dd>{memory.rounds_analyzed}</dd></div>
        {SITE_KEYS.filter((s) => s in (memory.site_presence || {})).map((s) => (
          <div key={s}><dt>{s} Presence</dt><dd className="good">{pct(memory.site_presence[s])}</dd></div>
        ))}
        <div><dt>Common Utility</dt><dd>{memory.common_utility || "—"}</dd></div>
        <div><dt>Enemy Economy</dt><dd>{memory.enemy_economy || "—"}</dd></div>
        <div><dt>Confidence</dt><dd className="amber">{pct(memory.confidence)}</dd></div>
      </dl>
    </Panel>
  );
}

export function EnemyProfiles({ profiles = [] }) {
  return (
    <Panel title="ENEMY PROFILES (SO FAR)">
      {profiles.length === 0 && <div className="empty small">No enemy agents identified yet.</div>}
      {profiles.map((p, i) => (
        <div className="profile-row" key={i}>
          <span className="agent-chip">
            <span className="ic enemy">{agentInitials(p.agent_name)}</span>
            {p.agent_name || "Unknown"}
          </span>
          <span className="muted small">{p.note}</span>
          <span className="profile-site">{p.favored_site} {pct(p.site_share)}</span>
          <span className="muted small">{p.rotation_tendency}</span>
        </div>
      ))}
    </Panel>
  );
}

function GunRow({ tier }) {
  const lit = { eco: 1, force: 2, full: 3, unknown: 0 }[tier] || 0;
  return (
    <div className="guns">
      {[0, 1, 2].map((i) => (
        <span key={i} className={cx("gun", i < lit && "lit")}>▰</span>
      ))}
    </div>
  );
}

export function WeaponEconomy({ economy }) {
  if (!economy) return null;
  return (
    <Panel title="WEAPON / ECONOMY DETECTION">
      <div className="econ-block">
        <div className="econ-label">Enemies</div>
        <GunRow tier={economy.enemy_tier} />
        <div className={cx("econ-tag", economy.enemy_tier)}>{economy.enemy_label || "Unknown"}</div>
      </div>
      <div className="econ-block">
        <div className="econ-label">Teammates</div>
        <GunRow tier={economy.ally_tier} />
        <div className={cx("econ-tag", economy.ally_tier)}>{economy.ally_label || "Unknown"}</div>
      </div>
    </Panel>
  );
}

export function RecommendationPanel({ rec }) {
  if (!rec) return null;
  return (
    <Panel title="RECOMMENDATION FOR NEXT ROUND">
      <div className="rec-best">
        <span className="rec-label">Best Site</span>
        <span className="rec-site">{rec.best_site || "—"}</span>
      </div>
      <div className="rec-stats">
        <div><span className="rec-label">Success Probability</span><span className="good big">{pct(rec.success_probability)}</span></div>
        <div><span className="rec-label">Confidence</span><span className="amber big">{pct(rec.confidence)}</span></div>
      </div>
      <div className="muted small">{rec.confidence_label}</div>
    </Panel>
  );
}

export function ReasoningPanel({ rec }) {
  if (!rec) return null;
  return (
    <Panel title="REASONING">
      <ul className="reasons">
        {rec.reasons.map((r, i) => <li key={i}><span className="check">✓</span>{r}</li>)}
      </ul>
      {rec.suggested_play?.length > 0 && (
        <>
          <div className="sub-label">Suggested Play</div>
          <ul className="suggested">
            {rec.suggested_play.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </>
      )}
    </Panel>
  );
}

export function AnalysisLog({ steps = [] }) {
  return (
    <Panel title="ANALYSIS LOG (STEP BY STEP)">
      <div className="log-steps">
        {steps.map((s) => (
          <div className={cx("log-step", s.status)} key={s.step}>
            <div className="log-step-head">
              <span className="log-check">{s.status === "skipped" ? "•" : "✓"}</span>
              Step {s.step} — {s.title}
            </div>
            <div className="muted small">{s.detail}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
