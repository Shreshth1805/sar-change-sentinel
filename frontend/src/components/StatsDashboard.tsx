import type { PipelineStats } from "../types";

interface Props {
  stats: PipelineStats | null;
}

export default function StatsDashboard({ stats }: Props) {
  if (!stats) {
    return <div className="panel stats-panel empty">Run a job to see detection stats.</div>;
  }
  const counts = stats.classification_counts;
  return (
    <div className="panel stats-panel">
      <h3>Detection Summary</h3>
      <div className="stat-grid">
        <div className="stat-card man-made">
          <span className="stat-value">{counts.man_made}</span>
          <span className="stat-label">Man-made</span>
        </div>
        <div className="stat-card natural">
          <span className="stat-value">{counts.natural}</span>
          <span className="stat-label">Natural (suppressed)</span>
        </div>
        <div className="stat-card uncertain">
          <span className="stat-value">{counts.uncertain}</span>
          <span className="stat-label">Uncertain</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.alerts_generated}</span>
          <span className="stat-label">Alerts issued</span>
        </div>
      </div>
      <div className="stat-footnote">
        {(stats.changed_pixel_fraction * 100).toFixed(2)}% of scene flagged as changed &middot; Otsu
        threshold {stats.otsu_threshold.toFixed(3)}
      </div>
    </div>
  );
}
