import type { Alert, Classification, JobResult, JobSummary } from "../types";

// Kept in sync with backend/app/main.py's CORS allowlist (localhost:5173).
export const API_BASE = "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export interface SyntheticJobRequest {
  aoi_name: string;
  seed?: number;
  width?: number;
  height?: number;
  include_classifications?: Classification[];
}

export function runSyntheticJob(body: SyntheticJobRequest): Promise<JobResult> {
  return request<JobResult>("/api/jobs/synthetic", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface GeeJobRequest {
  aoi_name: string;
  aoi_geojson: Record<string, unknown>;
  pre_start: string;
  pre_end: string;
  post_start: string;
  post_end: string;
  scale_m?: number;
  gee_project?: string;
  include_classifications?: Classification[];
}

export function runGeeJob(body: GeeJobRequest): Promise<JobResult> {
  return request<JobResult>("/api/jobs/gee", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listJobs(): Promise<JobSummary[]> {
  return request<JobSummary[]>("/api/jobs");
}

export function getJob(jobId: string): Promise<JobResult> {
  return request<JobResult>(`/api/jobs/${jobId}`);
}

export function listAlerts(severity?: string): Promise<Alert[]> {
  const qs = severity ? `?severity=${severity}` : "";
  return request<Alert[]>(`/api/alerts${qs}`);
}

export function geojsonDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/geojson`;
}

export function getGeeStatus(): Promise<{ authenticated: boolean; message: string }> {
  return request("/api/gee/status");
}
