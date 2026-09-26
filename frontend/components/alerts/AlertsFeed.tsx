"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd, timeAgo } from "@/lib/format";
import { cn } from "@/lib/utils";

const SEVERITY: Record<"LOW" | "MEDIUM" | "HIGH", string> = {
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
};

/**
 * PRICE_SPIKE / PRICE_DROP alerts from the Flink z-score detector, newest first.
 * Severity is spelled out, the direction is an icon + word, the z-score is shown raw.
 */
export function AlertsFeed({ symbol, limit = 8 }: { symbol: string; limit?: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["alerts", symbol],
    queryFn: () => api.alerts(symbol, { limit: 50, hours: 24 }),
    refetchInterval: 15_000,
  });

  const alerts = data?.alerts.slice(0, limit) ?? [];

  return (
    <section aria-labelledby={`alerts-heading-${symbol}`} className="fringe-top pt-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 id={`alerts-heading-${symbol}`} className="heading">
          Anomaly alerts
        </h2>
        <span className="caption num">
          {data ? `${data.alert_count} in ${data.lookback_hours} h` : symbol}
        </span>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton h-12" />
          ))}
        </div>
      ) : error ? (
        <p className="text-sm text-muted-foreground">Couldn&apos;t load alerts. Retrying every 15 s.</p>
      ) : alerts.length === 0 ? (
        <p className="text-sm leading-relaxed text-muted-foreground">
          No alerts for {symbol} in the last 24 h. The detector flags a candle whose price move is a
          statistical outlier (by z-score) against recent history.
        </p>
      ) : (
        <ul className="divide-y">
          {alerts.map((a, idx) => {
            const up = a.alert_type === "PRICE_SPIKE";
            const Icon = up ? ArrowUpRight : ArrowDownRight;
            return (
              <li key={`${a.created_at}-${idx}`} className="py-2.5 first:pt-0">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className={cn("inline-flex items-center gap-1", up ? "text-up" : "text-down")}>
                    <Icon size={15} strokeWidth={1.75} aria-hidden />
                    {up ? "Spike" : "Drop"}
                    <span className="num">{fmtPct(a.price_change_pct)}</span>
                  </span>
                  <span className="num text-foreground">z = {a.z_score.toFixed(1)}</span>
                </div>
                <div className="caption mt-0.5 flex items-center justify-between gap-3">
                  <span>
                    {SEVERITY[a.severity]} severity ·{" "}
                    <span className="num">
                      {fmtUsd(a.old_price)} to {fmtUsd(a.new_price)}
                    </span>
                  </span>
                  <time dateTime={a.created_at} className="whitespace-nowrap">
                    {timeAgo(a.created_at)}
                  </time>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
