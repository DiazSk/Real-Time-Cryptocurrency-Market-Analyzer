/**
 * Tiny inline-SVG sparkline. No charting library: a chart component is
 * overkill for a 168-point 7-day price strip in a table cell.
 *
 * Server-renderable: no hooks, no client state, no `'use client'`.
 */
export interface SparklineProps {
  prices: number[];
  width?: number;
  height?: number;
  /** If unset, color is derived from first-vs-last (up = green, down = red). */
  stroke?: string;
  strokeWidth?: number;
  className?: string;
  /** Stroke with a left-to-right gradient through these colours. Needs a page-unique id. */
  gradient?: { id: string; colors: string[] };
}

export function Sparkline({
  prices,
  width = 96,
  height = 28,
  stroke,
  strokeWidth = 1.2,
  className,
  gradient,
}: SparklineProps) {
  if (!prices || prices.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        className={className}
        aria-hidden="true"
      />
    );
  }

  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1; // guard against flat lines (avoids 0-div)
  const stepX = width / (prices.length - 1);

  const points = prices
    .map((p, i) => {
      const x = i * stepX;
      // Flip Y so higher prices render higher visually.
      const y = height - ((p - min) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const isUp = prices[prices.length - 1] >= prices[0];
  const color = stroke ?? (isUp ? "var(--up)" : "var(--down)");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-label={isUp ? "Price up over period" : "Price down over period"}
    >
      {gradient && (
        <defs>
          <linearGradient id={gradient.id} gradientUnits="userSpaceOnUse" x1={0} x2={width} y1={0} y2={0}>
            {gradient.colors.map((c, i) => (
              <stop key={c + i} offset={`${(i / Math.max(1, gradient.colors.length - 1)) * 100}%`} stopColor={c} />
            ))}
          </linearGradient>
        </defs>
      )}
      <polyline
        points={points}
        fill="none"
        stroke={gradient ? `url(#${gradient.id})` : color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
