import Image from "next/image";
import { TrendingDown, TrendingUp } from "lucide-react";

import { getCategories, type Category } from "@/lib/coingecko";
import { cn, formatCurrency, formatPercentage } from "@/lib/utils";
import DataTable from "@/components/DataTable";

/**
 * Top-10 categories by market cap. Server Component, 10-minute ISR. Visual
 * styling under `#categories` in globals.css (lifted from coinpulse).
 */
export async function CategoriesTile() {
  const cats = await getCategories({ limit: 10 });

  const columns: DataTableColumn<Category>[] = [
    {
      header: "Category",
      cellClassName: "category-cell",
      cell: (category) => category.name,
    },
    {
      header: "Top Gainers",
      cellClassName: "top-gainers-cell",
      cell: (category) =>
        category.top_3_coins.map((coin) => (
          <Image src={coin} alt="" key={coin} width={28} height={28} />
        )),
    },
    {
      header: "24h Change",
      cellClassName: "change-header-cell",
      cell: (category) => {
        const change = category.market_cap_change_24h ?? 0;
        const isTrendingUp = change > 0;
        return (
          <div
            className={cn(
              "change-cell",
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
      header: "Market Cap",
      cellClassName: "market-cap-cell",
      cell: (category) => formatCurrency(category.market_cap),
    },
    {
      header: "24h Volume",
      cellClassName: "volume-cell",
      cell: (category) => formatCurrency(category.volume_24h),
    },
  ];

  return (
    <div id="categories" className="custom-scrollbar">
      <h4>Top Categories</h4>

      <DataTable
        columns={columns}
        data={cats}
        rowKey={(_, index) => index}
        tableClassName="mt-3"
      />
    </div>
  );
}

export function CategoriesTileSkeleton() {
  const dummy = Array.from({ length: 10 }, (_, i) => ({ id: i }));

  return (
    <div id="categories-fallback">
      <h4>Top Categories</h4>
      <DataTable
        columns={
          [
            {
              header: "Category",
              cellClassName: "category-cell",
              cell: () => <div className="category-skeleton skeleton" />,
            },
            {
              header: "Top Gainers",
              cellClassName: "top-gainers-cell",
              cell: () => (
                <div className="flex gap-1">
                  <div className="coin-skeleton skeleton" />
                  <div className="coin-skeleton skeleton" />
                  <div className="coin-skeleton skeleton" />
                </div>
              ),
            },
            {
              header: "24h Change",
              cellClassName: "change-header-cell",
              cell: () => (
                <div className="change-cell">
                  <div className="change-icon skeleton" />
                  <div className="value-skeleton-sm skeleton" />
                </div>
              ),
            },
            {
              header: "Market Cap",
              cellClassName: "market-cap-cell",
              cell: () => <div className="value-skeleton-lg skeleton" />,
            },
            {
              header: "24h Volume",
              cellClassName: "volume-cell",
              cell: () => <div className="value-skeleton-md skeleton" />,
            },
          ] as DataTableColumn<{ id: number }>[]
        }
        data={dummy}
        rowKey={(item) => item.id}
        tableClassName="mt-3"
      />
    </div>
  );
}
