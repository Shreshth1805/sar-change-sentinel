import { useTilt } from "../hooks/useTilt";
import type { Blob } from "../types";
import Tilt from "./Tilt";

interface Props {
  blobs: Blob[];
  pixelAreaSqm: number | null;
}

function UncertainItem({ b, pixelAreaSqm }: { b: Blob; pixelAreaSqm: number | null }) {
  const { ref, onMouseMove, onMouseLeave } = useTilt<HTMLLIElement>(4);
  return (
    <li ref={ref} onMouseMove={onMouseMove} onMouseLeave={onMouseLeave} className="alert-item uncertain-item">
      <div className="alert-row-top">
        <span className="alert-area">
          {pixelAreaSqm != null ? `${Math.round(b.area_px * pixelAreaSqm).toLocaleString()} m²` : `${b.area_px} px`}
        </span>
        <span className="alert-confidence">{(b.confidence * 100).toFixed(0)}%</span>
      </div>
      <ul className="uncertain-reasons">
        {b.reasons.map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </li>
  );
}

export default function UncertainPanel({ blobs, pixelAreaSqm }: Props) {
  const uncertain = blobs.filter((b) => b.classification === "uncertain");

  if (uncertain.length === 0) {
    return null;
  }

  return (
    <Tilt className="panel uncertain-panel" max={3}>
      <h3>
        Uncertain <span className="badge badge-uncertain">{uncertain.length}</span>
      </h3>
      <p className="audit-intro">
        Evidence conflicted — shape and land-cover signals disagreed enough that the discrimination stage
        didn't force a call either way. Not included in alerts or the GeoJSON export.
      </p>
      <ul className="alert-list">
        {uncertain.map((b) => (
          <UncertainItem key={b.label} b={b} pixelAreaSqm={pixelAreaSqm} />
        ))}
      </ul>
    </Tilt>
  );
}
