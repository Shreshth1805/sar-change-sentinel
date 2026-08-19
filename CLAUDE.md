# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**SAR Change Sentinel**: automatic detection of man-made changes (new
construction, roads, structures) in Sentinel-1 SAR satellite imagery, while
actively suppressing natural changes (floods, water-level shifts, snow,
vegetation growth/die-back) to keep false alarms low. Built for the NTRO
problem statement "Automatic Change Detection in Synthetic Aperture Radar
Satellite Images" (Smart India Hackathon, Space Technology category).
Output is georeferenced GeoJSON polygons plus a structured alert feed.

The central design constraint, mirrored from how this problem statement is
scored: **every stage must explain itself**. There is no black-box "trust
the model" step — the discrimination stage (`app/core/discrimination.py`)
scores every candidate change blob against explicit physical evidence
(water/vegetation/slope overlap, shape regularity, size) and records a
plain-English reason for every point added or subtracted. Combined with the
per-stage `StepReport` audit trail (`app/core/audit.py`), any alert can be
traced back to exactly why it fired — this is what "minimum false alarms"
means operationally, not just a metric.

`backend/` is a FastAPI service wrapping a numpy/scikit-image SAR
processing pipeline, with a Google Earth Engine bridge for real Sentinel-1
data (usable standalone as a library too). `frontend/` is a React +
TypeScript (Vite) map dashboard that drives it.

## Commands

Backend (Python 3.11+). Always use the venv at `backend/.venv`:
```bash
cd backend
python -m venv .venv                                    # first time only
./.venv/Scripts/pip install -r requirements.txt          # first time / after requirements.txt changes
./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000   # dev server
./.venv/Scripts/python -m pytest tests/ -v                             # all tests (no GEE account needed — synthetic data only)
```

Frontend (Node):
```bash
cd frontend
npm install
npm run dev          # Vite dev server, http://localhost:5173
npm run build         # tsc -b && vite build (also serves as the typecheck step)
```

The frontend's API base URL is hardcoded in `frontend/src/api/client.ts`
(`API_BASE = "http://127.0.0.1:8000"`) — the backend must be running there.
CORS in `backend/app/main.py` only allows `localhost:5173`/`127.0.0.1:5173`.

### Google Earth Engine (optional, for real Sentinel-1 data)

Everything above works with zero external accounts via the synthetic scene
generator (`app/synthetic/generator.py`) — the whole pipeline, tests, and
UI demo path use it by default. To run against real Sentinel-1 imagery via
`POST /api/jobs/gee`, authenticate once in the backend venv:
```bash
cd backend
./.venv/Scripts/earthengine authenticate
```
This opens an interactive Google OAuth flow; there is no way to do this
non-interactively on the user's behalf. `GET /api/gee/status` reports
whether this machine is authenticated.

## Architecture

### Pipeline stage contract (`backend/app/core/`)

Every stage takes plain numpy arrays / dicts and returns
`(result, StepReport)` via `app.core.audit.run_step`, which times the stage
and wraps its `(result, details, warnings)` into a `StepReport`. Fixed
order, orchestrated by `app/core/pipeline.py::run_pipeline`:

1. **`preprocessing.py`** — adaptive Lee speckle filter on the pre/post SAR
   intensity pair. SAR speckle is multiplicative, not additive; Lee
   filtering blends each pixel toward the local mean in proportion to local
   homogeneity, preserving edges instead of blurring uniformly.
2. **`change_detection.py`** — log-ratio (single-pol) or Change Vector
   Analysis magnitude (dual-pol VV+VH), then Otsu-adaptive thresholding.
   Log-ratio turns multiplicative speckle noise into roughly-constant-
   variance additive noise, which is why one global threshold works
   reasonably well scene-wide — this is standard SAR change-detection
   literature (Bazi et al., Bruzzone & Prieto), not a heuristic invented
   for this project.
