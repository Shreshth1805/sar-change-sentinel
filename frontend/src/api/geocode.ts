// Client-side place lookup via OpenStreetMap's Nominatim search API — public,
// no API key, CORS-enabled. Used only to turn "city or country name" into a
// lat/lon (and a rough bounding box for the GEE AOI) so the demo isn't
// hardcoded to New Delhi. Nominatim's usage policy caps this at ~1 request/sec
// for interactive use, which a single user typing in a search box satisfies.
const NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search";

export interface GeocodeResult {
  displayName: string;
  lat: number;
  lon: number;
  /** [south, north, west, east] in degrees */
  boundingBox: [number, number, number, number];
}

export async function searchPlace(query: string): Promise<GeocodeResult[]> {
  const url = `${NOMINATIM_BASE}?format=json&limit=5&q=${encodeURIComponent(query)}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    throw new Error(`Place search failed: ${res.status} ${res.statusText}`);
  }
  const raw = (await res.json()) as Array<{
    display_name: string;
    lat: string;
    lon: string;
    boundingbox: [string, string, string, string];
  }>;
  return raw.map((r) => ({
    displayName: r.display_name,
    lat: parseFloat(r.lat),
    lon: parseFloat(r.lon),
    boundingBox: r.boundingbox.map(parseFloat) as [number, number, number, number],
  }));
}

/** A square AOI polygon (GeoJSON geometry) of `halfWidthKm` half-width around a point. */
export function bboxAroundPoint(lat: number, lon: number, halfWidthKm = 1.5): Record<string, unknown> {
  const dLat = halfWidthKm / 111.32;
  const dLon = halfWidthKm / (111.32 * Math.cos((lat * Math.PI) / 180));
  const south = lat - dLat;
  const north = lat + dLat;
  const west = lon - dLon;
  const east = lon + dLon;
  return {
    type: "Polygon",
    coordinates: [
      [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ],
    ],
  };
}

/** The real administrative extent Nominatim returned for a place, as a
 * GeoJSON polygon — used for "cover the entire searched area" region jobs,
 * as opposed to `bboxAroundPoint`'s fixed small box around just the center. */
export function regionPolygonFromBoundingBox(boundingBox: [number, number, number, number]): Record<string, unknown> {
  const [south, north, west, east] = boundingBox;
  return {
    type: "Polygon",
    coordinates: [
      [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ],
    ],
  };
}

/** Client-side mirror of the backend's tile-grid math, for showing "~N
 * tiles" in the UI before actually submitting a region job. */
export function estimateTileGrid(
  boundingBox: [number, number, number, number],
  tileKm: number,
  maxTiles: number
): { rows: number; cols: number; requestedTiles: number; processedTiles: number } {
  const [south, north, west, east] = boundingBox;
  const centerLat = (south + north) / 2;
  const degPerKmLat = 1 / 111.32;
  const degPerKmLon = 1 / (111.32 * Math.max(Math.cos((centerLat * Math.PI) / 180), 1e-6));
  const tileHDeg = tileKm * degPerKmLat;
  const tileWDeg = tileKm * degPerKmLon;

  const fullRows = Math.max(1, Math.ceil((north - south) / tileHDeg));
  const fullCols = Math.max(1, Math.ceil((east - west) / tileWDeg));
  const requestedTiles = fullRows * fullCols;

  let rows = fullRows;
  let cols = fullCols;
  if (requestedTiles > maxTiles) {
    const scale = Math.sqrt(maxTiles / requestedTiles);
    rows = Math.max(1, Math.floor(fullRows * scale));
    cols = Math.max(1, Math.floor(fullCols * scale));
  }

  return { rows, cols, requestedTiles, processedTiles: rows * cols };
}
