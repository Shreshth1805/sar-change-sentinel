import { useRef } from "react";

/**
 * Lightweight pointer-tilt: rotates an element in 3D toward the cursor.
 * Plain CSS transforms driven by mouse position — no WebGL/three.js, kept
 * intentionally cheap so it stays smooth on every panel at once.
 */
export function useTilt<T extends HTMLElement>(max = 5, scale = 1.015) {
  const ref = useRef<T | null>(null);

  function onMouseMove(e: React.MouseEvent<T>) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `perspective(700px) rotateX(${(-py * max).toFixed(2)}deg) rotateY(${(px * max).toFixed(
      2
    )}deg) scale3d(${scale}, ${scale}, ${scale})`;
  }

  function onMouseLeave() {
    const el = ref.current;
    if (!el) return;
    el.style.transform = "";
  }

  return { ref, onMouseMove, onMouseLeave };
}
