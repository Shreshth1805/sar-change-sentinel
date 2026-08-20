import { useState } from "react";
import { runGeeJob, runSyntheticJob, geojsonDownloadUrl } from "./api/client";
import AlertsPanel from "./components/AlertsPanel";
import AuditTrailPanel from "./components/AuditTrailPanel";
import MapView from "./components/MapView";
import PipelineControls from "./components/PipelineControls";
import RadarLoader from "./components/RadarLoader";
import StatsDashboard from "./components/StatsDashboard";
import UncertainPanel from "./components/UncertainPanel";
import type { JobResult } from "./types";

export default function App() {
  const [result, setResult] = useState<JobResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("scanning AOI");
  const [error, setError] = useState<string | null>(null);

  async function handleRunSynthetic(params: {
    aoiName: string;
    seed: number;
    width: number;
    height: number;
    originLat: number;
    originLon: number;
    numStructures: number;
  }) {
    setLoading(true);
    setLoadingLabel("generating synthetic scene");
    setError(null);
    try {
      const r = await runSyntheticJob({
        aoi_name: params.aoiName,
        seed: params.seed,
        width: params.width,
        height: params.height,
        origin_lat: params.originLat,
        origin_lon: params.originLon,
        num_structures: params.numStructures,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleRunGee(params: {
    aoiName: string;
    aoiGeojson: Record<string, unknown>;
    preStart: string;
    preEnd: string;
    postStart: string;
    postEnd: string;
    geeProjectId: string;
  }) {
    setLoading(true);
    setLoadingLabel("querying Earth Engine");
    setError(null);
    try {
      const r = await runGeeJob({
        aoi_name: params.aoiName,
        aoi_geojson: params.aoiGeojson,
        pre_start: params.preStart,
        pre_end: params.preEnd,
        post_start: params.postStart,
        post_end: params.postEnd,
        gee_project: params.geeProjectId || undefined,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const mapCenter: [number, number] | undefined = result?.aoi_center
    ? [result.aoi_center[1], result.aoi_center[0]]
    : result && result.alerts.length > 0
      ? [result.alerts[0].centroid[1], result.alerts[0].centroid[0]]
      : undefined;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand-mark-wrap">
            <svg className="brand-mark" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="50" cy="50" r="46" stroke="var(--panel-border)" strokeWidth="2" />
              <circle cx="50" cy="50" r="32" stroke="var(--accent)" strokeWidth="1.5" opacity="0.5" />
              <circle cx="50" cy="50" r="18" stroke="var(--accent)" strokeWidth="1.5" opacity="0.7" />
              <line x1="50" y1="50" x2="50" y2="6" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
              <circle cx="50" cy="50" r="4" fill="var(--accent)" />
            </svg>
          </div>
          <div className="brand-text">
            <h1>SAR Change Sentinel</h1>
            <span className="brand-tag">
              <span className="dot" /> {result ? `job ${result.job_id.slice(0, 8)}` : "awaiting run"}
            </span>
          </div>
        </div>
        {result && (
          <a className="download-btn" href={geojsonDownloadUrl(result.job_id)} download>
            ⬇ Download GeoJSON
          </a>
        )}
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <PipelineControls
            onRunSynthetic={handleRunSynthetic}
            onRunGee={handleRunGee}
            loading={loading}
            errorMessage={error}
          />
          <StatsDashboard stats={result?.stats ?? null} />
        </aside>

        <main className="map-area">
          <MapView geojson={result?.geojson ?? null} center={mapCenter} jobId={result?.job_id} />
          {loading && <RadarLoader label={loadingLabel} />}
        </main>

        <aside className="right-panel">
          <AlertsPanel alerts={result?.alerts ?? []} />
          <UncertainPanel blobs={result?.blobs ?? []} pixelAreaSqm={result?.stats.pixel_area_sqm ?? null} />
          <AuditTrailPanel steps={result?.audit_trail ?? []} />
        </aside>
      </div>
    </div>
  );
}
