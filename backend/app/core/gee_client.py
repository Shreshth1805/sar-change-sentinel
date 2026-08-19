"""Google Earth Engine bridge — real Sentinel-1/2/SRTM data access.

This is the module that gives the "scalable to huge areas" requirement
teeth: instead of us managing petabytes of raw Sentinel-1 downloads, GEE
holds the entire archive and does the filtering/mosaicking/masking
server-side across however large an AOI is requested. What we pull back
locally is only the small georeferenced raster needed to run the audited
numpy pipeline in `app/core/pipeline.py` on one AOI tile. Scaling to a
huge region is then an AOI-tiling concern (many independent, parallelizable
jobs, one per tile) rather than a raw-data-volume problem — GEE has
already solved the volume problem for us.

Requires the user to have authenticated once locally:
    earthengine authenticate
(interactive OAuth flow — this module cannot and does not do that on the
user's behalf). If that hasn't been done, `ensure_initialized` raises
`GeeNotAuthenticatedError` with the exact command to run.
"""

from __future__ import annotations

from datetime import date

import numpy as np
from affine import Affine

_initialized = False


class GeeNotAuthenticatedError(RuntimeError):
    pass


def ensure_initialized(project: str | None = None) -> None:
    global _initialized
    if _initialized:
        return
    try:
        import ee
    except ImportError as exc:  # pragma: no cover - dependency always in requirements.txt
        raise RuntimeError("earthengine-api is not installed; run pip install -r requirements.txt") from exc

    try:
        ee.Initialize(project=project)
    except Exception as exc:
        raise GeeNotAuthenticatedError(
            "Google Earth Engine is not authenticated for this machine. Run "
            "`earthengine authenticate` in this venv once (opens a browser OAuth flow), "
            "then retry. Original error: " + str(exc)
        ) from exc
    _initialized = True


def aoi_geometry(aoi_geojson: dict):
    import ee

    return ee.Geometry(aoi_geojson)


def get_sentinel1_composite(
    aoi_geojson: dict,
    start: date,
    end: date,
    polarizations: tuple[str, ...] = ("VV", "VH"),
    orbit_pass: str | None = None,
):
    """Median Sentinel-1 IW GRD composite over [start, end] clipped to the AOI.

    A median composite over the date range absorbs day-to-day noise and
    handles cases with more than one available pass, at the cost of
    temporal precision — callers wanting a single specific acquisition
    should narrow the date range to one pass.
    """
    import ee

    ensure_initialized()
    geom = aoi_geometry(aoi_geojson)

    collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(geom)
        .filterDate(str(start), str(end))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )
    for pol in polarizations:
        collection = collection.filter(ee.Filter.listContains("transmitterReceiverPolarisation", pol))
    if orbit_pass:
        collection = collection.filter(ee.Filter.eq("orbitProperties_pass", orbit_pass))

    composite = collection.select(list(polarizations)).median().clip(geom)
    return composite


def get_ancillary_masks(aoi_geojson: dict, as_of: date):
    """Server-side water / vegetation / slope masks for the AOI.

    - water: JRC Global Surface Water occurrence > 50% (permanent+seasonal water)
    - vegetation: NDVI > 0.3 from the least-cloudy Sentinel-2 SR scene within
      +/- 30 days of `as_of` that covers the AOI
    - slope: > 15 degrees from SRTM 30m DEM
    """
    import ee

    ensure_initialized()
    geom = aoi_geometry(aoi_geojson)

    water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(50).unmask(0).clip(geom)

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(str(as_of.replace(day=1)), str(as_of))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
        .first()
    )
    ndvi = ee.Image(s2).normalizedDifference(["B8", "B4"]).rename("NDVI")
    vegetation = ndvi.gt(0.3).unmask(0).clip(geom)

    dem = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(dem).gt(15).unmask(0).clip(geom)

    return {"water": water, "vegetation": vegetation, "slope": slope}


def image_to_numpy(image, aoi_geojson: dict, scale: float = 10.0) -> tuple[np.ndarray, Affine, str]:
    """Download a (small) AOI's worth of pixels from an ee.Image as a numpy array.

    Returns (array, affine_transform, crs). Intended for AOI tiles on the
    order of a few km across at 10m resolution (a few hundred to ~2000px
    per side) — well within GEE's synchronous download limits and the
    right granularity for "monitor this facility/border segment", with
    many tiles run in parallel to cover a larger region.
    """
    import geemap

    ensure_initialized()
    geom = aoi_geometry(aoi_geojson)
    arr = geemap.ee_to_numpy(image, region=geom, scale=scale)
    if arr is None:
        raise ValueError("Earth Engine returned no pixels for this AOI/date range/band combination")

    bounds = geom.bounds().getInfo()["coordinates"][0]
    lons = [c[0] for c in bounds]
    lats = [c[1] for c in bounds]
    min_lon, max_lat = min(lons), max(lats)
    deg_per_m = 1.0 / 111_320.0
    px_deg = scale * deg_per_m
    transform = Affine.translation(min_lon, max_lat) * Affine.scale(px_deg, -px_deg)

    return arr, transform, "EPSG:4326"
