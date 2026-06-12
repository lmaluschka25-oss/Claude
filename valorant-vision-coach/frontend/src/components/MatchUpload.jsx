import { useRef, useState } from "react";
import { api } from "../api/client.js";

export default function MatchUpload({ maps, onUploaded }) {
  const fileRef = useRef(null);
  const [mapName, setMapName] = useState("");
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [fileName, setFileName] = useState("");

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Choose a recorded match file first.");
      return;
    }
    setError(null);
    setProgress(0);
    try {
      const match = await api.uploadMatch(file, mapName || null, setProgress);
      setProgress(null);
      setFileName("");
      if (fileRef.current) fileRef.current.value = "";
      onUploaded?.(match);
    } catch (e) {
      setError(e.message);
      setProgress(null);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Upload match VOD</h2>
      </div>
      <div className="panel-body uploader">
        <div className="dropzone">
          Drop or choose a recording (.mp4 / .mov / .mkv / .avi / .webm).
          <br />
          Processed locally — nothing leaves this machine.
        </div>

        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          onChange={(e) => setFileName(e.target.files?.[0]?.name || "")}
        />
        {fileName && <div className="faint mono">{fileName}</div>}

        <div className="field">
          <label htmlFor="map-select">Map (optional — auto if blank)</label>
          <select
            id="map-select"
            value={mapName}
            onChange={(e) => setMapName(e.target.value)}
          >
            <option value="">Auto-detect</option>
            {maps.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {progress != null && (
          <div className="progress">
            <span style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}

        <button
          className="btn primary"
          onClick={handleUpload}
          disabled={progress != null}
        >
          {progress != null ? "Uploading…" : "Analyze"}
        </button>
      </div>
    </div>
  );
}
