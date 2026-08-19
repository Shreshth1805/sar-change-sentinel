export type Classification = "man_made" | "natural" | "uncertain";
export type Severity = "low" | "medium" | "high";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface ChangeFeatureProperties {
  change_id: number;
  classification: Classification;
  confidence: number;
  area_px: number;
  area_sqm: number | null;
  reasons: string[];
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
}

export interface JobResult {
  job_id: string;
  status: JobStatus;
  aoi_name: string;
  data_source?: "gee" | "synthetic";
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
