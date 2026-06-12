import { useEffect, useRef } from "react";
import { formatClock } from "../util.js";

export default function Timeline({ duration, at, onScrub, playing, setPlaying, ttl, onTtl }) {
  const raf = useRef(null);
  const last = useRef(null);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const tick = (now) => {
      const dt = (now - last.current) / 1000;
      last.current = now;
      const next = at + dt;
      if (next >= duration) {
        onScrub(duration);
        setPlaying(false);
        return;
      }
      onScrub(next);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, at, duration]);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Timeline</h2>
        <div className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <label style={{ textTransform: "none" }}>Sighting TTL</label>
          <select value={ttl} onChange={(e) => onTtl(Number(e.target.value))}>
            {[6, 8, 10, 12, 15, 20, 30, 45].map((v) => (
              <option key={v} value={v}>
                {v}s
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="panel-body">
        <div className="timeline">
          <div className="controls">
            <button className="btn" onClick={() => setPlaying(!playing)}>
              {playing ? "⏸" : "▶"}
            </button>
            <button className="btn ghost" onClick={() => onScrub(0)} title="Restart">
              ⏮
            </button>
          </div>
          <input
            type="range"
            min={0}
            max={Math.max(duration, 0.1)}
            step={0.1}
            value={at}
            onChange={(e) => {
              setPlaying(false);
              onScrub(Number(e.target.value));
            }}
          />
          <div className="tcode">
            {formatClock(at)} / {formatClock(duration)}
          </div>
        </div>
      </div>
    </div>
  );
}
