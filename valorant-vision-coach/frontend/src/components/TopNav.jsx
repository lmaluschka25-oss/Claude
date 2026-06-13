import { cx } from "../util.js";

const TABS = ["MATCHES", "ANALYSIS", "LEARNINGS", "SETTINGS"];

export default function TopNav({ tab, onTab, info }) {
  return (
    <header className="topnav">
      <div className="topnav-brand">
        <span className="brand-mark">◣</span>
        VALORANT MATCH ANALYZER
      </div>
      <nav className="topnav-tabs">
        {TABS.map((t) => (
          <button key={t} className={cx("topnav-tab", tab === t && "active")} onClick={() => onTab(t)}>
            {t}
          </button>
        ))}
      </nav>
      <div className="topnav-right">
        {info && (
          <span className="topnav-status" title="Detector backend">
            <span className={cx("dot", info.detector_ready ? "ok" : "off")} />
            {info.detector_backend}
          </span>
        )}
        <span className="topnav-ico" title="Settings" onClick={() => onTab("SETTINGS")}>⚙</span>
        <span className="topnav-ico">—</span>
        <span className="topnav-ico">✕</span>
      </div>
    </header>
  );
}
