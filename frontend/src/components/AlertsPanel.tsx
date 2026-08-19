import type { Alert } from "../types";

interface Props {
  alerts: Alert[];
}

const SEVERITY_LABEL: Record<Alert["severity"], string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
};

export default function AlertsPanel({ alerts }: Props) {
  return (
    <div className="panel alerts-panel">
      <h3>Alerts {alerts.length > 0 && <span className="badge">{alerts.length}</span>}</h3>
      {alerts.length === 0 && <div className="empty-note">No man-made changes flagged yet.</div>}
      <ul className="alert-list">
        {alerts.map((a) => (
          <li key={a.alert_id} className={`alert-item severity-${a.severity}`}>
            <div className="alert-row-top">
              <span className={`severity-chip severity-${a.severity}`}>{SEVERITY_LABEL[a.severity]}</span>
              <span className="alert-area">
                {a.area_sqm != null ? `${Math.round(a.area_sqm).toLocaleString()} m²` : "—"}
              </span>
              <span className="alert-confidence">{(a.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="alert-reasons">{a.reasons[0]}</div>
            <div className="alert-meta">
              {a.centroid[1].toFixed(4)}, {a.centroid[0].toFixed(4)} &middot;{" "}
              {new Date(a.detected_at).toLocaleString()}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
