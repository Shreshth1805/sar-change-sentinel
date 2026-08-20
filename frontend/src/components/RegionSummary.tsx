import type { RegionMeta } from "../types";
import Tilt from "./Tilt";

interface Props {
  region: RegionMeta | null;
}

export default function RegionSummary({ region }: Props) {
  if (!region) {
    return null;
  }

  const failedTiles = region.tiles.filter((t) => t.status === "failed");

  return (
    <Tilt className="panel region-summary-panel" max={3}>
      <h3>
        Region Coverage{" "}
        <span className="badge">
          {region.grid_rows}×{region.grid_cols}
        </span>
      </h3>
      <div className="stat-footnote">
        {region.successful_tiles} of {region.processed_tiles} tiles succeeded
        {region.requested_tiles > region.processed_tiles
          ? ` (capped from ${region.requested_tiles} tiles needed for the full area — showing a centered subset)`
          : ""}{" "}
        &middot; {region.tile_km}km per tile
      </div>
      {failedTiles.length > 0 && (
        <ul className="uncertain-reasons" style={{ marginTop: 8 }}>
          {failedTiles.map((t) => (
            <li key={t.tile_index}>
              tile ({t.row}, {t.col}): {t.error}
            </li>
          ))}
        </ul>
      )}
    </Tilt>
  );
}
