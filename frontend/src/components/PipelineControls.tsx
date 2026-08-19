import { useEffect, useState } from "react";
import { getGeeStatus } from "../api/client";
import { bboxAroundPoint, type GeocodeResult } from "../api/geocode";
import LocationSearch from "./LocationSearch";

const DEFAULT_LAT = 28.6139; // New Delhi
const DEFAULT_LON = 77.209;

interface Props {
  onRunSynthetic: (params: {
    aoiName: string;
    seed: number;
    width: number;
    height: number;
    originLat: number;
    originLon: number;
  }) => void;
  onRunGee: (params: {
    aoiName: string;
    aoiGeojson: Record<string, unknown>;
    preStart: string;
    preEnd: string;
    postStart: string;
    postEnd: string;
    geeProjectId: string;
  }) => void;
  loading: boolean;
  errorMessage: string | null;
}

const EXAMPLE_AOI = JSON.stringify(bboxAroundPoint(DEFAULT_LAT, DEFAULT_LON), null, 2);

function shortName(displayName: string): string {
  return displayName.split(",")[0].trim();
}

export default function PipelineControls({ onRunSynthetic, onRunGee, loading, errorMessage }: Props) {
  const [aoiName, setAoiName] = useState("Demo AOI (New Delhi)");
  const [seed, setSeed] = useState(42);
  const [size, setSize] = useState(200);
  const [location, setLocation] = useState<GeocodeResult | null>(null);

  const [geeStatus, setGeeStatus] = useState<{ authenticated: boolean; message: string } | null>(null);
  const [geeStatusChecking, setGeeStatusChecking] = useState(false);
  const [geeProjectId, setGeeProjectId] = useState(() => localStorage.getItem("geeProjectId") ?? "");
  const [aoiGeojsonText, setAoiGeojsonText] = useState(EXAMPLE_AOI);
  const [preStart, setPreStart] = useState("2024-01-01");
  const [preEnd, setPreEnd] = useState("2024-01-31");
  const [postStart, setPostStart] = useState("2024-06-01");
  const [postEnd, setPostEnd] = useState("2024-06-30");
  const [geeFormError, setGeeFormError] = useState<string | null>(null);
  const [geeOpen, setGeeOpen] = useState(false);

  function checkGeeStatus(project: string) {
    setGeeStatusChecking(true);
    getGeeStatus(project || undefined)
      .then(setGeeStatus)
      .catch(() => setGeeStatus({ authenticated: false, message: "Could not reach backend." }))
      .finally(() => setGeeStatusChecking(false));
  }

  useEffect(() => {
    checkGeeStatus(geeProjectId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleProjectIdChange(value: string) {
    setGeeProjectId(value);
    localStorage.setItem("geeProjectId", value);
  }

  function handleLocationSelect(place: GeocodeResult) {
    setLocation(place);
    setAoiName(`${shortName(place.displayName)} AOI`);
    setAoiGeojsonText(JSON.stringify(bboxAroundPoint(place.lat, place.lon), null, 2));
  }

  function submitGee() {
    try {
      const parsed = JSON.parse(aoiGeojsonText);
      setGeeFormError(null);
      onRunGee({ aoiName, aoiGeojson: parsed, preStart, preEnd, postStart, postEnd, geeProjectId });
    } catch {
      setGeeFormError("AOI must be valid GeoJSON geometry (a Polygon).");
    }
  }

  return (
    <div className="panel controls-panel">
      <h3>Run Detection</h3>

      <LocationSearch onSelect={handleLocationSelect} selected={location} />

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
        onClick={() =>
          onRunSynthetic({
            aoiName,
            seed,
            width: size,
            height: size,
            originLat: location?.lat ?? DEFAULT_LAT,
            originLon: location?.lon ?? DEFAULT_LON,
          })
        }
      >
        {loading ? "Running…" : "Run Demo Scene"}
      </button>
      <p className="hint">
        Generates a synthetic Sentinel-1-like scene centered on the searched location (or New Delhi by
        default), with injected new structures, a flood, and vegetation growth — runs entirely locally, no
        Earth Engine account needed.
      </p>

      {errorMessage && <div className="error-banner">{errorMessage}</div>}

      <hr />

      <button className="link-btn" onClick={() => setGeeOpen(!geeOpen)}>
        {geeOpen ? "▾" : "▸"} Real Sentinel-1 via Google Earth Engine
      </button>

      {geeOpen && (
        <div className="gee-form">
          <label>
            GEE Cloud project ID
            <div className="location-search-row">
              <input
                value={geeProjectId}
                placeholder="e.g. ee-yourname"
                onChange={(e) => handleProjectIdChange(e.target.value)}
              />
              <button
                className="secondary-btn"
                disabled={geeStatusChecking}
                onClick={() => checkGeeStatus(geeProjectId)}
              >
                {geeStatusChecking ? "…" : "Check"}
              </button>
            </div>
          </label>

          {geeStatus && (
            <div className={`gee-status ${geeStatus.authenticated ? "ok" : "warn"}`}>
              {geeStatus.authenticated ? "✓ Earth Engine authenticated" : "⚠ " + geeStatus.message}
            </div>
          )}

          <p className="hint">
            Newer Earth Engine accounts need a linked Google Cloud project. Register free at{" "}
            <a href="https://code.earthengine.google.com/register" target="_blank" rel="noreferrer">
              code.earthengine.google.com/register
            </a>
            , then find the project ID in the{" "}
            <a href="https://console.cloud.google.com" target="_blank" rel="noreferrer">
              Cloud Console
            </a>{" "}
            project picker (top-left) and paste it above.
          </p>
          <p className="hint">
            Search a city or country above to auto-fill a ~3km AOI box below, or paste your own GeoJSON
            polygon.
          </p>
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
