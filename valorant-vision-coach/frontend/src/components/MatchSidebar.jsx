import { cx, formatClock, formatDate } from "../util.js";
import RoundUploader from "./RoundUploader.jsx";

const STATUS_GLYPH = {
  completed: "✓",
  processing: "…",
  pending: "•",
  failed: "✕",
};

export default function MatchSidebar({
  match,
  intelligence,
  selectedRoundId,
  onSelectRound,
  onNewMatch,
  onUploaded,
  onUpdateSide,
}) {
  const rounds = match?.rounds || [];
  const mem = intelligence?.match_memory;

  return (
    <aside className="sidebar">
      <div className="panel match-head">
        <div className="match-title">MATCH: {(match?.map_name || match?.name || "—").toUpperCase()}</div>
        <dl className="match-meta">
          <div><dt>Map</dt><dd>{match?.map_name || "—"}</dd></div>
          <div><dt>Date</dt><dd>{formatDate(match?.created_at)}</dd></div>
          <div><dt>Score</dt><dd>{intelligence?.detected_info?.score_text || "—"}</dd></div>
          <div><dt>Side</dt><dd className="cap">{match?.side || "—"}</dd></div>
          <div><dt>Rounds</dt><dd>{mem ? `${mem.rounds_analyzed} analyzed` : (rounds.length || 0)}</dd></div>
        </dl>
        <div className="side-toggle">
          <span className="side-hint">Your starting side</span>
          <div className="side-btns">
            {["attack", "defense"].map((s) => (
              <button key={s} className={cx("side-btn", match?.side === s && "on")}
                      onClick={() => onUpdateSide?.(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel rounds-panel">
        <div className="panel-head"><h3>ROUNDS</h3></div>
        <div className="rounds-list">
          {rounds.length === 0 && <div className="empty small">No rounds yet — record or upload one.</div>}
          {rounds.map((r) => (
            <button
              key={r.id}
              className={cx("round-row", r.id === selectedRoundId && "active")}
              onClick={() => onSelectRound(r)}
            >
              <span className="round-name">Round {r.round_number}</span>
              <span className="round-time">
                {r.status === "processing"
                  ? `${Math.round((r.progress || 0) * 100)}%`
                  : r.round_time || (r.duration_seconds ? formatClock(r.duration_seconds) : "—")}
              </span>
              <span className={cx("round-stat", r.status)}>{STATUS_GLYPH[r.status] || "•"}</span>
            </button>
          ))}
        </div>
      </div>

      {match && (
        <div className="panel uploader-panel">
          <RoundUploader matchId={match.id} onUploaded={onUploaded} />
        </div>
      )}

      <button className="btn newmatch block" onClick={onNewMatch}>+ NEW MATCH</button>
    </aside>
  );
}
