interface Props {
  label: string;
}

/** A tilted, spinning 3D radar disc shown over the map while a job runs —
 * replaces a generic spinner with something that actually looks like the
 * thing the app is doing (scanning an AOI). Pure CSS 3D, no canvas/WebGL. */
export default function RadarLoader({ label }: Props) {
  return (
    <div className="radar-loader-overlay">
      <div className="radar-loader-stack">
        <div className="radar-loader">
          <div className="radar-loader-disc">
            <div className="radar-loader-ring" style={{ inset: "0%" }} />
            <div className="radar-loader-ring" style={{ inset: "16%" }} />
            <div className="radar-loader-ring" style={{ inset: "32%" }} />
            <div className="radar-loader-ring" style={{ inset: "48%" }} />
            <div className="radar-loader-sweep" />
            <div className="radar-loader-blip" style={{ top: "22%", left: "68%", animationDelay: "0s" }} />
            <div className="radar-loader-blip" style={{ top: "62%", left: "28%", animationDelay: "0.9s" }} />
            <div className="radar-loader-blip" style={{ top: "40%", left: "50%", animationDelay: "1.6s" }} />
          </div>
          <div className="radar-loader-crosshair-h" />
          <div className="radar-loader-crosshair-v" />
        </div>
        <div className="radar-loader-label">
          <span className="dot" /> {label}
        </div>
      </div>
    </div>
  );
}
