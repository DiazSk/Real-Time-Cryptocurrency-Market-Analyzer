"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { AlertsFeed } from "@/components/alerts/AlertsFeed";
import { LivePriceChart, useLiveWindow } from "@/components/coin/LivePriceChart";
import { LiveProvenance, PriceHero } from "@/components/coin/PriceHero";
import { PriceChart } from "@/components/coin/PriceChart";
import { CandleTable } from "@/components/ohlc/CandleTable";
import { StatsPanel } from "@/components/stats/StatsPanel";
import { useChange, Watchlist } from "@/components/ticker/Watchlist";
import { api } from "@/lib/api";
import { useLiveTrades, useNowSeconds } from "@/lib/ws";

/**
 * The first viewport of `/`. One ALL-symbols WebSocket feeds the watchlist, the
 * rolling price, the live trade line and the 1m candle tail.
 *
 * Desktop: wide main column (hero, live line, candles) + narrow rail
 * (watchlist, stats, alerts). Mobile: watchlist chips, hero, charts, rail.
 */
export function LiveDashboardSection() {
  const [symbol, setSymbol] = useState("BTC");
  const { data: symbols } = useQuery({
    queryKey: ["symbols"],
    queryFn: api.symbols,
    staleTime: 60 * 60 * 1000,
  });
  const { status, latestBySymbol, series } = useLiveTrades("ALL");
  const now = useNowSeconds();

  const prices: Record<string, number | undefined> = {};
  const lastTradeAt: Record<string, number | undefined> = {};
  for (const [sym, pts] of Object.entries(series)) {
    prices[sym] = pts.at(-1)?.value;
    lastTradeAt[sym] = pts.at(-1)?.time;
  }

  const meta = symbols?.find((s) => s.symbol === symbol);
  const newest = useLiveWindow(symbol, series[symbol] ?? []).data.at(-1); // seeded or streamed
  const price = prices[symbol] ?? newest?.value ?? latestBySymbol[symbol]?.close;
  const { pct, window } = useChange(symbol, price);

  return (
    <div className="mx-auto grid w-full max-w-[1440px] grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] lg:grid-rows-[auto_1fr]">
      <div className="px-4 pt-4 sm:px-8 lg:col-start-2 lg:row-start-1 lg:border-l lg:bg-mist/50 lg:px-6 lg:pt-8">
        <Watchlist
          symbols={symbols}
          prices={prices}
          lastTradeAt={lastTradeAt}
          now={now}
          selected={symbol}
          onSelect={setSymbol}
        />
      </div>

      <section aria-label={`${symbol} live price and candles`} className="min-w-0 space-y-7 px-4 pt-6 pb-12 sm:px-8 lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:pt-8">
        <PriceHero
          name={meta?.name ?? symbol}
          symbol={symbol}
          price={price}
          change={pct}
          changeLabel={window === "24h" ? "24 h" : "past hour"}
          provenance={
            <LiveProvenance
              status={status}
              symbol={symbol}
              lastTradeAt={newest?.time}
              now={now}
            />
          }
          aside={
            meta && (
              <Link href={`/coins/${meta.slug}`} className="pill pill-sm">
                Details
                <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
              </Link>
            )
          }
        />

        <LivePriceChart symbol={symbol} points={series[symbol] ?? []} />

        <PriceChart symbol={symbol} liveCandle={latestBySymbol[symbol]} />

        <div className="pt-6">
          <CandleTable symbol={symbol} />
        </div>
      </section>

      <aside className="space-y-10 px-4 pb-12 sm:px-8 lg:col-start-2 lg:row-start-2 lg:border-l lg:bg-mist/50 lg:px-6 lg:pt-10">
        <StatsPanel symbol={symbol} />
        <AlertsFeed symbol={symbol} />
      </aside>
    </div>
  );
}
