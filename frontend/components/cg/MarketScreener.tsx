import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { getMarketScreener, type MarketCoin } from "@/lib/coingecko";
import { fmtCap, fmtUsd } from "@/lib/format";
import { Change } from "@/components/ui/change";
import { cn } from "@/lib/utils";
import { Sparkline } from "./Sparkline";

export interface MarketScreenerProps {
  page?: number;
  perPage?: number;
  /** Show previous/next links (the /coins page). */
  paginate?: boolean;
}

/**
 * CoinGecko /coins/markets by market cap (60 s ISR). CoinGecko returns no
 * total count, so "has next page" is inferred from a full page.
 */
export async function MarketScreener({ page = 1, perPage = 10, paginate = false }: MarketScreenerProps) {
  const safePage = Math.max(1, Math.floor(page) || 1);
  const coins = await getMarketScreener({ page: safePage, perPage });
  const hasNext = coins.length === perPage;
  const hasPrev = safePage > 1;

  return (
    <div>
      <div className="scroll-x">
        <table className="num w-full text-sm">
          <thead className="caption">
            <tr className="border-b">
              <Th className="w-10 pl-0 text-right">#</Th>
              <Th>Coin</Th>
              <Th className="text-right">Price</Th>
              <Th className="hidden text-right md:table-cell">1 h</Th>
              <Th className="text-right">24 h</Th>
              <Th className="hidden text-right md:table-cell">7 d</Th>
              <Th className="hidden text-right lg:table-cell">Market cap</Th>
              <Th className="hidden text-right lg:table-cell">Volume 24 h</Th>
              <Th className="hidden pr-0 text-right md:table-cell">Last 7 d</Th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {coins.map((c) => (
              <Row key={c.id} c={c} />
            ))}
            {coins.length === 0 && (
              <tr>
                <td colSpan={9} className="py-10 text-center text-muted-foreground">
                  CoinGecko returned no coins for page {safePage}.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {paginate && (
        <nav aria-label="Screener pages" className="mt-6 flex items-center justify-between gap-4">
          <PageLink href={`?page=${safePage - 1}`} disabled={!hasPrev}>
            <ArrowLeft size={14} strokeWidth={1.75} aria-hidden /> Previous
          </PageLink>
          <span className="caption num">Page {safePage}</span>
          <PageLink href={`?page=${safePage + 1}`} disabled={!hasNext}>
            Next <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
          </PageLink>
        </nav>
      )}
    </div>
  );
}

function PageLink({ href, disabled, children }: { href: string; disabled: boolean; children: React.ReactNode }) {
  if (disabled) {
    return (
      <span className="pill pointer-events-none opacity-40 shadow-none" aria-disabled>
        {children}
      </span>
    );
  }
  return (
    <Link href={href} className="pill">
      {children}
    </Link>
  );
}

function Th({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={cn("px-3 py-2.5 text-left font-normal whitespace-nowrap", className)} scope="col">
      {children}
    </th>
  );
}

function Row({ c }: { c: MarketCoin }) {
  return (
    <tr className="relative transition-colors hover:bg-mist/60">
      <td className="py-3 pr-3 pl-0 text-right text-muted-foreground">{c.market_cap_rank ?? "—"}</td>
      <td className="px-3 py-3">
        <Link href={`/coins/${c.id}`} className="flex items-center gap-2.5 whitespace-nowrap hover:underline">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={c.image} alt="" width={20} height={20} className="rounded-full" />
          <span className="text-foreground">{c.name}</span>
          <span className="caption uppercase">{c.symbol}</span>
          <span className="absolute inset-0" aria-hidden />
        </Link>
      </td>
      <td className="px-3 py-3 text-right text-foreground">{fmtUsd(c.current_price)}</td>
      <td className="hidden px-3 py-3 text-right md:table-cell">
        <Change value={c.price_change_percentage_1h_in_currency} />
      </td>
      <td className="px-3 py-3 text-right">
        <Change value={c.price_change_percentage_24h_in_currency} />
      </td>
      <td className="hidden px-3 py-3 text-right md:table-cell">
        <Change value={c.price_change_percentage_7d_in_currency} />
      </td>
      <td className="hidden px-3 py-3 text-right lg:table-cell">{fmtCap(c.market_cap)}</td>
      <td className="hidden px-3 py-3 text-right lg:table-cell">{fmtCap(c.total_volume)}</td>
      <td className="hidden py-3 pr-0 pl-3 md:table-cell">
        <div className="flex justify-end">
          <Sparkline prices={c.sparkline_in_7d?.price ?? []} stroke="var(--muted-foreground)" width={88} height={24} />
        </div>
      </td>
    </tr>
  );
}

export function MarketScreenerSkeleton({ perPage = 10 }: { perPage?: number }) {
  return (
    <div className="space-y-2" aria-label="Loading screener">
      {Array.from({ length: perPage }).map((_, i) => (
        <div key={i} className="skeleton h-10" />
      ))}
    </div>
  );
}
