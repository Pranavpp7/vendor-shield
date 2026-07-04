import { useMemo, useState } from "react";

// Validated status colors (3:1+ on light surface, CVD-separated).
const SLICES = [
  { key: "High", color: "#dc2626" },
  { key: "Medium", color: "#d97706" },
  { key: "Low", color: "#16a34a" },
] as const;

type Props = {
  counts: { High: number; Medium: number; Low: number };
  size?: number;
};

/** Build an SVG donut-segment path between two angles (radians). */
function arcPath(cx: number, cy: number, rOuter: number, rInner: number, a0: number, a1: number): string {
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const p = (r: number, a: number) => `${cx + r * Math.cos(a)} ${cy + r * Math.sin(a)}`;
  return [
    `M ${p(rOuter, a0)}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${p(rOuter, a1)}`,
    `L ${p(rInner, a1)}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${p(rInner, a0)}`,
    "Z",
  ].join(" ");
}

/**
 * Portfolio risk distribution donut. Identity is never color-alone:
 * the legend carries label + count per slice, and hover highlights the
 * matching legend row. Empty portfolio renders a neutral ring.
 */
export function RiskDonut({ counts, size = 132 }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);
  const total = counts.High + counts.Medium + counts.Low;

  const segments = useMemo(() => {
    if (total === 0) return [];
    const gapAngle = 0.035; // ~2px surface gap between slices
    let angle = -Math.PI / 2;
    return SLICES.filter((s) => counts[s.key] > 0).map((s) => {
      const sweep = (counts[s.key] / total) * Math.PI * 2;
      const singleSlice = counts[s.key] === total;
      const a0 = angle + (singleSlice ? 0 : gapAngle / 2);
      const a1 = angle + sweep - (singleSlice ? 0.0001 : gapAngle / 2);
      angle += sweep;
      return { ...s, a0, a1 };
    });
  }, [counts, total]);

  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 2;
  const rInner = rOuter - 14;

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0" role="img"
        aria-label={`Risk distribution: ${counts.High} high, ${counts.Medium} medium, ${counts.Low} low risk vendors`}>
        <svg width={size} height={size}>
          {total === 0 ? (
            <circle cx={cx} cy={cy} r={rOuter - 7} fill="none" strokeWidth={14} className="stroke-muted" />
          ) : (
            segments.map((s) => (
              <path
                key={s.key}
                d={arcPath(cx, cy, rOuter, rInner, s.a0, s.a1)}
                fill={s.color}
                opacity={hovered && hovered !== s.key ? 0.35 : 1}
                style={{ transition: "opacity 150ms" }}
                onMouseEnter={() => setHovered(s.key)}
                onMouseLeave={() => setHovered(null)}
              >
                <title>{`${s.key} risk: ${counts[s.key]} vendor${counts[s.key] === 1 ? "" : "s"}`}</title>
              </path>
            ))
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-2xl font-bold tabular-nums leading-none">{total}</span>
          <span className="text-[10px] text-muted-foreground mt-0.5">
            vendor{total === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {/* Legend: dot + label + count — identity never color-alone */}
      <div className="space-y-1.5">
        {SLICES.map((s) => (
          <div
            key={s.key}
            className={`flex items-center gap-2 text-sm transition-opacity ${
              hovered && hovered !== s.key ? "opacity-40" : ""
            }`}
            onMouseEnter={() => setHovered(s.key)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
            <span className="text-muted-foreground">{s.key} risk</span>
            <span className="font-semibold tabular-nums ml-auto pl-3">{counts[s.key]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
