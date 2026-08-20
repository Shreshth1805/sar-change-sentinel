import { useCountUp } from "../hooks/useCountUp";
import type { PipelineStats } from "../types";
import Tilt from "./Tilt";

interface Props {
  stats: PipelineStats | null;
}

function StatCard({ value, label, className }: { value: number; label: string; className?: string }) {
  const animated = useCountUp(value);
  return (
    <Tilt className={`stat-card ${className ?? ""}`} max={10}>
      <span className="stat-value">{animated}</span>
      <span className="stat-label">{label}</span>
    </Tilt>
  );
}

export default function StatsDashboard({ stats }: Props) {
  if (!stats) {
    return <div className="panel stats-panel empty">Run a job to see detection stats.</div>;
  }
  const counts = stats.classification_counts;
  return (
    <Tilt className="panel stats-panel" max={3}>
      <h3>Detection Summary</h3>
      <div className="stat-grid">
        <StatCard value={counts.man_made} label="Man-made" className="man-made" />
        <StatCard value={counts.natural} label="Natural (suppressed)" className="natural" />
        <StatCard value={counts.uncertain} label="Uncertain" className="uncertain" />
        <StatCard value={stats.alerts_generated} label="Alerts issued" />
      </div>
      <div className="stat-footnote">
        {(stats.changed_pixel_fraction * 100).toFixed(2)}% of scene flagged as changed &middot; Otsu
        threshold {stats.otsu_threshold.toFixed(3)}
      </div>
    </Tilt>
  );
}
