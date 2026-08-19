import { useEffect, useState } from "react";
import { getGeeStatus } from "../api/client";

interface Props {
  onRunSynthetic: (params: { aoiName: string; seed: number; width: number; height: number }) => void;
  onRunGee: (params: {
    aoiName: string;
    aoiGeojson: Record<string, unknown>;
    preStart: string;
    preEnd: string;
    postStart: string;
    postEnd: string;
  }) => void;
  loading: boolean;
  errorMessage: string | null;
}

const EXAMPLE_AOI = JSON.stringify(
  {
    type: "Polygon",
    coordinates: [
      [
        [77.19, 28.6],
        [77.22, 28.6],
        [77.22, 28.63],
        [77.19, 28.63],
        [77.19, 28.6],
      ],
    ],
  },
  null,
  2
);

export default function PipelineControls({ onRunSynthetic, onRunGee, loading, errorMessage }: Props) {
  const [aoiName, setAoiName] = useState("Demo AOI (New Delhi)");
  const [seed, setSeed] = useState(42);
  const [size, setSize] = useState(200);

  const [geeStatus, setGeeStatus] = useState<{ authenticated: boolean; message: string } | null>(null);
  const [aoiGeojsonText, setAoiGeojsonText] = useState(EXAMPLE_AOI);
  const [preStart, setPreStart] = useState("2024-01-01");
  const [preEnd, setPreEnd] = useState("2024-01-31");
  const [postStart, setPostStart] = useState("2024-06-01");
  const [postEnd, setPostEnd] = useState("2024-06-30");
  const [geeFormError, setGeeFormError] = useState<string | null>(null);
  const [geeOpen, setGeeOpen] = useState(false);

  useEffect(() => {
    getGeeStatus()
      .then(setGeeStatus)
      .catch(() => setGeeStatus({ authenticated: false, message: "Could not reach backend." }));
  }, []);

  function submitGee() {
    try {
      const parsed = JSON.parse(aoiGeojsonText);
      setGeeFormError(null);
      onRunGee({ aoiName, aoiGeojson: parsed, preStart, preEnd, postStart, postEnd });
    } catch {
      setGeeFormError("AOI must be valid GeoJSON geometry (a Polygon).");
    }
  }

  return (
    <div className="panel controls-panel">
      <h3>Run Detection</h3>
      <label>
        AOI name
        <input value={aoiName} onChange={(e) => setAoiName(e.target.value)} />
      </label>

      <div className="controls-row">
        <label>
          Seed
          <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
        </label>
        <label>
          Size (px)
          <input
            type="number"
            min={64}
            max={512}
            step={16}
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
          />
        </label>
      </div>

      <button
        className="primary-btn"
        disabled={loading}
        onClick={() => onRunSynthetic({ aoiName, seed, width: size, height: size })}
      >
        {loading ? "Running…" : "Run Demo Scene"}
      </button>
      <p className="hint">
        Generates a synthetic Sentinel-1-like scene with injected new structures, a flood, and vegetation
        growth — runs entirely locally, no Earth Engine account needed.
      </p>

      {errorMessage && <div className="error-banner">{errorMessage}</div>}

      <hr />

      <button className="link-btn" onClick={() => setGeeOpen(!geeOpen)}>
        {geeOpen ? "▾" : "▸"} Real Sentinel-1 via Google Earth Engine
      </button>

      {geeStatus && (
        <div className={`gee-status ${geeStatus.authenticated ? "ok" : "warn"}`}>
          {geeStatus.authenticated ? "✓ Earth Engine authenticated" : "⚠ " + geeStatus.message}
        </div>
      )}

      {geeOpen && (
        <div className="gee-form">
          <label>
            AOI geometry (GeoJSON Polygon)
            <textarea rows={6} value={aoiGeojsonText} onChange={(e) => setAoiGeojsonText(e.target.value)} />
          </label>
          <div className="controls-row">
            <label>
              Pre-change start
              <input type="date" value={preStart} onChange={(e) => setPreStart(e.target.value)} />
            </label>
            <label>
              Pre-change end
              <input type="date" value={preEnd} onChange={(e) => setPreEnd(e.target.value)} />
            </label>
          </div>
          <div className="controls-row">
            <label>
              Post-change start
              <input type="date" value={postStart} onChange={(e) => setPostStart(e.target.value)} />
            </label>
            <label>
              Post-change end
              <input type="date" value={postEnd} onChange={(e) => setPostEnd(e.target.value)} />
            </label>
          </div>
          {geeFormError && <div className="error-banner">{geeFormError}</div>}
          <button className="primary-btn secondary" disabled={loading || !geeStatus?.authenticated} onClick={submitGee}>
            {loading ? "Running…" : "Run on Real Sentinel-1 Data"}
          </button>
        </div>
      )}
    </div>
  );
}
