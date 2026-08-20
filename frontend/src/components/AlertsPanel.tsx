import { useTilt } from "../hooks/useTilt";
import type { Alert } from "../types";
import Tilt from "./Tilt";

interface Props {
  alerts: Alert[];
}

const SEVERITY_LABEL: Record<Alert["severity"], string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

function AlertItem({ a }: { a: Alert }) {
  const { ref, onMouseMove, onMouseLeave } = useTilt<HTMLLIElement>(4);
  return (
    <li
      ref={ref}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className={`alert-item severity-${a.severity}`}
    >
      <div className="alert-row-top">
        <span className={`severity-chip severity-${a.severity}`}>{SEVERITY_LABEL[a.severity]}</span>
        <span className="alert-area">
          {a.area_sqm != null ? `${Math.round(a.area_sqm).toLocaleString()} m²` : "—"}
        </span>
        <span className="alert-confidence">{(a.confidence * 100).toFixed(0)}%</span>
      </div>
      <div className="alert-reasons">{a.reasons[0]}</div>
      <div className="alert-meta">
        {a.centroid[1].toFixed(4)}, {a.centroid[0].toFixed(4)} &middot; {new Date(a.detected_at).toLocaleString()}
      </div>
    </li>
  );
}

export default function AlertsPanel({ alerts }: Props) {
  return (
    <Tilt className="panel alerts-panel" max={3}>
      <h3>Alerts {alerts.length > 0 && <span className="badge">{alerts.length}</span>}</h3>
      {alerts.length === 0 && <div className="empty-note">No man-made changes flagged yet.</div>}
      <ul className="alert-list">
        {alerts.map((a) => (
          <AlertItem key={a.alert_id} a={a} />
        ))}
      </ul>
    </Tilt>
  );
}
