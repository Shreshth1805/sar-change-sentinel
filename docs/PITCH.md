# SAR Change Sentinel — Pitch & Demo Script

## Problem statement (as given)

> Automatic Change Detection in Synthetic Aperture Radar Satellite Images
> — NTRO, Space Technology. Detect man-made changes while ignoring natural
> changes (floods, water-level changes, snow, vegetation). Must scale to
> huge areas, minimize false alarms, and output georeferenced
> polygons/GeoJSON/shapefiles with alerts.

Four requirements are doing the real work here, and each one maps to a
specific decision in this system:

| Requirement | What breaks a naive solution | What we did |
|---|---|---|
| Detect *man-made* change | A plain pixel-difference/log-ratio flags **everything** that changed — floods and crop cycles included | A dedicated discrimination stage scores every change blob against physical evidence, not raw magnitude |
| *Ignore* natural change | Hard-coding "flood = water-colored pixels" doesn't generalize | Ancillary land-cover masks (JRC surface water, Sentinel-2 NDVI, SRTM slope) plus shape geometry, each with an explainable weight |
| Scale to huge areas | Downloading raw Sentinel-1 pixels for a whole state/country is a data-engineering project on its own | Google Earth Engine holds and mosaics the archive server-side; we only pull the small AOI tile we need, so scaling out is "run more tiles in parallel," not "manage petabytes" |
| Minimum false alarms | A black-box classifier's false positives are unactionable — an operator can't tell *why* it fired | Every blob carries plain-English reasons ("62% overlap with surface-water mask") and a full per-stage audit trail, so every alert is traceable to physical evidence |

## Why this design wins on the things a jury actually scores

**1. It's not "yet another CNN change-detector."** Deep-learning SAR
change detection is well-trodden ground, and without a large labeled
man-made-change dataset (which doesn't really exist publicly at scale),
training one is either infeasible in a hackathon timeframe or quietly
overfit to a toy dataset. We instead built a physically-grounded,
explainable pipeline — log-ratio/CVA change detection (standard SAR
literature) into an evidence-weighted discrimination stage. It's
defensible in a Q&A: every number a judge asks about has a physical
justification, not a "the model learned it" shrug.

**2. The false-alarm story is concrete, not a slide claim.** Run the demo:
the synthetic scene injects three new structures *and* a flood *and*
vegetation growth into the same scene. Watch the flood and vegetation
blobs get scored `natural` and dropped from the GeoJSON, while the
structures survive as `man_made` alerts with a stated reason. That's the
requirement, demonstrated live, not asserted.

**3. Scalability has a real mechanism, not a buzzword.** "We'll use Earth
Engine" is a common hackathon line; the credible version of that claim is
explaining *why* it makes huge-area processing tractable (GEE's own
compute handles the archive-scale mosaicking/filtering; our job is only
AOI-tile orchestration) — which is what `CLAUDE.md`'s architecture section
and `gee_client.py` actually implement, not just reference.

**4. Auditability is a feature the problem statement didn't explicitly
ask for but every operational deployment needs.** An analyst triaging
alerts from a live system needs to know why a polygon fired before acting
on it. The `AuditTrailPanel` and per-blob `reasons` array exist because a
real NTRO deployment is worthless if operators can't trust or debug it.

## Demo script (~3 minutes)

1. **Open the dashboard.** Point out the map, the empty stats/alerts
   panels — nothing has run yet.
2. **Click "Run Demo Scene."** Narrate while it runs (it's near-instant):
   *"This synthetic scene has three new structures, a flood, and
   vegetation growth injected into it — deliberately adversarial, so we
   can see the false-alarm suppression working, not just the detection."*
3. **Point at the map.** Red polygon(s) = man-made, confirmed. Note that
   the flood and vegetation regions do **not** appear as red — open the
   audit trail's `discriminate_man_made_vs_natural` step to show the
   `classification_counts` breakdown (e.g. `man_made: 1, natural: 3`).
4. **Click a red polygon.** Show the popup: classification, confidence,
   area in m², and the reason ("compact, near-convex footprint...").
5. **Open the Alerts panel.** Point out the severity rating (area +
   confidence driven) and the georeferenced centroid.
6. **Download GeoJSON.** *"This is the actual deliverable format the
   problem statement asks for — ready to load into any GIS tool."*
7. **(If time / GEE is authenticated) Switch to the real-data panel** and
   run against an actual Sentinel-1 AOI to show it isn't a synthetic-only
   toy.
8. **Close on the architecture, not just the demo:** the fixed audited
   pipeline order, the AOI-tiling scalability story, and the fact that
   every alert is traceable to physical evidence.

## Honest limitations (be ready for this question)

- The discrimination stage is rule-based/evidence-weighted, not a trained
  classifier — a deliberate choice given no large labeled man-made-change
  dataset exists publicly, but it means thresholds are hand-tuned rather
  than learned. A natural v2: collect labeled polygons from operator
  feedback and train a calibrated classifier (e.g. gradient-boosted trees)
  on the same feature set, keeping the reasons for explainability.
- Coregistration between pre/post scenes is assumed (GEE composites over
  the same AOI are naturally aligned); a production system ingesting
  scenes from different orbits/geometries would need an explicit
  coregistration step.
- The GEE path downloads AOI-tile pixels synchronously; a production
  deployment would move `POST /api/jobs/gee` to a background task queue
  so very large AOIs (many tiles) don't block a request thread.

## One-line elevator pitch

*"We built an explainable SAR change-detection pipeline that tells you not
just where something changed, but why we believe it was man-made — with
every false-alarm-suppression decision traceable to a specific piece of
physical evidence, and an architecture that scales by tiling AOIs across
Google Earth Engine's own planetary-scale compute instead of us managing
the raw archive."*
