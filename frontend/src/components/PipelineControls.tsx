import { useEffect, useState } from "react";
import { getGeeStatus } from "../api/client";
import { bboxAroundPoint, type GeocodeResult } from "../api/geocode";
import LocationSearch from "./LocationSearch";

const DEFAULT_LAT = 28.6139; // New Delhi
const DEFAULT_LON = 77.209;
const DEFAULT_RADIUS_KM = 3;
// 10m/px (Sentinel-1-like); cap keeps the local pipeline snappy (~1s at the max).
const METERS_PER_PIXEL = 10;
const MAX_RADIUS_KM = 6;

function randomSeed(): number {
  return Math.floor(Math.random() * 1_000_000);
}

function structuresForRadius(radiusKm: number): number {
  return Math.min(12, Math.max(3, Math.round(radiusKm * 1.5)));
}

interface Props {
  onRunSynthetic: (params: {
    aoiName: string;
    seed: number;
    width: number;
    height: number;
    originLat: number;
    originLon: number;
    numStructures: number;
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

const EXAMPLE_AOI = JSON.stringify(bboxAroundPoint(DEFAULT_LAT, DEFAULT_LON, DEFAULT_RADIUS_KM), null, 2);

function shortName(displayName: string): string {
  return displayName.split(",")[0].trim();
}

export default function PipelineControls({ onRunSynthetic, onRunGee, loading, errorMessage }: Props) {
  const [aoiName, setAoiName] = useState("Demo AOI (New Delhi)");
  const [seed, setSeed] = useState(42);
  const [radiusKm, setRadiusKm] = useState(DEFAULT_RADIUS_KM);
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

  // Keep the GEE AOI box in sync with the current location + radius, so
  // dragging the radius slider updates it too, not just a fresh search.
  useEffect(() => {
    const lat = location?.lat ?? DEFAULT_LAT;
    const lon = location?.lon ?? DEFAULT_LON;
    setAoiGeojsonText(JSON.stringify(bboxAroundPoint(lat, lon, radiusKm), null, 2));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location, radiusKm]);

  function handleProjectIdChange(value: string) {
    setGeeProjectId(value);
    localStorage.setItem("geeProjectId", value);
  }

  function handleLocationSelect(place: GeocodeResult) {
    setLocation(place);
    setAoiName(`${shortName(place.displayName)} AOI`);
    setSeed(randomSeed()); // otherwise every city shows the exact same injected pattern
  }

  const sizePx = Math.round((radiusKm * 2 * 1000) / METERS_PER_PIXEL);
  const numStructures = structuresForRadius(radiusKm);

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
          <div className="location-search-row">
            <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
            <button className="secondary-btn" onClick={() => setSeed(randomSeed())} title="Randomize pattern">
              🎲
            </button>
          </div>
        </label>
        <label>
          Coverage radius (km)
          <input
            type="number"
            min={1}
            max={MAX_RADIUS_KM}
            step={0.5}
            value={radiusKm}
            onChange={(e) => setRadiusKm(Math.min(MAX_RADIUS_KM, Math.max(1, Number(e.target.value))))}
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
            width: sizePx,
            height: sizePx,
            originLat: location?.lat ?? DEFAULT_LAT,
            originLon: location?.lon ?? DEFAULT_LON,
            numStructures,
          })
        }
      >
        {loading ? "Running…" : "Run Demo Scene"}
      </button>
      <p className="hint">
        Generates a synthetic Sentinel-1-like scene covering a {(radiusKm * 2).toFixed(1)}km-wide area
        centered on the searched location (or New Delhi by default), scattering {numStructures} injected new
        structures across it alongside a flood and vegetation growth — runs entirely locally, no Earth Engine
        account needed. The seed randomizes on every new search so different cities don't show the identical
        pattern; use 🎲 to reroll the current one.
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
            AOI box tracks the coverage radius above ({(radiusKm * 2).toFixed(1)}km wide) — search a city or
            adjust the radius to resize it, or paste your own GeoJSON polygon. A single request can't safely
            cover an entire city or state at once (that's hundreds of megapixels of real Sentinel-1 data); for
            that you'd tile it into several AOI-sized requests like this one rather than one giant call.
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
