import { useEffect, useState } from "react";

// Status colors validated against the light surface (3:1+ contrast,
// CVD-separated): green-600 / amber-600 / red-600.
const RISK_COLORS: Record<string, string> = {
  Low: "#16a34a",
  Medium: "#d97706",
  High: "#dc2626",
  Critical: "#991b1b",
};

type Props = {
  score: number; // 0–100
  riskLevel: "Low" | "Medium" | "High" | string;
  size?: number; // px
};

/**
 * Circular score gauge: a 270° arc filled proportionally to the score,
 * colored by risk band, with the number in the center. Identity is never
 * color-alone — the numeric score and the risk badge next to it carry
 * the same information.
 */
export function ScoreGauge({ score, riskLevel, size = 108 }: Props) {
  // Animate the sweep on mount / score change
  const [displayed, setDisplayed] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDisplayed(score));
    return () => cancelAnimationFrame(frame);
  }, [score]);

  const stroke = 9;
  const radius = (size - stroke) / 2;
  const center = size / 2;
  // 270° arc, opening at the bottom (gauge style)
  const arcFraction = 0.75;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * arcFraction;
  const filled = arcLength * (Math.max(0, Math.min(100, displayed)) / 100);
  const color = RISK_COLORS[riskLevel] ?? RISK_COLORS.High;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      role="img"
      aria-label={`Overall score ${score} out of 100, ${riskLevel} risk`}
    >
      <svg width={size} height={size}>
        {/* Rotate so the 270° arc is centered with the gap at the bottom */}
        <g transform={`rotate(135 ${center} ${center})`}>
          {/* Track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            className="stroke-muted"
            strokeWidth={stroke}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
          />
          {/* Value */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={`${filled} ${circumference}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 900ms cubic-bezier(0.22, 1, 0.36, 1)" }}
          />
        </g>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold tabular-nums leading-none">{score}</span>
        <span className="text-[10px] text-muted-foreground mt-0.5">/ 100</span>
      </div>
    </div>
  );
}
