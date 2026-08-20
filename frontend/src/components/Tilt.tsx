import type { ReactNode } from "react";
import { useTilt } from "../hooks/useTilt";

interface Props {
  className?: string;
  children: ReactNode;
  max?: number;
}

/** Drop-in replacement for a plain <div> that tilts toward the cursor. */
export default function Tilt({ className, children, max }: Props) {
  const { ref, onMouseMove, onMouseLeave } = useTilt<HTMLDivElement>(max);
  return (
    <div ref={ref} className={className} onMouseMove={onMouseMove} onMouseLeave={onMouseLeave}>
      {children}
    </div>
  );
}
