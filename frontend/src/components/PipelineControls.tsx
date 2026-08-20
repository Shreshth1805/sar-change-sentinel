import { useEffect, useState } from "react";
import { getGeeStatus } from "../api/client";
import { bboxAroundPoint, estimateTileGrid, regionPolygonFromBoundingBox, type GeocodeResult } from "../api/geocode";
import LocationSearch from "./LocationSearch";

const DEFAULT_LAT = 28.6139; // New Delhi
const DEFAULT_LON = 77.209;
const DEFAULT_RADIUS_KM = 3;
// 10m/px (Sentinel-1-like); cap keeps the local pipeline snappy (~1s at the max).
const METERS_PER_PIXEL = 10;
const MAX_RADIUS_KM = 6;
// Kept in sync with backend/app/api/routes_jobs.py's MAX_SYNTHETIC_REGION_TILES
// / MAX_GEE_REGION_TILES — synthetic tiles are cheap (~1s), GEE tiles each make
// several real network calls (~10-20s), hence the much smaller real-data cap.
const MAX_SYNTHETIC_REGION_TILES = 25;
const MAX_GEE_REGION_TILES = 9;

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
  onRunSyntheticRegion: (params: {
    aoiName: string;
    aoiGeojson: Record<string, unknown>;
    baseSeed: number;
    tileKm: number;
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
  onRunGeeRegion: (params: {
    aoiName: string;
    aoiGeojson: Record<string, unknown>;
    preStart: string;
    preEnd: string;
    postStart: string;
    postEnd: string;
    geeProjectId: string;
    tileKm: number;
  }) => void;
  loading: boolean;
  errorMessage: string | null;
}

const EXAMPLE_AOI = JSON.stringify(bboxAroundPoint(DEFAULT_LAT, DEFAULT_LON, DEFAULT_RADIUS_KM), null, 2);

function shortName(displayName: string): string {
  return displayName.split(",")[0].trim();
}

export default function PipelineControls({
  onRunSynthetic,
  onRunSyntheticRegion,
  onRunGee,
  onRunGeeRegion,
  loading,
  errorMessage,
}: Props) {
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
  const tileKm = radiusKm * 2;

  const syntheticRegionEstimate = location
    ? estimateTileGrid(location.boundingBox, tileKm, MAX_SYNTHETIC_REGION_TILES)
    : null;
  const geeRegionEstimate = location ? estimateTileGrid(location.boundingBox, tileKm, MAX_GEE_REGION_TILES) : null;

  function runSyntheticRegion() {
    if (!location) return;
    onRunSyntheticRegion({
      aoiName: `${aoiName} (full area)`,
      aoiGeojson: regionPolygonFromBoundingBox(location.boundingBox),
      baseSeed: seed,
      tileKm,
    });
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

  function submitGeeRegion() {
    if (!location) return;
    onRunGeeRegion({
      aoiName: `${aoiName} (full area)`,
      aoiGeojson: regionPolygonFromBoundingBox(location.boundingBox),
      preStart,
      preEnd,
      postStart,
      postEnd,
      geeProjectId,
      tileKm,
    });
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
          Tile size (km)
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

      {location && syntheticRegionEstimate && (
        <div className="region-box">
          <div className="region-box-label">Cover the entire searched area</div>
          <div className="region-box-estimate">
            {syntheticRegionEstimate.rows}×{syntheticRegionEstimate.cols} grid of {tileKm.toFixed(1)}km tiles (
            {syntheticRegionEstimate.processedTiles} tile{syntheticRegionEstimate.processedTiles === 1 ? "" : "s"}
            {syntheticRegionEstimate.requestedTiles > syntheticRegionEstimate.processedTiles
              ? `, capped from ${syntheticRegionEstimate.requestedTiles} — a centered subset is shown`
              : ""}
            )
          </div>
          <button className="primary-btn secondary" disabled={loading} onClick={runSyntheticRegion}>
            {loading ? "Running…" : `Cover Entire ${shortName(location.displayName)} (Demo, tiled)`}
          </button>
        </div>
      )}

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
            AOI box tracks the tile size above ({(radiusKm * 2).toFixed(1)}km wide) — search a city or adjust
            the size to resize it, or paste your own GeoJSON polygon.
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

          {location && geeRegionEstimate && (
            <div className="region-box">
              <div className="region-box-label">Cover the entire searched area (real data)</div>
              <div className="region-box-estimate">
                {geeRegionEstimate.rows}×{geeRegionEstimate.cols} grid of {tileKm.toFixed(1)}km tiles (
                {geeRegionEstimate.processedTiles} tile{geeRegionEstimate.processedTiles === 1 ? "" : "s"}
                {geeRegionEstimate.requestedTiles > geeRegionEstimate.processedTiles
                  ? `, capped from ${geeRegionEstimate.requestedTiles} — a centered subset is shown`
                  : ""}
                ) — each tile is a real Earth Engine fetch, so this can take a while
              </div>
              <button
                className="primary-btn secondary"
                disabled={loading || !geeStatus?.authenticated}
                onClick={submitGeeRegion}
              >
                {loading ? "Running…" : `Cover Entire ${shortName(location.displayName)} (Real Data, tiled)`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
