import Donut from "../components/Donut.jsx";
import {
  AnalysisLog,
  MatchMemory,
  PatternRecognition,
  PositionProbabilities,
} from "../components/panels.jsx";
import { pct } from "../util.js";

export default function LearningsView({ intelligence }) {
  if (!intelligence || (intelligence.match_memory?.rounds_analyzed || 0) === 0) {
    return (
      <div className="view">
        <div className="panel"><div className="panel-body empty">
          Nothing learned yet. Add rounds to a match — this page fills in as the
          system builds a read on the opponent.
        </div></div>
      </div>
    );
  }

  const mem = intelligence.match_memory;
  const learnings = intelligence.learnings || [];
  const profiles = intelligence.enemy_profiles || [];

  return (
    <div className="view learnings-view">
      <div className="panel">
        <div className="panel-head">
          <h3>WHAT THE SYSTEM HAS LEARNED</h3>
          <span className="panel-extra">{mem.rounds_analyzed} rounds · {pct(mem.confidence)} confidence</span>
        </div>
        <div className="panel-body">
          <ul className="learn-list">
            {learnings.map((l, i) => <li key={i}><span className="check">✓</span>{l}</li>)}
          </ul>
        </div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head"><h3>SITE TENDENCY (LEARNED)</h3></div>
          <div className="panel-body"><Donut data={mem.site_presence} title="Share of rounds" /></div>
        </div>
        <PositionProbabilities probs={intelligence.position_probabilities} />
      </div>

      <PatternRecognition patterns={intelligence.patterns} />

      <div className="panel">
        <div className="panel-head"><h3>AGENT TENDENCIES (LEARNED)</h3></div>
        <div className="panel-body">
          {profiles.length === 0 && <div className="empty small">No agents identified yet.</div>}
          {profiles.map((p, i) => (
            <div className="agent-learn" key={i}>
              <div className="agent-learn-head">
                <b>{p.agent_name || "Unknown"}</b>
                <span className="muted small">{p.note} · {p.rotation_tendency}</span>
              </div>
              <div className="agent-learn-bar">
                <div className="bar"><span style={{ width: pct(p.site_share), background: "#4ade80" }} /></div>
                <span className="mono small">{p.favored_site} {pct(p.site_share)}</span>
              </div>
              <div className="muted small">Seen {p.rounds_seen}× — most often near {p.favored_site}.</div>
            </div>
          ))}
        </div>
      </div>

      <MatchMemory memory={mem} />
      <AnalysisLog steps={intelligence.analysis_log} />
    </div>
  );
}
