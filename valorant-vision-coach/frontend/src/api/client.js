// API client for the Match Intelligence platform.
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* non-JSON */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function jsonBody(body) {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const api = {
  base: BASE,
  systemInfo: () => req("/system/info"),
  listMaps: () => req("/maps"),
  getMap: (name) => req(`/maps/${name}`),

  listMatches: () => req("/matches"),
  createMatch: (body) => req("/matches", jsonBody(body)),
  getMatch: (id) => req(`/matches/${id}`),
  updateMatch: (id, body) =>
    req(`/matches/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  deleteMatch: (id) => req(`/matches/${id}`, { method: "DELETE" }),
  listRounds: (id) => req(`/matches/${id}/rounds`),
  getIntelligence: (id, roundId) =>
    req(`/matches/${id}/intelligence${roundId ? `?round_id=${roundId}` : ""}`),

  getRound: (id) => req(`/rounds/${id}`),
  deleteRound: (id) => req(`/rounds/${id}`, { method: "DELETE" }),
  roundVideoUrl: (id) => `${BASE}/rounds/${id}/video`,
  minimapPreviewUrl: (id, opts = {}) => {
    const p = new URLSearchParams({ t: opts.t ?? 0 });
    if (opts.mask) p.set("mask", "1");
    for (const k of ["x_frac", "y_frac", "w_frac", "h_frac", "sat_min", "val_min", "hue_min", "hue_max"]) {
      if (opts[k] != null) p.set(k, opts[k]);
    }
    return `${BASE}/rounds/${id}/minimap-preview?${p.toString()}`;
  },

  // Upload a round recording to a match (XHR for progress).
  uploadRound(matchId, file, mapName, onProgress) {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      if (mapName) form.append("map_name", mapName);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/matches/${matchId}/rounds`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
        else {
          let detail = xhr.statusText;
          try {
            detail = JSON.parse(xhr.responseText).detail || detail;
          } catch {
            /* ignore */
          }
          reject(new Error(`${xhr.status}: ${detail}`));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(form);
    });
  },
};
