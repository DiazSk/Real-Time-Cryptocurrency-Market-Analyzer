import Link from "next/link";
import Image from "next/image";

import { getTrending, type TrendingResponse } from "@/lib/coingecko";
import { fmtUsd } from "@/lib/format";
import DataTable from "@/components/DataTable";
import { Change } from "@/components/ui/change";

type TrendingCoin = TrendingResponse["coins"][number];

/** CoinGecko's most-searched coins (5 min ISR). */
export async function TrendingTile() {
  const data = await getTrending();
  const coins = data.coins.slice(0, 7);

  const columns: DataTableColumn<TrendingCoin>[] = [
    {
      header: "Coin",
      cell: ({ item }) => (
        <Link href={`/coins/${item.id}`} className="flex items-center gap-2.5 hover:underline">
          <Image src={item.small} alt="" width={20} height={20} className="rounded-full" />
          <span className="text-foreground">{item.name}</span>
          <span className="caption uppercase">{item.symbol}</span>
          <span className="absolute inset-0" aria-hidden />
        </Link>
      ),
    },
    {
      header: "Price",
      headClassName: "text-right",
      cellClassName: "text-right",
      cell: ({ item }) => fmtUsd(item.data?.price),
    },
    {
      header: "24 h",
      headClassName: "text-right",
      cellClassName: "text-right",
      cell: ({ item }) => <Change value={item.data?.price_change_percentage_24h?.usd} />,
    },
  ];

  return (
    <section aria-labelledby="trending-heading">
      <h3 id="trending-heading" className="heading mb-2">Trending searches</h3>
      <DataTable data={coins} columns={columns} rowKey={(c) => c.item.id} />
    </section>
  );
}

export function TrendingTileSkeleton() {
  return (
    <section>
      <h3 className="heading mb-2">Trending searches</h3>
      <div className="space-y-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="skeleton h-9" />
        ))}
      </div>
    </section>
  );
}
