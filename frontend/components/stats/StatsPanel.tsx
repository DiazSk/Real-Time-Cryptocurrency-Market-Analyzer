"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtPct, fmtUsd, fmtVolume, pctClass } from "@/lib/format";
import clsx from "clsx";

function Tile({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-background-elev)] p-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={clsx("num mt-1 text-lg font-semibold", valueClass)}>{value}</div>
    </div>
  );
}

export function StatsPanel({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["stats", symbol],
    queryFn: () => api.stats(symbol),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-[68px] animate-pulse rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-background-elev)]"
          />
        ))}
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-lg border border-[color:var(--color-border)] bg-[color:var(--color-background-elev)] p-3 text-sm text-muted-foreground">
        Stats unavailable for {symbol}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      <Tile label="24h Low" value={fmtUsd(data.lowest_price)} valueClass="text-down" />
      <Tile label="24h High" value={fmtUsd(data.highest_price)} valueClass="text-up" />
      <Tile label="24h Avg" value={fmtUsd(data.average_price)} />
      <Tile label="24h Volume" value={fmtVolume(data.total_volume)} />
      <Tile label="Range" value={fmtUsd(data.price_range)} />
      <Tile
        label="Change %"
        value={fmtPct(data.price_change_pct)}
        valueClass={pctClass(data.price_change_pct)}
      />
      <Tile label="Candles" value={String(data.candle_count)} />
    </div>
  );
}
