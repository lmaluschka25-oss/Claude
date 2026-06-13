export function formatClock(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "0:00";
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export function formatAge(seconds) {
  if (seconds == null) return "—";
  if (seconds < 1) return "just now";
  if (seconds < 60) return `${seconds.toFixed(1)}s ago`;
  return `${formatClock(seconds)} ago`;
}

export function agentInitials(name) {
  if (!name) return "?";
  const clean = name.replace("/", "");
  return clean.slice(0, 2).toUpperCase();
}

export function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}

// Map a pressure value in [0,1] to a warm color (teal -> amber -> red).
export function pressureColor(p) {
  if (p >= 0.66) return "#ff4655";
  if (p >= 0.33) return "#ffb454";
  return "#19c3a6";
}

export function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
