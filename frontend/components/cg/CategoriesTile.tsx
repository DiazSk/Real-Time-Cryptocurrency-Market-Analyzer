import Image from "next/image";

import { getCategories, type Category } from "@/lib/coingecko";
import { fmtCap } from "@/lib/format";
import DataTable from "@/components/DataTable";
import { Change } from "@/components/ui/change";

/** Top categories by market cap from CoinGecko (10 min ISR). */
export async function CategoriesTile() {
  const cats = await getCategories({ limit: 7 });

  const columns: DataTableColumn<Category>[] = [
    {
      header: "Category",
      cellClassName: "max-w-[14rem] truncate text-foreground",
      cell: (c) => c.name,
    },
    {
      header: "Top coins",
      headClassName: "hidden sm:table-cell",
      cellClassName: "hidden sm:table-cell",
      cell: (c) => (
        <span className="flex -space-x-1.5">
          {c.top_3_coins.map((src) => (
            <Image key={src} src={src} alt="" width={20} height={20} className="rounded-full ring-2 ring-card" />
          ))}
        </span>
      ),
    },
    {
      header: "Market cap",
      headClassName: "text-right",
      cellClassName: "text-right",
      cell: (c) => fmtCap(c.market_cap),
    },
    {
      header: "24 h",
      headClassName: "text-right",
      cellClassName: "text-right",
      cell: (c) => <Change value={c.market_cap_change_24h} />,
    },
  ];

  return (
    <section aria-labelledby="categories-heading">
      <h3 id="categories-heading" className="heading mb-2">Top categories</h3>
      <DataTable columns={columns} data={cats} rowKey={(c) => c.id} />
    </section>
  );
}

export function CategoriesTileSkeleton() {
  return (
    <section>
      <h3 className="heading mb-2">Top categories</h3>
      <div className="space-y-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="skeleton h-9" />
        ))}
      </div>
    </section>
  );
}
