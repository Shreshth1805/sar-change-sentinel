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

_UNSET = object()
# Tracks which project string ee.Initialize() last succeeded with, so a
# request for a *different* project re-initializes instead of silently
# reusing whatever project happened to be cached first.
_initialized_project: object = _UNSET


class GeeNotAuthenticatedError(RuntimeError):
    pass


class NoScenesFoundError(RuntimeError):
    """Raised when an Earth Engine collection query returns zero images for
    the requested AOI/date range. Deliberately fails loudly here rather than
    letting `.median()` on an empty collection silently produce a zero-band
    image — that failure mode surfaces many steps later as a confusing
    "wrong number of bands" array-shape error instead of the real cause."""

    pass


def ensure_initialized(project: str | None = None) -> None:
    global _initialized_project
    if _initialized_project is not _UNSET and _initialized_project == project:
        return
    try:
        import ee
    except ImportError as exc:  # pragma: no cover - dependency always in requirements.txt
        raise RuntimeError("earthengine-api is not installed; run pip install -r requirements.txt") from exc

    try:
        ee.Initialize(project=project)
    except Exception as exc:
        msg = str(exc)
        if "no project found" in msg.lower():
            raise GeeNotAuthenticatedError(
                "Earth Engine is authenticated but no Google Cloud project is linked. "
                "Register one (free) at https://code.earthengine.google.com/register, then "
                "find its project ID at https://console.cloud.google.com (top-left project "
                "picker) and pass it as the GEE project ID in the app. Original error: " + msg
            ) from exc
        raise GeeNotAuthenticatedError(
            "Google Earth Engine is not authenticated for this machine. Run "
            "`earthengine authenticate` in this venv once (opens a browser OAuth flow), "
            "then retry. Original error: " + msg
        ) from exc
    _initialized_project = project


def aoi_geometry(aoi_geojson: dict):
    import ee

    return ee.Geometry(aoi_geojson)


def get_sentinel1_composite(
    aoi_geojson: dict,
    start: date,
    end: date,
    polarizations: tuple[str, ...] = ("VV", "VH"),
    orbit_pass: str | None = None,
    project: str | None = None,
):
    """Median Sentinel-1 IW GRD composite over [start, end] clipped to the AOI.

    A median composite over the date range absorbs day-to-day noise and
    handles cases with more than one available pass, at the cost of
    temporal precision — callers wanting a single specific acquisition
    should narrow the date range to one pass.
    """
    import ee

    ensure_initialized(project=project)
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

    scene_count = collection.size().getInfo()
    if scene_count == 0:
        raise NoScenesFoundError(
            f"No Sentinel-1 scenes found over this AOI between {start} and {end}. "
            "Sentinel-1 revisits a given area roughly every 6-12 days depending on "
            "location — widen the date range and try again."
        )

    composite = collection.select(list(polarizations)).median().clip(geom)
    return composite


VEGETATION_SEARCH_WINDOW_DAYS = 45


def get_ancillary_masks(aoi_geojson: dict, as_of: date, project: str | None = None):
    """Server-side water / vegetation / slope masks for the AOI.

    - water: JRC Global Surface Water occurrence > 50% (permanent+seasonal water)
    - vegetation: NDVI > 0.3 from the least-cloudy Sentinel-2 SR scene within
      +/- 45 days of `as_of` that covers the AOI; if no scene exists in that
      window at all (rare, but happens for short pre/post gaps combined with
      persistent cloud cover), the vegetation mask degrades to all-False
      rather than crashing the whole job — natural-change suppression from
      other signals (water, shape, size) still applies.
    - slope: > 15 degrees from SRTM 30m DEM
    """
    import ee
    from datetime import timedelta

    ensure_initialized(project=project)
    geom = aoi_geometry(aoi_geojson)

    water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(50).unmask(0).clip(geom)

    window = timedelta(days=VEGETATION_SEARCH_WINDOW_DAYS)
    s2_collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(str(as_of - window), str(as_of + window))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    if s2_collection.size().getInfo() > 0:
        s2 = s2_collection.first()
        ndvi = ee.Image(s2).normalizedDifference(["B8", "B4"]).rename("NDVI")
        vegetation = ndvi.gt(0.3).unmask(0).clip(geom)
    else:
        vegetation = ee.Image(0).clip(geom)

    dem = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(dem).gt(15).unmask(0).clip(geom)

    return {"water": water, "vegetation": vegetation, "slope": slope}


def fetch_pipeline_inputs(
    aoi_geojson: dict,
    pre_start: date,
    pre_end: date,
    post_start: date,
    post_end: date,
    scale: float = 10.0,
    project: str | None = None,
) -> tuple[dict[str, np.ndarray], Affine, str]:
    """Fetch every pipeline input band (pre/post VV+VH, water, vegetation, slope)
    as ONE combined multi-band image and download it in a single call.

    This matters for correctness, not just efficiency: separate `ee_to_numpy`
    calls for the composite and each mask each let Earth Engine pick its own
    default output pixel grid, and different source datasets (Sentinel-1,
    Sentinel-2, SRTM, JRC surface water) don't share a native grid — so
    independently-downloaded arrays can come back at slightly different
    pixel dimensions and fail to stack. Combining every band into one
    `ee.Image` first forces Earth Engine to resample all of them onto a
    single common grid as part of the same request, which is the only way
    to guarantee the returned arrays are pixel-aligned.
    """
    ensure_initialized(project=project)

    pre = get_sentinel1_composite(aoi_geojson, pre_start, pre_end, project=project).rename(["pre_VV", "pre_VH"])
    post = get_sentinel1_composite(aoi_geojson, post_start, post_end, project=project).rename(
        ["post_VV", "post_VH"]
    )
    masks = get_ancillary_masks(aoi_geojson, post_end, project=project)

    band_order = ["pre_VV", "pre_VH", "post_VV", "post_VH", "water", "vegetation", "slope"]
    combined = (
        pre.addBands(post)
        .addBands(masks["water"].rename("water"))
        .addBands(masks["vegetation"].rename("vegetation"))
        .addBands(masks["slope"].rename("slope"))
    )

    arr, transform, crs = image_to_numpy(combined, aoi_geojson, scale=scale, project=project)
    if arr.ndim != 3 or arr.shape[-1] != len(band_order):
        raise ValueError(
            f"expected {len(band_order)} bands ({band_order}) from Earth Engine, got array shape {arr.shape}"
        )

    bands = {name: arr[..., i] for i, name in enumerate(band_order)}
    return bands, transform, crs


def image_to_numpy(
    image, aoi_geojson: dict, scale: float = 10.0, project: str | None = None
) -> tuple[np.ndarray, Affine, str]:
    """Download a (small) AOI's worth of pixels from an ee.Image as a numpy array.

    Returns (array, affine_transform, crs). Intended for AOI tiles on the
    order of a few km across at 10m resolution (a few hundred to ~2000px
    per side) — well within GEE's synchronous download limits and the
    right granularity for "monitor this facility/border segment", with
    many tiles run in parallel to cover a larger region.
    """
    import geemap

    ensure_initialized(project=project)
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
