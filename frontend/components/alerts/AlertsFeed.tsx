"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtDateTime, fmtPct, fmtUsd } from "@/lib/format";
import clsx from "clsx";

export function AlertsFeed({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["alerts", symbol],
    queryFn: () => api.alerts(symbol, { limit: 50, hours: 24 }),
    refetchInterval: 15_000,
  });

  return (
    <div className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-background-elev)]">
      <div className="flex items-center justify-between border-b border-[color:var(--color-border)] px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide">
          Alerts
          <span className="ml-2 text-muted-foreground">— {symbol}</span>
        </h3>
        <span className="text-xs text-muted-foreground">
          {data ? `${data.alert_count} in last ${data.lookback_hours}h` : "—"}
        </span>
      </div>

      <div className="max-h-[420px] overflow-y-auto">
        {isLoading && (
          <div className="space-y-2 p-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded bg-[color:var(--color-background-elev-2)]"
              />
            ))}
          </div>
        )}

        {error && (
          <div className="p-4 text-sm text-down">Failed to load alerts.</div>
        )}

        {data && data.alerts.length === 0 && (
          <div className="p-4 text-sm text-muted-foreground">No alerts in the last 24 hours.</div>
        )}

        {data && data.alerts.length > 0 && (
          <ul className="divide-y divide-[color:var(--color-border)]">
            {data.alerts.map((a, idx) => {
              const up = a.alert_type === "PRICE_SPIKE";
              return (
                <li
                  key={`${a.symbol}-${a.created_at}-${idx}`}
                  className="flex items-center justify-between px-4 py-2.5 text-sm"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={clsx(
                        "rounded px-2 py-0.5 text-xs font-bold",
                        up ? "bg-up/15 text-up" : "bg-down/15 text-down",
                      )}
                    >
                      {up ? "SPIKE" : "DROP"}
                    </span>
                    <span className="num font-medium">{a.symbol}</span>
                    <span className={clsx("num", up ? "text-up" : "text-down")}>
                      {fmtPct(a.price_change_pct)}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="num">
                      {fmtUsd(a.old_price)} → {fmtUsd(a.new_price)}
                    </span>
                    <span>{fmtDateTime(a.created_at)}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
