import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { formatClock } from "../util.js";

// Add a match either by recording the screen (analyzed AFTER you stop — not
// live) or by uploading an existing recording. Both feed the same post-match
// pipeline.
export default function MatchUpload({ maps, onUploaded }) {
  const fileRef = useRef(null);
  const [mapName, setMapName] = useState("");
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [fileName, setFileName] = useState("");

  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  useEffect(
    () => () => {
      clearInterval(timerRef.current);
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    },
    []
  );

  async function uploadFile(file) {
    setError(null);
    setProgress(0);
    try {
      const match = await api.uploadMatch(file, mapName || null, setProgress);
      setProgress(null);
      onUploaded?.(match);
    } catch (e) {
      setError(e.message);
      setProgress(null);
    }
  }

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setError("Wähle zuerst eine Aufnahme aus.");
      return;
    }
    await uploadFile(file);
    setFileName("");
    if (fileRef.current) fileRef.current.value = "";
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setError("Bildschirmaufnahme wird von diesem Browser nicht unterstützt.");
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: 30 },
        audio: false,
      });
    } catch {
      setError("Bildschirmfreigabe abgebrochen.");
      return;
    }
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp8")
      ? "video/webm;codecs=vp8"
      : "video/webm";
    const rec = new MediaRecorder(stream, { mimeType: mime });
    chunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data && e.data.size) chunksRef.current.push(e.data);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(timerRef.current);
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      const file = new File([blob], `recording-${Date.now()}.webm`, {
        type: "video/webm",
      });
      await uploadFile(file);
    };
    // If the user stops sharing via the browser's own bar.
    stream.getVideoTracks()[0].addEventListener("ended", () => {
      if (rec.state !== "inactive") rec.stop();
    });
    recorderRef.current = rec;
    rec.start(1000);
    setRecording(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  }

  function stopRecording() {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }

  const busy = progress != null;

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Match hinzufügen</h2>
      </div>
      <div className="panel-body uploader">
        <div className="dropzone">
          Nimm deinen Bildschirm auf oder lade eine Aufnahme hoch.
          <br />
          Alles wird lokal verarbeitet — nichts verlässt deinen Rechner.
        </div>

        <div className="field">
          <label htmlFor="map-select">Map (optional — automatisch wenn leer)</label>
          <select
            id="map-select"
            value={mapName}
            onChange={(e) => setMapName(e.target.value)}
            disabled={recording}
          >
            <option value="">Automatisch erkennen</option>
            {maps.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {!recording ? (
          <button className="btn primary" onClick={startRecording} disabled={busy}>
            ● Bildschirm aufnehmen
          </button>
        ) : (
          <button className="btn danger" onClick={stopRecording}>
            ■ Aufnahme stoppen ({formatClock(elapsed)})
          </button>
        )}
        {recording && (
          <div className="rec-hint">
            <span className="rec-dot" /> Aufnahme läuft … die Analyse startet,
            wenn du stoppst (nicht live).
          </div>
        )}

        <div className="or">— oder Datei hochladen —</div>

        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          disabled={recording}
          onChange={(e) => setFileName(e.target.files?.[0]?.name || "")}
        />
        {fileName && <div className="faint mono">{fileName}</div>}

        {busy && (
          <div className="progress">
            <span style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}

        <button className="btn" onClick={handleUpload} disabled={busy || recording}>
          {busy ? "Lädt …" : "Datei analysieren"}
        </button>
      </div>
    </div>
  );
}
