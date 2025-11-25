// frontend/src/components/Gauge.jsx
import React, { useEffect, useRef, useState } from "react";

/**
 * Animated SVG gauge. Uses stroke-dashoffset animation to sweep.
 * Props:
 *  - value: number 0-100
 *  - size: px (default 160)
 *  - thickness: stroke width (default 10)
 */
export default function Gauge({ value = 0, size = 160, thickness = 10 }) {
  const circleRef = useRef(null);
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    // animate numeric counter (spring-like easing approximation)
    let start = performance.now();
    const from = display;
    const to = Math.round(Math.max(0, Math.min(100, value || 0)));
    const dur = 900;
    const easeOutBack = (t) => 1 - Math.pow(1 - t, 3); // simple easing

    const tick = (ts) => {
      const t = Math.min(1, (ts - start) / dur);
      const eased = easeOutBack(t);
      setDisplay(Math.round(from + (to - from) * eased));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);

    // SVG sweep using stroke-dashoffset
    const circle = circleRef.current;
    if (circle) {
      const r = (size - thickness) / 2;
      const c = 2 * Math.PI * r;
      const pct = Math.max(0, Math.min(100, to));
      const filled = (pct / 100) * c;
      // animate strokeDashoffset from c to c-filled
      circle.style.transition = "stroke-dashoffset 1.2s cubic-bezier(.22,.9,.3,1)";
      circle.style.strokeDasharray = `${c} ${c}`;
      circle.style.strokeDashoffset = `${c - filled}`;
    }

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="rounded-full">
        <defs>
          <linearGradient id="g1" x1="0" x2="1">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#3b82f6" />
          </linearGradient>
        </defs>

        {/* background track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#eef2ff"
          strokeWidth={thickness}
          fill="none"
        />
        {/* animated arc */}
        <circle
          ref={circleRef}
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="url(#g1)"
          strokeWidth={thickness}
          strokeLinecap="round"
          fill="none"
          style={{
            transform: "rotate(-90deg)",
            transformOrigin: "50% 50%",
            strokeDasharray: `${c} ${c}`,
            strokeDashoffset: `${c}`,
          }}
        />
        {/* center hole */}
        <circle cx={size / 2} cy={size / 2} r={r - thickness - 2} fill="white" />
      </svg>

      <div>
        <div className="text-sm text-gray-500">Overall Match</div>
        <div className="text-2xl font-extrabold text-gray-900">{display}%</div>
        <div className="text-xs text-gray-500 mt-1 max-w-xs">Combined: Keywords, Structure, Semantics, Readability, Tone.</div>
      </div>
    </div>
  );
}
