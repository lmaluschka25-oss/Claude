export function formatClock(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "0:00";
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function pct(v) {
  return `${Math.round((v || 0) * 100)}%`;
}

export function agentInitials(name) {
  if (!name) return "?";
  if (name === "You") return "Y";
  return name.replace("/", "").slice(0, 2).toUpperCase();
}

export function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}

// Probability/heat color ramp: teal (low) → amber → red (high).
export function rampColor(v) {
  if (v >= 0.66) return "#ff4655";
  if (v >= 0.33) return "#ffb454";
  return "#3fb6a8";
}

export const TEAM_COLOR = {
  enemy: "#ff4655",
  ally: "#3fb6a8",
  unknown: "#8b97a8",
};

// Icon glyphs for timeline / utility kinds.
export const KIND_ICON = {
  spotted: "◎",
  smoke: "❂",
  recon: "➶",
  turret: "⊙",
  trap: "◇",
  flash: "✸",
  molly: "🔥",
  wall: "▦",
  kill: "✕",
  rotation: "➜",
  move: "→",
  info: "?",
};
