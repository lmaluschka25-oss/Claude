import { useState } from "react";
import { cx, formatDate } from "../util.js";

export default function MatchesView({ matches, maps, selectedId, onCreate, onSelect, onDelete }) {
  const [name, setName] = useState("");
  const [mapName, setMapName] = useState("");
  const [side, setSide] = useState("attack");
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      await onCreate({ name: name || null, map_name: mapName || null, side });
      setName("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view matches-view">
      <div className="panel create-panel">
        <div className="panel-head"><h3>NEW MATCH</h3></div>
        <div className="panel-body create-form">
          <label className="field">
            <span>Name (optional)</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ranked vs Sentinels" />
          </label>
          <label className="field">
            <span>Map</span>
            <select value={mapName} onChange={(e) => setMapName(e.target.value)}>
              <option value="">Auto / unknown</option>
              {maps.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Side</span>
            <select value={side} onChange={(e) => setSide(e.target.value)}>
              <option value="attack">Attack</option>
              <option value="defense">Defense</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <button className="btn primary" onClick={create} disabled={busy}>
            {busy ? "Creating…" : "+ Create Match"}
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>MATCH HISTORY</h3><span className="panel-extra">{matches.length}</span></div>
        <div className="panel-body match-grid">
          {matches.length === 0 && <div className="empty">No matches yet — create one above.</div>}
          {matches.map((m) => (
            <div key={m.id} className={cx("match-card", m.id === selectedId && "active")}
                 onClick={() => onSelect(m)}>
              <div className="match-card-top">
                <span className="match-card-map">{(m.map_name || "Unknown").toUpperCase()}</span>
                <span className="cap muted small">{m.side}</span>
              </div>
              <div className="match-card-name">{m.name}</div>
              <div className="match-card-meta">
                <span>{m.completed_rounds}/{m.rounds_count} rounds</span>
                <span>{formatDate(m.created_at)}</span>
              </div>
              <button className="btn ghost danger tiny"
                      onClick={(e) => { e.stopPropagation(); onDelete(m.id); }}>
                Delete
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
