import { useState } from "react";
import { runGeeJob, runSyntheticJob, geojsonDownloadUrl } from "./api/client";
import AlertsPanel from "./components/AlertsPanel";
import AuditTrailPanel from "./components/AuditTrailPanel";
import MapView from "./components/MapView";
import PipelineControls from "./components/PipelineControls";
import StatsDashboard from "./components/StatsDashboard";
import UncertainPanel from "./components/UncertainPanel";
import type { JobResult } from "./types";

export default function App() {
  const [result, setResult] = useState<JobResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRunSynthetic(params: {
    aoiName: string;
    seed: number;
    width: number;
    height: number;
    originLat: number;
    originLon: number;
  }) {
    setLoading(true);
    setError(null);
    try {
      const r = await runSyntheticJob({
        aoi_name: params.aoiName,
        seed: params.seed,
        width: params.width,
        height: params.height,
        origin_lat: params.originLat,
        origin_lon: params.originLon,
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
        <div>
          <h1>SAR Change Sentinel</h1>
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
          <MapView geojson={result?.geojson ?? null} center={mapCenter} />
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
