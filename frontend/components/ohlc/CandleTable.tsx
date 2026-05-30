"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtTime, fmtUsd, fmtVolume } from "@/lib/format";

export function CandleTable({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["candles", symbol, "table"],
    queryFn: () => api.historical(symbol, { limit: 30, order_by: "desc" }),
    refetchInterval: 60_000,
  });

  return (
    <div className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-background-elev)]">
      <div className="border-b border-[color:var(--color-border)] px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide">
          Recent Candles
          <span className="ml-2 text-muted-foreground">— {symbol} (1m)</span>
        </h3>
      </div>

      <div className="max-h-[420px] overflow-y-auto">
        {isLoading && (
          <div className="space-y-2 p-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-8 animate-pulse rounded bg-[color:var(--color-background-elev-2)]"
              />
            ))}
          </div>
        )}

        {error && <div className="p-4 text-sm text-down">Failed to load candles.</div>}

        {data && (
          <table className="num w-full text-sm">
            <thead className="sticky top-0 bg-[color:var(--color-background-elev)] text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Time</th>
                <th className="px-2 py-2 text-right font-medium">Open</th>
                <th className="px-2 py-2 text-right font-medium">High</th>
                <th className="px-2 py-2 text-right font-medium">Low</th>
                <th className="px-2 py-2 text-right font-medium">Close</th>
                <th className="px-4 py-2 text-right font-medium">Vol</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--color-border)]">
              {data.map((c) => {
                const up = c.close_price >= c.open_price;
                return (
                  <tr key={c.window_start} className="hover:bg-[color:var(--color-background-elev-2)]">
                    <td className="px-4 py-1.5 text-left text-muted-foreground">{fmtTime(c.window_start)}</td>
                    <td className="px-2 py-1.5 text-right">{fmtUsd(c.open_price)}</td>
                    <td className="px-2 py-1.5 text-right text-up">{fmtUsd(c.high_price)}</td>
                    <td className="px-2 py-1.5 text-right text-down">{fmtUsd(c.low_price)}</td>
                    <td className={`px-2 py-1.5 text-right ${up ? "text-up" : "text-down"}`}>
                      {fmtUsd(c.close_price)}
                    </td>
                    <td className="px-4 py-1.5 text-right text-muted-foreground">
                      {fmtVolume(c.volume_sum)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
