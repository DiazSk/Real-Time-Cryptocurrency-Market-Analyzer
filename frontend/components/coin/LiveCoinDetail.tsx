"use client";

import { useState } from "react";
import { Separator } from "@/components/ui/separator";
import CoinChart from "@/components/coin/CoinChart";
import CoinHeader from "@/components/coin/CoinHeader";
import { AlertsFeed } from "@/components/alerts/AlertsFeed";
import { useCryptoSocket } from "@/lib/ws";
import type { CoinDetail } from "@/lib/coingecko";

interface LiveCoinDetailProps {
  coinId: string;
  coin: CoinDetail;
  coinOHLCData: OHLCData[];
  /**
   * Our backend ticker for this coin (e.g. "BTC"), or null if this coin isn't
   * one of the 8 symbols our Flink pipeline tracks. When set, the header price
   * + chart get patched with WS candles and we show the AlertsFeed in the
   * "Recent Trades" slot.
   */
  supportedSymbol: string | null;
}

/**
 * Coin-detail client wrapper. Composes CoinHeader + CoinChart + AlertsFeed
 * (in coinpulse's "Recent Trades" slot, since our backend has no per-trade
 * stream — only PRICE_SPIKE/DROP alerts and aggregated candles).
 *
 * For coins that aren't backend-tracked, the chart still works (CoinGecko
 * static OHLC) and the alerts slot shows an empty-state.
 */
const LiveCoinDetail = ({
  coinId,
  coin,
  coinOHLCData,
  supportedSymbol,
}: LiveCoinDetailProps) => {
  const [liveInterval, setLiveInterval] = useState<"1s" | "1m">("1m");

  // Only open a WebSocket for symbols our backend actually streams. The hook
  // is unconditional in React (rules of hooks); we just point it at an
  // unused symbol when we don't have a supported one and ignore the result.
  const { latestBySymbol } = useCryptoSocket(supportedSymbol ?? "ALL");

  const liveCandle = supportedSymbol ? latestBySymbol[supportedSymbol] : undefined;
  const liveOhlcv: OHLCData | null = liveCandle
    ? [
        liveCandle.windowStart,
        liveCandle.open,
        liveCandle.high,
        liveCandle.low,
        liveCandle.close,
      ]
    : null;

  const livePrice = liveCandle?.close ?? coin.market_data.current_price.usd;
  const livePriceChangePercentage24h =
    coin.market_data.price_change_percentage_24h_in_currency.usd;
  const priceChangePercentage30d =
    coin.market_data.price_change_percentage_30d_in_currency.usd;
  const priceChange24h = coin.market_data.price_change_24h_in_currency.usd;

  return (
    <section id="live-data-wrapper">
      <CoinHeader
        name={coin.name}
        image={coin.image.large}
        livePrice={livePrice}
        livePriceChangePercentage24h={livePriceChangePercentage24h}
        priceChangePercentage30d={priceChangePercentage30d}
        priceChange24h={priceChange24h}
      />
      <Separator className="divider" />

      <div className="trend">
        <CoinChart
          coinId={coinId}
          data={coinOHLCData}
          liveOhlcv={liveOhlcv}
          mode={supportedSymbol ? "live" : "historical"}
          initialPeriod="daily"
          liveInterval={supportedSymbol ? liveInterval : undefined}
          setLiveInterval={supportedSymbol ? setLiveInterval : undefined}
        >
          <h4>Trend Overview</h4>
        </CoinChart>
      </div>

      <Separator className="divider" />

      <div className="trades">
        <h4>
          Recent Alerts
          {supportedSymbol && (
            <span className="ml-2 text-base text-purple-100 font-normal">— {supportedSymbol}</span>
          )}
        </h4>

        {supportedSymbol ? (
          <AlertsFeed symbol={supportedSymbol} />
        ) : (
          <div className="rounded-lg bg-dark-500 p-6 text-sm text-purple-100">
            Real-time price-spike/drop alerts are only available for tracked
            symbols (BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, MATIC).
          </div>
        )}
      </div>
    </section>
  );
};

export default LiveCoinDetail;