3. **`postprocessing.cleanup_mask`** — binary opening + small-object
   removal. This is the primary lever against speckle-scale false alarms,
   applied *before* blobs are scored.
4. **`discrimination.py`** — the false-alarm-suppression core. Labels
   connected components and scores each for man-made likelihood using
   shape features (compactness, solidity — built structures are compact
   and convex; floods/vegetation are sprawling) plus ancillary land-cover
   masks (water/vegetation/slope overlap). Every scoring adjustment is
   logged as a plain-English reason string — same "no unexplained numbers"
   philosophy as a scoring system you'd want a human to be able to audit.
5. **`postprocessing.to_geojson`** — vectorizes classified blobs into a
   georeferenced `FeatureCollection` via `rasterio.features.shapes` and
   the raster's affine transform. `include_classifications` (default:
   `("man_made",)`) is where "ignore natural changes" takes effect on the
   actual deliverable, not just in scoring.
6. **`alerts.py`** — turns confirmed-man-made polygons into severity-rated
   alert records (area + confidence driven).

Never mutate input arrays in place; always surface what changed via
`details`/`warnings`. This is the pattern to follow for any new stage.

### Data access: synthetic vs. Google Earth Engine (`gee_client.py`, `synthetic/generator.py`)

Two interchangeable sources of pre/post VV+VH arrays + water/vegetation/
slope masks, both producing the exact same shape of input the pipeline
expects:

- **`synthetic/generator.py`** generates a deterministic (seeded), 
  physically-motivated fake Sentinel-1 scene: gamma-distributed
  multiplicative speckle at Sentinel-1's nominal ENL, a water body, a
  vegetation patch, and *injected* man-made changes (compact bright
  rectangles) alongside *injected* natural changes (flood expansion,
  vegetation growth) in the same scene — adversarial by construction, so a
  pipeline that can't actually discriminate visibly fails on it. Used by
  the test suite and the default UI demo path; needs no network access or
  credentials.
- **`gee_client.py`** pulls real Sentinel-1 GRD median composites (already
  radiometrically calibrated + terrain-corrected by GEE), JRC Global
  Surface Water occurrence, Sentinel-2-derived NDVI, and SRTM slope for a
  given AOI/date range, then downloads that AOI's pixels as numpy via
  `geemap.ee_to_numpy`. This is *why* the pipeline can claim "scalable to
  huge areas" without us hosting a Sentinel-1 archive ourselves: GEE has
  already solved the volume/mosaicking problem, and scaling to a huge
  region is an AOI-tiling concern (many independent parallel jobs, one per
  tile) rather than a raw-data-volume one.

### API / job layer

`services/job_store.py` is an in-memory `dict[job_id, ChangeDetectionJob]`
(single-process, no persistence — same pattern as a typical FastAPI demo
session store). `api/routes_jobs.py` exposes `POST /api/jobs/synthetic`
(instant, no auth) and `POST /api/jobs/gee` (real data, requires Earth
Engine auth, returns HTTP 428 with instructions if not authenticated) plus
job lookup and GeoJSON download; `api/routes_alerts.py` lists alerts across
all jobs; `api/routes_gee.py` reports auth status. `api/serialization.py`
strips the numpy pixel-coordinate arrays pipeline internals carry before
anything crosses the JSON boundary — `types.ts` on the frontend mirrors
exactly what's left after that strip.

### Frontend

`App.tsx` owns all state (current job result, loading/error) and passes it
down — no separate state management library, same pattern as a typical
small React dashboard. `api/client.ts` is the only place that talks to the
backend. `MapView.tsx` renders the GeoJSON change polygons over an Esri
World Imagery basemap via `react-leaflet`, color-coded by classification,
with a popup showing confidence + reasons per polygon. `AuditTrailPanel.tsx`
exposes the full per-stage `StepReport` list so a viewer can expand any
stage and see exactly what it did — this is deliberately not hidden behind
a "details" toggle buried three clicks deep, since the audit trail is a
core part of the product's credibility story.
