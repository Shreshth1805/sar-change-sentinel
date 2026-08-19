import { useState } from "react";
import { searchPlace, type GeocodeResult } from "../api/geocode";

interface Props {
  onSelect: (place: GeocodeResult) => void;
  selected: GeocodeResult | null;
}

export default function LocationSearch({ onSelect, selected }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodeResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const found = await searchPlace(query);
      setResults(found);
      if (found.length === 0) {
        setError("No matching places found.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="location-search">
      <label>
        City or country
        <div className="location-search-row">
          <input
            value={query}
            placeholder="e.g. Mumbai, Sundarbans, Kyiv..."
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <button className="secondary-btn" onClick={runSearch} disabled={loading}>
            {loading ? "…" : "Search"}
          </button>
        </div>
      </label>

      {error && <div className="error-banner">{error}</div>}

      {results.length > 0 && (
        <ul className="location-results">
          {results.map((r, i) => (
            <li key={i}>
              <button
                className="location-result-btn"
                onClick={() => {
                  onSelect(r);
                  setResults([]);
                  setQuery(r.displayName);
                }}
              >
                {r.displayName}
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && (
        <div className="location-selected">
          📍 {selected.lat.toFixed(4)}, {selected.lon.toFixed(4)}
        </div>
      )}
    </div>
  );
}
