import Image from "next/image";

import { getCoin, getCoinOHLC } from "@/lib/coingecko";
import { formatCurrency } from "@/lib/utils";
import CoinChart from "@/components/coin/CoinChart";

/**
 * Bitcoin hero block — mirrors coinpulse's home-grid hero. Server Component
 * that fetches BTC metadata + initial 1D hourly OHLC, then hands them to the
 * client-side CoinChart for rendering. Visual styling under `#coin-overview`
 * in globals.css.
 */
export async function CoinOverview() {
  const [coin, ohlc] = await Promise.all([
    getCoin("bitcoin"),
    getCoinOHLC("bitcoin", 1).catch(() => [] as OHLCData[]),
  ]);

  return (
    <div id="coin-overview">
      <CoinChart data={ohlc} coinId="bitcoin">
        <div className="header pt-2">
          <Image src={coin.image.large} alt={coin.name} width={56} height={56} />
          <div className="info">
            <p>
              {coin.name} / {coin.symbol.toUpperCase()}
            </p>
            <h1>{formatCurrency(coin.market_data.current_price.usd)}</h1>
          </div>
        </div>
      </CoinChart>
    </div>
  );
}

export function CoinOverviewSkeleton() {
  return (
    <div id="coin-overview-fallback">
      <div className="header pt-2">
        <div className="header-image skeleton" />
        <div className="info">
          <div className="header-line-sm skeleton" />
          <div className="header-line-lg skeleton" />
        </div>
      </div>
      <div className="chart">
        <div className="chart-skeleton skeleton" />
      </div>
    </div>
  );
}
