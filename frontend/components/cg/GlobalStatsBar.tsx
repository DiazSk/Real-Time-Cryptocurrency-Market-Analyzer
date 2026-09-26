import { getGlobalStats } from "@/lib/coingecko";
import { fmtCap, fmtCount } from "@/lib/format";
import { Change } from "@/components/ui/change";

/** Market-wide figures from CoinGecko /global (60 s ISR). An inline strip, not a hero. */
export async function GlobalStatsBar() {
  const { data } = await getGlobalStats();

  const btcDom = data.market_cap_percentage?.btc;
  const ethDom = data.market_cap_percentage?.eth;
  const items: [string, React.ReactNode][] = [
    [
      "Market cap",
      <>
        {fmtCap(data.total_market_cap?.usd)}{" "}
        <Change value={data.market_cap_change_percentage_24h_usd} className="ml-1 text-xs" iconSize={12} />
      </>,
    ],
    ["24 h volume", fmtCap(data.total_volume?.usd)],
    ["BTC dominance", btcDom !== undefined ? `${btcDom.toFixed(1)}%` : "—"],
    ["ETH dominance", ethDom !== undefined ? `${ethDom.toFixed(1)}%` : "—"],
    ["Active coins", fmtCount(data.active_cryptocurrencies)],
    ["Markets", fmtCount(data.markets)],
  ];

  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
      {items.map(([k, v]) => (
        <div key={k}>
          <dt className="caption">{k}</dt>
          <dd className="num mt-1 text-base text-foreground">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function GlobalStatsBarSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:grid-cols-6" aria-label="Loading market stats">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="space-y-1.5">
          <div className="skeleton h-3 w-20" />
          <div className="skeleton h-5 w-24" />
        </div>
      ))}
    </div>
  );
}
