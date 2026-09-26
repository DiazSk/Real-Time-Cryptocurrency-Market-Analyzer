"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtUsd, fmtVolume } from "@/lib/format";

/**
 * 24 h summary computed by our API over the 1m candles in TimescaleDB.
 * Note: the API's `price_change_pct` is (high - low) / low, i.e. the range as a
 * percentage, so it is labelled "Range", never "Change".
 */
export function StatsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["stats", symbol],
    queryFn: () => api.stats(symbol),
    refetchInterval: 30_000,
  });

  const rows: [string, string][] = data
    ? [
        ["Low", fmtUsd(data.lowest_price)],
        ["High", fmtUsd(data.highest_price)],
        ["VWAP", fmtUsd(data.average_price)],
        ["Volume", fmtVolume(data.total_volume)],
        ["Range", `${fmtUsd(data.price_range)} · ${data.price_change_pct.toFixed(2)}%`],
        ["Candles", data.candle_count.toLocaleString()],
      ]
    : [];

  return (
    <section aria-labelledby="stats-heading" className="fringe-top pt-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="stats-heading" className="heading">
          Last 24 h
        </h2>
        <span className="caption num">{symbol} · our candles</span>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="skeleton h-10" />
          ))}
        </div>
      ) : error || !data ? (
        <p className="text-sm text-muted-foreground">
          No stats for {symbol} yet. They appear once the pipeline has written candles in the last 24 h.
        </p>
      ) : (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
          {rows.map(([k, v]) => (
            <div key={k} className={k === "Range" ? "col-span-2" : undefined}>
              <dt className="caption">{k}</dt>
              <dd className="num mt-0.5 text-sm text-foreground">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
