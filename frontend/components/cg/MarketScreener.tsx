import Link from "next/link";
import { getMarketScreener, type MarketCoin } from "@/lib/coingecko";
import { fmtCap, fmtPct, fmtUsd, pctClass } from "@/lib/format";
import { Sparkline } from "./Sparkline";

export interface MarketScreenerProps {
  page: number;
  perPage?: number;
}

/**
 * Paginated market screener. Server Component — page is derived from
 * page.tsx's `?page=N` searchParam and passed in as a prop.
 *
 * CoinGecko's /coins/markets doesn't return a total count, so we infer
 * "has next page" from whether we got back a full page of results.
 */
export async function MarketScreener({ page, perPage = 10 }: MarketScreenerProps) {
  const safePage = Math.max(1, Math.floor(page) || 1);
  const coins = await getMarketScreener({ page: safePage, perPage });
  const hasNext = coins.length === perPage;
  const hasPrev = safePage > 1;

  return (
    <section className="border border-[var(--color-border)] rounded-md bg-[var(--color-background-elev)] overflow-hidden">
      <header className="flex items-baseline justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <h2 className="text-sm font-semibold uppercase tracking-wide">
          Market Screener
        </h2>
        <span className="text-[var(--color-muted-foreground)] text-xs">
          top {perPage * safePage} by market cap · page {safePage}
        </span>
      </header>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-[var(--color-muted-foreground)] text-xs uppercase tracking-wide">
            <tr className="border-b border-[var(--color-border)]">
              <Th className="text-right w-10">#</Th>
              <Th>Coin</Th>
              <Th className="text-right">Price</Th>
              <Th className="text-right hidden md:table-cell">1h</Th>
              <Th className="text-right">24h</Th>
              <Th className="text-right hidden md:table-cell">7d</Th>
              <Th className="text-right hidden lg:table-cell">Market Cap</Th>
              <Th className="text-right hidden lg:table-cell">Vol (24h)</Th>
              <Th className="text-center hidden md:table-cell">7d</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {coins.map((c) => (
              <Row key={c.id} c={c} />
            ))}
            {coins.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-8 text-center text-[var(--color-muted-foreground)]"
                >
                  No coins on this page.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <footer className="flex items-center justify-between px-4 py-3 border-t border-[var(--color-border)] text-xs">
        <Link
          href={hasPrev ? `?page=${safePage - 1}` : "?page=1"}
          aria-disabled={!hasPrev}
          tabIndex={hasPrev ? 0 : -1}
          className={
            hasPrev
              ? "text-[var(--color-foreground)] hover:text-[var(--color-accent)]"
              : "text-[var(--color-muted-foreground)] pointer-events-none"
          }
          scroll={false}
        >
          ← Previous
        </Link>
        <span className="text-[var(--color-muted-foreground)]">Page {safePage}</span>
        <Link
          href={`?page=${safePage + 1}`}
          aria-disabled={!hasNext}
          tabIndex={hasNext ? 0 : -1}
          className={
            hasNext
              ? "text-[var(--color-foreground)] hover:text-[var(--color-accent)]"
              : "text-[var(--color-muted-foreground)] pointer-events-none"
          }
          scroll={false}
        >
          Next →
        </Link>
      </footer>
    </section>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th className={`px-3 py-2 font-medium ${className}`} scope="col">
      {children}
    </th>
  );
}

function Row({ c }: { c: MarketCoin }) {
  const change24h = c.price_change_percentage_24h_in_currency;
  const change1h = c.price_change_percentage_1h_in_currency;
  const change7d = c.price_change_percentage_7d_in_currency;
  const sparkPrices = c.sparkline_in_7d?.price ?? [];

  return (
    <tr className="hover:bg-[var(--color-background-elev-2)] transition-colors">
      <td className="px-3 py-2.5 text-right num text-[var(--color-muted-foreground)]">
        {c.market_cap_rank ?? "—"}
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={c.image}
            alt=""
            width={20}
            height={20}
            className="rounded-full"
          />
          <span className="font-medium">{c.name}</span>
          <span className="text-[var(--color-muted-foreground)] uppercase text-xs">
            {c.symbol}
          </span>
        </div>
      </td>
      <td className="px-3 py-2.5 text-right num">{fmtUsd(c.current_price)}</td>
      <td
        className={`px-3 py-2.5 text-right num hidden md:table-cell ${pctClass(change1h ?? 0)}`}
      >
        {change1h !== null ? fmtPct(change1h) : "—"}
      </td>
      <td className={`px-3 py-2.5 text-right num ${pctClass(change24h ?? 0)}`}>
        {change24h !== null ? fmtPct(change24h) : "—"}
      </td>
      <td
        className={`px-3 py-2.5 text-right num hidden md:table-cell ${pctClass(change7d ?? 0)}`}
      >
        {change7d !== null ? fmtPct(change7d) : "—"}
      </td>
      <td className="px-3 py-2.5 text-right num hidden lg:table-cell">
        {fmtCap(c.market_cap)}
      </td>
      <td className="px-3 py-2.5 text-right num hidden lg:table-cell">
        {fmtCap(c.total_volume)}
      </td>
      <td className="px-3 py-2.5 hidden md:table-cell">
        <div className="flex justify-center">
          <Sparkline prices={sparkPrices} />
        </div>
      </td>
    </tr>
  );
}

export function MarketScreenerSkeleton({ perPage = 10 }: { perPage?: number }) {
  return (
    <section className="border border-[var(--color-border)] rounded-md bg-[var(--color-background-elev)] animate-pulse">
      <header className="px-4 py-3 border-b border-[var(--color-border)]">
        <div className="h-4 w-40 bg-[var(--color-border)] rounded" />
      </header>
      <div className="divide-y divide-[var(--color-border)]">
        {Array.from({ length: perPage }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <div className="w-5 h-5 bg-[var(--color-border)] rounded-full" />
            <div className="h-3 flex-1 bg-[var(--color-border)] rounded" />
            <div className="h-3 w-20 bg-[var(--color-border)] rounded" />
            <div className="h-3 w-16 bg-[var(--color-border)] rounded" />
          </div>
        ))}
      </div>
    </section>
  );
}
