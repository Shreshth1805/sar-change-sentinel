import { useEffect } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";
import type { Layer, PathOptions } from "leaflet";
import type { Feature } from "geojson";
import type { ChangeFeatureCollection, Classification } from "../types";

const CLASSIFICATION_COLOR: Record<Classification, string> = {
  man_made: "#ff5a5f",
  natural: "#5fa8ff",
  uncertain: "#f5c542",
};

const DEFAULT_CENTER: [number, number] = [28.6139, 77.209]; // New Delhi

function styleForFeature(feature?: Feature): PathOptions {
  const cls = (feature?.properties?.classification ?? "uncertain") as Classification;
  return {
    color: CLASSIFICATION_COLOR[cls],
    weight: 2,
    fillColor: CLASSIFICATION_COLOR[cls],
    fillOpacity: 0.45,
  };
}

function bindPopup(feature: Feature, layer: Layer) {
  const p = feature.properties as Record<string, unknown> | null;
  if (!p) return;
  const reasons = Array.isArray(p.reasons) ? (p.reasons as string[]) : [];
  const area = p.area_sqm != null ? `${Math.round(p.area_sqm as number).toLocaleString()} m²` : "unknown area";
  const html = `
    <div class="change-popup">
      <strong>${String(p.classification).replace("_", " ").toUpperCase()}</strong>
      <div>confidence: ${((p.confidence as number) * 100).toFixed(0)}%</div>
      <div>${area}</div>
      <ul>${reasons.map((r) => `<li>${r}</li>`).join("")}</ul>
    </div>`;
  layer.bindPopup(html);
}

/** react-leaflet's `center`/`zoom` props on MapContainer only apply on the
 * initial mount — they're silently ignored on every prop update after that.
 * This imperatively pans/fits the already-mounted map whenever the target
 * changes. `bounds` (a region job's full tile-grid extent) takes priority
 * over `center`/`zoom` (a single-point AOI) when both are present. */
function RecenterOnChange({
  center,
  zoom,
  bounds,
}: {
  center: [number, number];
  zoom: number;
  bounds?: [[number, number], [number, number]];
}) {
  const map = useMap();
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [24, 24] });
    } else {
      map.setView(center, zoom);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center, zoom, bounds, map]);
  return null;
}

interface Props {
  geojson: ChangeFeatureCollection | null;
  center?: [number, number];
  /** [[south, west], [north, east]] — when set (region/tiled jobs), the map
   * fits this whole extent instead of centering on one point. */
  bounds?: [[number, number], [number, number]];
  /** Unique id of the current job/run — used to force the GeoJSON layer to
   * redraw with fresh data, since react-leaflet's <GeoJSON> doesn't react to
   * `data` prop changes on its own. */
  jobId?: string;
}

export default function MapView({ geojson, center, bounds, jobId }: Props) {
  const resolvedCenter = center ?? DEFAULT_CENTER;
  return (
    <MapContainer center={resolvedCenter} zoom={15} className="map-container">
      <RecenterOnChange center={resolvedCenter} zoom={15} bounds={bounds} />
      <TileLayer
        attribution='&copy; <a href="https://www.esri.com/">Esri</a> World Imagery'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      />
      {geojson && geojson.features.length > 0 && (
        <GeoJSON
          key={jobId ?? "empty"}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          data={geojson as any}
          style={styleForFeature}
          onEachFeature={bindPopup}
        />
      )}
    </MapContainer>
  );
}
