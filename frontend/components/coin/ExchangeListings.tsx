import Link from "next/link";

import DataTable from "@/components/DataTable";
import { formatCurrency, timeAgo } from "@/lib/utils";
import type { Ticker } from "@/lib/coingecko";

/**
 * Renders the CoinGecko `tickers` array for a coin as a styled DataTable.
 * Visual rules live under `#coin-details-page .exchange-table` in
 * globals.css (lifted from coinpulse).
 */
export function ExchangeListings({ tickers }: { tickers: Ticker[] }) {
  // CoinGecko returns up to ~100 tickers; show the top 10 by USD volume.
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
      cellClassName: "exchange-name",
      cell: (t) =>
        t.trade_url ? (
          <>
            {t.market.name}
            <Link href={t.trade_url} target="_blank" rel="noreferrer noopener" />
          </>
        ) : (
          t.market.name
        ),
    },
    {
      header: "Pair",
      cellClassName: "pair",
      cell: (t) => (
        <>
          <p>{t.base}</p>
          <p>/</p>
          <p>{t.target}</p>
        </>
      ),
    },
    {
      header: "Price",
      cellClassName: "price-cell",
      cell: (t) => formatCurrency(t.converted_last?.usd ?? 0),
    },
    {
      header: "Last Updated",
      cellClassName: "time-cell",
      cell: (t) => (t.timestamp ? timeAgo(t.timestamp) : "—"),
    },
  ];

  return (
    <div className="exchange-section">
      <h4>Exchange Listings</h4>
      <DataTable
        data={top}
        columns={columns}
        rowKey={(t, i) => `${t.market.name}-${t.base}-${t.target}-${i}`}
        tableClassName="exchange-table"
      />
    </div>
  );
}
