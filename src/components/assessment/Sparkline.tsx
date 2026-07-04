type Props = {
  /** Score values 0–100, oldest first. Rendered only when 2+ points. */
  values: number[];
  width?: number;
  height?: number;
};

/**
 * Tiny single-series score trend for table rows. One hue (the app
 * accent), a dot on the latest point, no axes — the row's score cell
 * carries the exact number.
 */
export function Sparkline({ values, width = 64, height = 20 }: Props) {
  if (values.length < 2) return null;

  const pad = 2;
  // Fixed 0–100 domain so sparklines are comparable across rows
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - (Math.max(0, Math.min(100, v)) / 100) * (height - pad * 2);
  const points = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const last = values[values.length - 1];

  return (
    <svg
      width={width}
      height={height}
      className="text-accent shrink-0"
      role="img"
      aria-label={`Score trend over ${values.length} runs, latest ${last}`}
    >
      <title>{values.join(" → ")}</title>
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={x(values.length - 1)} cy={y(last)} r={2.5} fill="currentColor" />
    </svg>
  );
}
