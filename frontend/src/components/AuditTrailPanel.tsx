import { useState } from "react";
import type { AuditStep } from "../types";
import Tilt from "./Tilt";

interface Props {
  steps: AuditStep[];
}

export default function AuditTrailPanel({ steps }: Props) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (steps.length === 0) {
    return null;
  }

  return (
    <Tilt className="panel audit-panel" max={3}>
      <h3>Audit Trail</h3>
      <p className="audit-intro">Every pipeline stage, in order, with exactly what it did — nothing is silent.</p>
      <ol className="audit-list">
        {steps.map((s, i) => (
          <li key={i} className={openIndex === i ? "open" : ""}>
            <button className="audit-step-header" onClick={() => setOpenIndex(openIndex === i ? null : i)}>
              <span className="audit-step-name">{s.step_name.replace(/_/g, " ")}</span>
              <span className="audit-step-duration">{s.duration_ms.toFixed(1)} ms</span>
            </button>
            <div className="audit-step-desc">{s.description}</div>
            {openIndex === i && (
              <div className="audit-step-details">
                <pre>{JSON.stringify(s.details, null, 2)}</pre>
                {s.warnings.length > 0 && (
                  <ul className="audit-warnings">
                    {s.warnings.map((w, wi) => (
                      <li key={wi}>⚠ {w}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
    </Tilt>
  );
}
