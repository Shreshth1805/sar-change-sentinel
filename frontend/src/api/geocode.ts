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
