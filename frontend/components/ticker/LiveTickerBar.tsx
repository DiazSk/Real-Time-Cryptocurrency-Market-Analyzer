"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useCryptoSocket } from "@/lib/ws";
import { fmtPct, fmtUsd, pctClass } from "@/lib/format";
import clsx from "clsx";

/**
 * WS-driven ticker. Subscribes to /ws/prices/ALL for sub-second updates.
 * Falls back to /api/v1/trending for the static 24h % change column
 * (the Flink-driven WS candles don't carry 24h change).
 */
export function LiveTickerBar() {
  const { status, latestBySymbol } = useCryptoSocket("ALL");

  const { data: trending } = useQuery({
    queryKey: ["trending", "abs"],
    queryFn: () => api.trending({ limit: 20, direction: "abs" }),
    refetchInterval: 60_000,
  });

  // Build chip list ordered by trending, prices from WS (with REST fallback).
  const wsSymbols = Object.keys(latestBySymbol);
  const ordered = [
    ...(trending ?? []).map((t) => t.symbol),
    ...wsSymbols.filter((s) => !trending?.some((t) => t.symbol === s)),
  ];

  return (
    <div className="overflow-x-auto border-b border-[color:var(--color-border)] bg-[color:var(--color-background-elev)]">
      <div className="flex min-w-max items-center gap-6 px-4 py-2">
        <span
          className={clsx(
            "text-xs uppercase tracking-wide",
            status === "open" ? "text-up" : status === "closed" || status === "error" ? "text-down" : "text-muted-foreground",
          )}
          title={`Stream status: ${status}`}
        >
          ● {status === "open" ? "live" : status}
        </span>

        {ordered.length === 0 && (
          <span className="text-xs text-muted-foreground">Waiting for market data…</span>
        )}

        {ordered.map((sym) => {
          const ws = latestBySymbol[sym];
          const t = trending?.find((row) => row.symbol === sym);
          const price = ws?.close ?? t?.price ?? NaN;
          const pct = t?.price_change_24h ?? NaN;
          return (
            <div key={sym} className="flex items-center gap-2 text-sm">
              <span className="num font-semibold">{sym}</span>
              <span className="num text-foreground">{fmtUsd(price)}</span>
              <span className={clsx("num text-xs", pctClass(pct))}>
                {Number.isFinite(pct) ? fmtPct(pct) : ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
