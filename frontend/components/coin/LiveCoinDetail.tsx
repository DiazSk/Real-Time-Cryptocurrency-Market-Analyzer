"use client";

import { LivePriceChart } from "@/components/coin/LivePriceChart";
import { LiveProvenance, PriceHero } from "@/components/coin/PriceHero";
import { PriceChart } from "@/components/coin/PriceChart";
import type { CoinDetail } from "@/lib/coingecko";
import { useLiveTrades, useNowSeconds } from "@/lib/ws";

interface LiveCoinDetailProps {
  coinId: string;
  coin: CoinDetail;
  coinOHLCData: OHLCData[];
  /** Our ticker (e.g. "BTC") when the pipeline tracks this coin, else null. */
  supportedSymbol: string | null;
}

/**
 * Coin-detail main column. Tracked coins get the live trade line and our
 * candles; untracked coins chart from CoinGecko and say why there is no live line.
 * Split in two so untracked coins never open a WebSocket.
 */
export default function LiveCoinDetail(props: LiveCoinDetailProps) {
  return props.supportedSymbol ? (
    <TrackedDetail {...props} symbol={props.supportedSymbol} />
  ) : (
    <UntrackedDetail {...props} />
  );
}

const cgChange = (coin: CoinDetail) => coin.market_data.price_change_percentage_24h_in_currency.usd;

function TrackedDetail({ coin, symbol }: LiveCoinDetailProps & { symbol: string }) {
  const { status, latestBySymbol, series } = useLiveTrades(symbol);
  const now = useNowSeconds();
  const pts = series[symbol] ?? [];
  const last = pts.at(-1);
  const price = last?.value ?? latestBySymbol[symbol]?.close ?? coin.market_data.current_price.usd;

  return (
    <div className="space-y-10">
      <PriceHero
        name={coin.name}
        symbol={symbol}
        price={price}
        change={cgChange(coin)}
        changeLabel="24 h, CoinGecko"
        provenance={<LiveProvenance status={status} symbol={symbol} lastTradeAt={last?.time} now={now} />}
      />
      <LivePriceChart symbol={symbol} points={pts} />
      <PriceChart symbol={symbol} liveCandle={latestBySymbol[symbol]} />
    </div>
  );
}

function UntrackedDetail({ coin, coinId, coinOHLCData }: LiveCoinDetailProps) {
  return (
    <div className="space-y-10">
      <PriceHero
        name={coin.name}
        symbol={coin.symbol.toUpperCase()}
        price={coin.market_data.current_price.usd}
        change={cgChange(coin)}
        changeLabel="24 h"
        provenance={
          <>
            <span className="live-dot" data-state="idle" aria-hidden />
            <span>
              {`CoinGecko price, cached up to 2 min. Our pipeline tracks 8 assets and ${coin.name} isn't one of them, so there is no live trade line here.`}
            </span>
          </>
        }
      />
      <PriceChart symbol={null} coinId={coinId} initialOhlc={coinOHLCData} />
    </div>
  );
}
