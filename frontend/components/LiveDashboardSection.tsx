"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SymbolPicker } from "@/components/chart/SymbolPicker";
import CoinChart from "@/components/coin/CoinChart";
import { StatsPanel } from "@/components/stats/StatsPanel";
import { AlertsFeed } from "@/components/alerts/AlertsFeed";
import { CandleTable } from "@/components/ohlc/CandleTable";
import { api } from "@/lib/api";
import { fetchCoinOHLC } from "@/lib/coingecko-actions";
import { useCryptoSocket } from "@/lib/ws";

/**
 * Client-side wrapper for the home dashboard's live section. Uses the same
 * coinpulse-styled CoinChart as /coins/[id] for visual parity:
 *   - CoinGecko-backed hourly OHLC as the static layer (rich, period-switchable)
 *   - Our /ws/prices/{symbol} live candle merged in as the trailing tick
 *
 * Our 1-min Flink-aggregated candles are still surfaced — see the
 * CandleTable + StatsPanel + AlertsFeed below.
 */
export function LiveDashboardSection() {
  const [symbol, setSymbol] = useState("BTC");

  const { data: symbols } = useQuery({
    queryKey: ["symbols"],
    queryFn: api.symbols,
    staleTime: 60 * 60 * 1000,
  });

  const slug = symbols?.find((s) => s.symbol === symbol)?.slug ?? null;

  const { data: ohlcData = [] } = useQuery({
    queryKey: ["coin-ohlc-init", slug],
    queryFn: () => fetchCoinOHLC(slug as string, 1),
    enabled: !!slug,
    staleTime: 60_000,
  });

  const { latestBySymbol } = useCryptoSocket(symbol);
  const liveCandle = latestBySymbol[symbol];
  const liveOhlcv: OHLCData | null = liveCandle
    ? [
        liveCandle.windowStart,
        liveCandle.open,
        liveCandle.high,
        liveCandle.low,
        liveCandle.close,
      ]
    : null;

  return (
    <>
      <header className="border-b border-[color:var(--color-border)] px-6 py-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              Crypto Market Analyzer
            </h1>
            <p className="text-sm text-muted-foreground">
              Real-time terminal · Flink-driven 1-min candles · Pub/Sub alerts
            </p>
          </div>
          <SymbolPicker value={symbol} onChange={setSymbol} />
        </div>
      </header>

      <section className="space-y-4 px-6 py-5">
        <StatsPanel symbol={symbol} />

        {slug && (
          <CoinChart
            coinId={slug}
            data={ohlcData}
            liveOhlcv={liveOhlcv}
            mode="live"
            initialPeriod="daily"
          />
        )}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <AlertsFeed symbol={symbol} />
          <CandleTable symbol={symbol} />
        </div>
      </section>
    </>
  );
}
