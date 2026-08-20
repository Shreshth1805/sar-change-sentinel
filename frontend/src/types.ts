export type Classification = "man_made" | "natural" | "uncertain";
export type Severity = "low" | "medium" | "high";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface ChangeFeatureProperties {
  change_id: number | string;
  classification: Classification;
  confidence: number;
  area_px: number;
  area_sqm: number | null;
  reasons: string[];
  tile_index?: number;
}

export interface GeoJsonFeature {
  type: "Feature";
  geometry: { type: string; coordinates: unknown };
  properties: ChangeFeatureProperties;
}

export interface ChangeFeatureCollection {
  type: "FeatureCollection";
  crs: { type: string; properties: { name: string } };
  features: GeoJsonFeature[];
}

export interface Alert {
  alert_id: string;
  aoi_name: string;
  detected_at: string;
  severity: Severity;
  classification: Classification;
  confidence: number;
  area_sqm: number | null;
  centroid: [number, number];
  reasons: string[];
  geometry: { type: string; coordinates: unknown };
  tile_index?: number;
}

export interface Blob {
  label: number;
  area_px: number;
  bbox: number[];
  centroid: [number, number];
  shape_features: { compactness: number; solidity: number; extent: number };
  confidence: number;
  classification: Classification;
  reasons: string[];
  tile_index?: number;
}

export interface AuditStep {
  step_name: string;
  description: string;
  duration_ms: number;
  details: Record<string, unknown>;
  warnings: string[];
}

export interface PipelineStats {
  changed_pixel_fraction: number;
  total_blobs: number;
  classification_counts: Record<Classification, number>;
  alerts_generated: number;
  otsu_threshold: number;
  pixel_area_sqm: number | null;
}

export interface RegionTileOutcome {
  tile_index: number;
  row: number;
  col: number;
  bounds: [number, number, number, number]; // min_lon, min_lat, max_lon, max_lat
  status: "ok" | "failed";
  error?: string;
  stats?: PipelineStats;
}

export interface RegionMeta {
  grid_rows: number;
  grid_cols: number;
  tile_km: number;
  requested_tiles: number;
  processed_tiles: number;
  successful_tiles: number;
  failed_tiles: number;
  bounds: [number, number, number, number]; // min_lon, min_lat, max_lon, max_lat
  tiles: RegionTileOutcome[];
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  aoi_name: string;
  data_source?: "gee" | "synthetic";
  aoi_center?: [number, number];
  region?: RegionMeta;
  error?: string | null;
  geojson: ChangeFeatureCollection;
  alerts: Alert[];
  blobs: Blob[];
  audit_trail: AuditStep[];
  stats: PipelineStats;
}

export interface JobSummary {
  job_id: string;
  aoi_name: string;
  data_source: "gee" | "synthetic";
  status: JobStatus;
  created_at: string;
  stats: PipelineStats | null;
  error: string | null;
}
