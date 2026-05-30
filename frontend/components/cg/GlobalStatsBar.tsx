import { getGlobalStats } from "@/lib/coingecko";
import { fmtCap, fmtCount, fmtPct, pctClass } from "@/lib/format";
import clsx from "clsx";

/**
 * Top-of-page market-context strip. Server Component — calls CoinGecko's
 * /global endpoint server-side with 60s ISR caching.
 */
export async function GlobalStatsBar() {
  const { data } = await getGlobalStats();

  const totalCap = data.total_market_cap?.usd ?? null;
  const totalVol = data.total_volume?.usd ?? null;
  const btcDom = data.market_cap_percentage?.btc ?? null;
  const ethDom = data.market_cap_percentage?.eth ?? null;
  const capChange = data.market_cap_change_percentage_24h_usd;
  const activeCoins = data.active_cryptocurrencies;
  const markets = data.markets;

  return (
    <div
      className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-background-elev)] text-sm"
      role="status"
      aria-label="Global cryptocurrency market stats"
    >
      <Chip label="Market Cap" value={fmtCap(totalCap)}>
        <span className={clsx("num text-xs", pctClass(capChange))}>
          {fmtPct(capChange)}
        </span>
      </Chip>
      <Chip label="24h Vol" value={fmtCap(totalVol)} />
      <Chip
        label="BTC Dom"
        value={btcDom !== null ? `${btcDom.toFixed(1)}%` : "—"}
      />
      <Chip
        label="ETH Dom"
        value={ethDom !== null ? `${ethDom.toFixed(1)}%` : "—"}
      />
      <Chip label="Coins" value={fmtCount(activeCoins)} />
      <Chip label="Markets" value={fmtCount(markets)} />
    </div>
  );
}

function Chip({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[var(--color-muted-foreground)] uppercase tracking-wide text-[10px]">
        {label}
      </span>
      <span className="num font-medium">{value}</span>
      {children}
    </div>
  );
}

export function GlobalStatsBarSkeleton() {
  return (
    <div className="flex items-center gap-x-6 px-4 py-2 border border-[var(--color-border)] rounded-md bg-[var(--color-background-elev)] text-sm animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-baseline gap-2">
          <span className="h-3 w-12 bg-[var(--color-border)] rounded" />
          <span className="h-4 w-20 bg-[var(--color-border)] rounded" />
        </div>
      ))}
    </div>
  );
}
