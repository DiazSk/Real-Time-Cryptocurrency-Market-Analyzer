import Link from "next/link";
import Image from "next/image";
import { TrendingDown, TrendingUp } from "lucide-react";

import { getTrending, type TrendingResponse } from "@/lib/coingecko";
import { cn, formatCurrency, formatPercentage } from "@/lib/utils";
import DataTable from "@/components/DataTable";

type TrendingCoin = TrendingResponse["coins"][number];

/**
 * Top-7 trending coins on CoinGecko by search volume.
 * Server Component, 5-minute ISR. Visual styling lives under
 * `#trending-coins` in globals.css (lifted from coinpulse).
 */
export async function TrendingTile() {
  const data = await getTrending();
  const coins = data.coins.slice(0, 6);

  const columns: DataTableColumn<TrendingCoin>[] = [
    {
      header: "Name",
      cellClassName: "name-cell",
      cell: ({ item }) => (
        <Link href={`/coins/${item.id}`}>
          <Image src={item.large} alt={item.name} width={36} height={36} />
          <p>{item.name}</p>
        </Link>
      ),
    },
    {
      header: "24h Change",
      cellClassName: "change-cell",
      cell: ({ item }) => {
        const change = item.data?.price_change_percentage_24h?.usd ?? 0;
        const isTrendingUp = change > 0;
        return (
          <div
            className={cn(
              "price-change",
              isTrendingUp ? "text-green-500" : "text-red-500",
            )}
          >
            <p className="flex items-center">
              {formatPercentage(change)}
              {isTrendingUp ? (
                <TrendingUp width={16} height={16} />
              ) : (
                <TrendingDown width={16} height={16} />
              )}
            </p>
          </div>
        );
      },
    },
    {
      header: "Price",
      cellClassName: "price-cell",
      cell: ({ item }) =>
        item.data?.price !== undefined ? formatCurrency(item.data.price) : "—",
    },
  ];

  return (
    <div id="trending-coins">
      <h4>Trending Coins</h4>

      <DataTable
        data={coins}
        columns={columns}
        rowKey={(coin) => coin.item.id}
        tableClassName="trending-coins-table"
        headerCellClassName="py-3!"
        bodyCellClassName="py-2!"
      />
    </div>
  );
}

export function TrendingTileSkeleton() {
  const dummy = Array.from({ length: 6 }, (_, i) => ({ id: i }));

  return (
    <div id="trending-coins-fallback">
      <h4>Trending Coins</h4>
      <DataTable
        data={dummy}
        columns={
          [
            {
              header: "Name",
              cell: () => (
                <div className="name-link">
                  <div className="name-image skeleton" />
                  <div className="name-line skeleton" />
                </div>
              ),
            },
            {
              header: "24h Change",
              cell: () => (
                <div className="price-change">
                  <div className="change-icon skeleton" />
                  <div className="change-line skeleton" />
                </div>
              ),
            },
            {
              header: "Price",
              cell: () => <div className="price-line skeleton" />,
            },
          ] as DataTableColumn<{ id: number }>[]
        }
        rowKey={(item) => item.id}
        tableClassName="trending-coins-table"
      />
    </div>
  );
}
