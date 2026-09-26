"use client";

import { LiveLine } from "@/components/charts/live-line";
import { LiveLineChart } from "@/components/charts/live-line-chart";
import { LiveXAxis } from "@/components/charts/live-x-axis";
import { LiveYAxis } from "@/components/charts/live-y-axis";
import { Grid } from "@/components/charts/grid";
import { fmtPrice } from "@/lib/format";
import type { LivePoint } from "@/lib/ws";

const MOMENTUM = { up: "var(--up)", down: "var(--down)", flat: "var(--foreground)" };
const clock = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

/**
 * Per-trade line for a tracked symbol: the last 60 s of Coinbase trades as they
 * leave our pipeline. Points come from useLiveTrades (last 500 per symbol).
 */
export function LivePriceChart({
  symbol,
  points,
  height = 220,
}: {
  symbol: string;
  points: LivePoint[];
  height?: number;
}) {
  const last = points.at(-1);

  return (
    <section aria-label={`Live trades for ${symbol}`}>
      <div className="fringe-bottom relative" style={{ height }}>
        {last ? (
          <LiveLineChart
            data={points}
            value={last.value}
            window={60}
            numXTicks={4}
            margin={{ top: 12, right: 72, bottom: 28, left: 32 }}
            style={{ height, touchAction: "pan-y" }}
          >
            <Grid horizontal numTicksRows={3} strokeDasharray="2 4" />
            <LiveLine
              dataKey="value"
              momentumColors={MOMENTUM}
              strokeWidth={1.5}
              badge={false}
              formatValue={(v) => fmtPrice(v)}
            />
            <LiveYAxis position="right" minGap={44} formatValue={(v) => fmtPrice(v)} />
            <LiveXAxis numTicks={4} formatTime={(t) => clock.format(new Date(t))} />
          </LiveLineChart>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Waiting for the first {symbol} trade…
          </div>
        )}
      </div>
    </section>
  );
}

export default LivePriceChart;
