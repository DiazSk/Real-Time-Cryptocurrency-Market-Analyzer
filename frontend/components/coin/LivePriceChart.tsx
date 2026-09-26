"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { LiveLine } from "@/components/charts/live-line";
import { LiveLineChart } from "@/components/charts/live-line-chart";
import { LiveXAxis } from "@/components/charts/live-x-axis";
import { LiveYAxis } from "@/components/charts/live-y-axis";
import { Grid } from "@/components/charts/grid";
import { api } from "@/lib/api";
import { fmtPrice } from "@/lib/format";
import type { LivePoint } from "@/lib/ws";

const WINDOW_S = 60;
const INK = { up: "var(--violet-ink)", down: "var(--violet-ink)", flat: "var(--violet-ink)" };
const FRINGE = ["var(--fringe-1)", "var(--fringe-2)", "var(--fringe-3)"];
const clock = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

/**
 * The live window for a symbol: the last 60 s of raw trades from /trades (so it
 * opens full) followed by streamed WS points newer than the seed. Shared by the
 * chart and the provenance line (react-query dedupes the seed fetch).
 */
export function useLiveWindow(symbol: string, points: LivePoint[]) {
  const seed = useQuery({
    queryKey: ["trades", symbol, WINDOW_S],
    queryFn: () => api.trades(symbol, WINDOW_S),
    staleTime: Infinity,
    retry: 0,
  });
  const data = useMemo(() => {
    const s = seed.data ?? [];
    const lastSeed = s.at(-1)?.time ?? -Infinity;
    const merged = [...s, ...points.filter((p) => p.time > lastSeed)];
    const end = merged.at(-1)?.time;
    return end === undefined ? merged : merged.filter((p) => p.time >= end - WINDOW_S - 5).slice(-500);
  }, [seed.data, points]);
  return { data, seedLoading: seed.isLoading };
}

/**
 * Per-trade line for a tracked symbol: the last 60 s of Coinbase trades as they
 * leave our pipeline. Seeded from /trades (raw_trades) so it opens full, then
 * carried forward by the WebSocket points from useLiveTrades.
 */
export function LivePriceChart({
  symbol,
  points,
  height = 168,
}: {
  symbol: string;
  points: LivePoint[];
  height?: number;
}) {
  const { data, seedLoading } = useLiveWindow(symbol, points);
  const last = data.at(-1);

  return (
    <section aria-label={`Live trades for ${symbol}`} className="fringe-top pt-2">
      <div className="relative" style={{ height }}>
        {last ? (
          <LiveLineChart
            key={symbol}
            data={data}
            value={last.value}
            window={WINDOW_S}
            numXTicks={4}
            margin={{ top: 12, right: 76, bottom: 26, left: 36 }}
            className="chart-slot"
            style={{ height, touchAction: "pan-y" }}
          >
            <Grid horizontal numTicksRows={3} strokeDasharray="2 4" />
            <LiveLine
              dataKey="value"
              stroke="var(--violet-ink)"
              strokeGradient={FRINGE}
              momentumColors={INK}
              strokeWidth={1.5}
              fill={false}
              badge={false}
              formatValue={(v) => fmtPrice(v)}
            />
            <LiveYAxis position="right" minGap={40} bottomInset={14} formatValue={(v) => fmtPrice(v)} />
            <LiveXAxis numTicks={4} formatTime={(t) => clock.format(new Date(t))} />
          </LiveLineChart>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            {seedLoading ? "Loading the last minute of trades…" : `No ${symbol} trades in the last minute yet.`}
          </div>
        )}
      </div>
    </section>
  );
}

export default LivePriceChart;
