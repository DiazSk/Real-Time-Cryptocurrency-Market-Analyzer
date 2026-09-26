"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { Sparkline } from "@/components/cg/Sparkline";
import { Change } from "@/components/ui/change";
import { api } from "@/lib/api";
import { fmtUsd } from "@/lib/format";
import type { SymbolMeta } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Last hour of our 1m candles: feeds the sparkline and the 1h change. Shared cache key with the hero. */
export const hourCandlesQuery = (symbol: string) => ({
  queryKey: ["candles", symbol, "1m", "hour"],
  queryFn: () => api.historical(symbol, { interval: "1m", limit: 60, order_by: "desc" }),
  refetchInterval: 60_000,
});

export const trendingQuery = {
  queryKey: ["trending", "abs"],
  queryFn: () => api.trending({ limit: 20, direction: "abs" }),
  refetchInterval: 60_000,
};

/**
 * Change for a symbol: 24h from our /trending once the pipeline holds ~24 h of
 * candles, otherwise the last hour from our 1m candles. Never a guess.
 */
export function useChange(symbol: string, price: number | undefined) {
  const hour = useQuery(hourCandlesQuery(symbol));
  const trending = useQuery(trendingQuery);
  return changeFrom(symbol, price, hour.data, trending.data);
}

function changeFrom(
  symbol: string,
  price: number | undefined,
  hour: Awaited<ReturnType<typeof api.historical>> | undefined,
  trending: Awaited<ReturnType<typeof api.trending>> | undefined,
): { pct: number | null; window: "24h" | "1h" } {
  const t = trending?.find((r) => r.symbol === symbol);
  if (t) return { pct: t.price_change_24h, window: "24h" };
  const base = hour?.at(-1)?.close_price;
  const now = price ?? hour?.[0]?.close_price;
  if (!base || now === undefined) return { pct: null, window: "1h" };
  return { pct: ((now - base) / base) * 100, window: "1h" };
}

export function Watchlist({
  symbols,
  prices,
  lastTradeAt,
  now,
  selected,
  onSelect,
}: {
  symbols: SymbolMeta[] | undefined;
  prices: Record<string, number | undefined>;
  lastTradeAt: Record<string, number | undefined>;
  now: number;
  selected: string;
  onSelect: (symbol: string) => void;
}) {
  const list = symbols ?? [];
  const hours = useQueries({ queries: list.map((s) => hourCandlesQuery(s.symbol)) });
  const trending = useQuery(trendingQuery);
  const has24h = (trending.data?.length ?? 0) > 0;

  return (
    <section aria-labelledby="watchlist-heading">
      <h2 id="watchlist-heading" className="heading mb-3 hidden lg:block">
        Watchlist
      </h2>
      <h2 className="sr-only lg:hidden">Watchlist</h2>

      {list.length === 0 ? (
        <div className="flex gap-2 lg:flex-col" aria-label="Loading watchlist">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton h-12 w-32 flex-none lg:w-full" />
          ))}
        </div>
      ) : (
        <ul className="scroll-x -mx-4 flex gap-2 px-4 pb-1 lg:mx-0 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:px-0">
          {list.map((s, i) => {
            const hour = hours[i]?.data;
            const price = prices[s.symbol] ?? hour?.[0]?.close_price;
            const { pct, window } = changeFrom(s.symbol, prices[s.symbol], hour, trending.data);
            const at = lastTradeAt[s.symbol];
            const live = at !== undefined && now - at < 15;
            const active = s.symbol === selected;
            const closes = hour ? hour.map((c) => c.close_price).reverse() : [];

            return (
              <li key={s.symbol} className="flex-none">
                <button
                  type="button"
                  onClick={() => onSelect(s.symbol)}
                  aria-pressed={active}
                  aria-label={`${s.name} (${s.symbol})`}
                  className={cn(
                    "group flex w-full items-center gap-3 text-left transition-shadow",
                    // Mobile: a chip. Desktop: a row.
                    "rounded-full border px-3.5 py-2 lg:rounded-[var(--radius-md)] lg:border-transparent lg:px-3 lg:py-2.5",
                    active
                      ? "fringe-top border-[var(--violet-edge)] bg-card shadow-[var(--shadow-soft)] lg:border-transparent"
                      : "bg-card hover:shadow-[var(--shadow-soft)] lg:bg-transparent lg:hover:bg-card",
                  )}
                >
                  <span
                    className="live-dot"
                    data-state={live ? "live" : "idle"}
                    aria-label={live ? "receiving trades" : "no recent trades"}
                  />
                  <span className="min-w-0 lg:w-20">
                    <span className="num block text-sm font-medium text-foreground">{s.symbol}</span>
                    <span className="caption hidden truncate lg:block">{s.name}</span>
                  </span>
                  <span className="hidden flex-1 justify-center lg:flex" aria-hidden>
                    <Sparkline
                      prices={closes}
                      width={72}
                      height={22}
                      strokeWidth={1.25}
                      stroke="var(--muted-foreground)"
                      gradient={
                        active
                          ? { id: `spark-${s.symbol}`, colors: ["var(--fringe-1)", "var(--fringe-2)", "var(--fringe-3)"] }
                          : undefined
                      }
                    />
                  </span>
                  <span className="flex items-baseline gap-2 lg:ml-auto lg:flex-col lg:items-end lg:gap-0">
                    <span className="num text-sm text-foreground">{fmtUsd(price)}</span>
                    <Change value={pct} className="text-xs" iconSize={12}>
                      {pct === null ? "—" : `${Math.abs(pct).toFixed(2)}%`}
                      <span className="ml-1 text-muted-foreground">{window}</span>
                    </Change>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {!has24h && list.length > 0 && (
        <p className="caption mt-3 hidden lg:block">
          Change covers the last hour. 24 h change appears once the pipeline holds about 24 h of candles.
        </p>
      )}
    </section>
  );
}
