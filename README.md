# SAR Change Sentinel

Automatic detection of **man-made changes** (new construction, roads,
structures) in Sentinel-1 SAR satellite imagery — while actively
suppressing **natural changes** (floods, water-level shifts, snow,
vegetation growth) to keep false alarms low. Output: georeferenced GeoJSON
polygons + a severity-rated alert feed, with a full audit trail explaining
every stage's decision.

Built for the NTRO problem statement *"Automatic Change Detection in
Synthetic Aperture Radar Satellite Images"* (Smart India Hackathon, Space
Technology category). See [`docs/PITCH.md`](docs/PITCH.md) for the
jury-facing narrative and demo script, and [`CLAUDE.md`](CLAUDE.md) for
the full architecture writeup.

## Quick start (no Google account needed)

The demo path uses a built-in synthetic Sentinel-1-like scene generator —
no Earth Engine account, no downloads, works fully offline.

**Backend:**
```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt
./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

**Frontend** (in a second terminal):
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and click **"Run Demo Scene"**. You'll see:
- A map with detected change polygons color-coded by classification
  (red = man-made, blue = natural/suppressed, yellow = uncertain)
- A stats panel and severity-rated alert feed
- An expandable audit trail showing every pipeline stage's exact output

## Running on real Sentinel-1 data

Requires a free [Google Earth Engine](https://earthengine.google.com/)
account. One-time setup:
```bash
cd backend
./.venv/Scripts/earthengine authenticate
```
This opens a browser OAuth flow. Once authenticated, open the "Real
Sentinel-1 via Google Earth Engine" panel in the UI, paste an AOI polygon
(GeoJSON), pick pre/post date ranges, and run.

## Tests

```bash
cd backend
./.venv/Scripts/python -m pytest tests/ -v
```
All 15 tests run against the synthetic generator — no external account
required to verify the detection algorithm.

## Project layout

```
backend/
  app/core/          # preprocessing, change detection, discrimination, postprocessing, alerts, GEE bridge
  app/synthetic/      # deterministic fake-SAR-scene generator (demo + tests)
  app/api/            # FastAPI routes
  tests/
frontend/
  src/components/     # MapView, AlertsPanel, AuditTrailPanel, StatsDashboard, PipelineControls
docs/
  PITCH.md            # SIH jury narrative + demo script
```
