import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import DataTable from "@/components/DataTable";
import { fmtUsd, timeAgo } from "@/lib/format";
import type { Ticker } from "@/lib/coingecko";

/** The coin's top 10 CoinGecko tickers by USD volume. */
export function ExchangeListings({ tickers }: { tickers: Ticker[] }) {
  const top = [...tickers]
    .sort(
      (a, b) =>
        (b.converted_last?.usd ?? 0) * (b.volume ?? 0) -
        (a.converted_last?.usd ?? 0) * (a.volume ?? 0),
    )
    .slice(0, 10);

  if (top.length === 0) return null;

  const columns: DataTableColumn<Ticker>[] = [
    {
      header: "Exchange",
      cellClassName: "text-foreground",
      cell: (t) =>
        t.trade_url ? (
          <Link
            href={t.trade_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 hover:underline"
          >
            {t.market.name}
            <ArrowUpRight size={13} strokeWidth={1.75} aria-hidden />
            <span className="sr-only">(opens in a new tab)</span>
          </Link>
        ) : (
          t.market.name
        ),
    },
    {
      header: "Pair",
      cellClassName: "text-muted-foreground",
      cell: (t) => `${t.base}/${t.target}`.slice(0, 24),
    },
    {
      header: "Price",
      headClassName: "text-right",
      cellClassName: "text-right",
      cell: (t) => fmtUsd(t.converted_last?.usd),
    },
    {
      header: "Updated",
      headClassName: "text-right",
      cellClassName: "text-right text-muted-foreground",
      cell: (t) => (t.timestamp ? timeAgo(t.timestamp) : "—"),
    },
  ];

  return (
    <section aria-labelledby="exchanges-heading">
      <h2 id="exchanges-heading" className="heading">
        Exchange listings
      </h2>
      <p className="caption mt-0.5 mb-2">Top 10 by USD volume · CoinGecko</p>
      <DataTable
        data={top}
        columns={columns}
        rowKey={(t, i) => `${t.market.name}-${t.base}-${t.target}-${i}`}
      />
    </section>
  );
}
