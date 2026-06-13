// Thin API client. Defaults to same-origin "/api" (works in dev via the Vite
// proxy and in Docker via nginx). Override with VITE_API_BASE if needed.
const BASE = import.meta.env.VITE_API_BASE || "/api";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  systemInfo: () => req("/system/info"),
  listMaps: () => req("/maps"),
  getMap: (name) => req(`/maps/${name}`),

  listMatches: () => req("/matches"),
  getMatch: (id) => req(`/matches/${id}`),
  deleteMatch: (id) => req(`/matches/${id}`, { method: "DELETE" }),
  getRounds: (id) => req(`/matches/${id}/rounds`),
  getKillfeed: (id) => req(`/matches/${id}/killfeed`),

  getSnapshot: (id, at, ttl) => {
    const params = new URLSearchParams();
    if (at != null) params.set("at", at);
    if (ttl != null) params.set("ttl", ttl);
    return req(`/matches/${id}/analysis/snapshot?${params.toString()}`);
  },
  getTendencies: (id) => req(`/matches/${id}/analysis/tendencies`),
  getPrediction: (id) => req(`/matches/${id}/analysis/prediction`),

  // Upload with progress via XHR (fetch lacks upload progress events).
  uploadMatch(file, mapName, onProgress) {
    return new Promise((resolve, reject) => {
      const form = new FormData();
      form.append("file", file);
      if (mapName) form.append("map_name", mapName);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/matches`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
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
