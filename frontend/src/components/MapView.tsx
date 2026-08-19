import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
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

interface Props {
  geojson: ChangeFeatureCollection | null;
  center?: [number, number];
}

export default function MapView({ geojson, center }: Props) {
  return (
    <MapContainer
      center={center ?? DEFAULT_CENTER}
      zoom={15}
      className="map-container"
      key={geojson ? JSON.stringify(geojson.features.length) : "empty"}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.esri.com/">Esri</a> World Imagery'
        url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
      />
      {geojson && geojson.features.length > 0 && (
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        <GeoJSON data={geojson as any} style={styleForFeature} onEachFeature={bindPopup} />
      )}
    </MapContainer>
  );
}
