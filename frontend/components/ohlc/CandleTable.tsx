"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtTime, fmtUsd, fmtVolume } from "@/lib/format";
import { cn } from "@/lib/utils";

/** The most recent 1m candles as the pipeline wrote them, including trades per candle. */
export function CandleTable({ symbol, rows = 10 }: { symbol: string; rows?: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["candles", symbol, "1m", "table", rows],
    queryFn: () => api.historical(symbol, { interval: "1m", limit: rows, order_by: "desc" }),
    refetchInterval: 60_000,
  });

  return (
    <section aria-labelledby="candle-table-heading">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id="candle-table-heading" className="heading">
          Recent 1m candles
        </h2>
        <span className="caption">Flink event-time windows, deduplicated</span>
      </div>

      {isLoading ? (
        <div className="space-y-1.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton h-8" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-muted-foreground">Couldn&apos;t load candles. Retrying every 60 s.</p>
      ) : !data?.length ? (
        <p className="text-sm text-muted-foreground">No 1m candles for {symbol} in the last 24 h yet.</p>
      ) : (
        <div className="scroll-x">
          <table className="num w-full min-w-[560px] text-sm">
            <thead className="caption text-left">
              <tr className="border-b">
                <th scope="col" className="py-2 pr-3 font-normal">Minute</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Open</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">High</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Low</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Close</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Volume</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Trades</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((c) => {
                const up = c.close_price >= c.open_price;
                return (
                  <tr key={c.window_start}>
                    <td className="py-2 pr-3 text-muted-foreground">{fmtTime(c.window_start)}</td>
                    <td className="px-3 py-2 text-right">{fmtUsd(c.open_price)}</td>
                    <td className="px-3 py-2 text-right">{fmtUsd(c.high_price)}</td>
                    <td className="px-3 py-2 text-right">{fmtUsd(c.low_price)}</td>
                    <td className={cn("px-3 py-2 text-right", up ? "text-up" : "text-down")}>
                      {fmtUsd(c.close_price)}
                    </td>
                    <td className="px-3 py-2 text-right text-muted-foreground">{fmtVolume(c.quote_volume)}</td>
                    <td className="py-2 pl-3 text-right">{c.trade_count.toLocaleString()}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
