import Image from "next/image";
import Link from "next/link";

import { getMarketScreener } from "@/lib/coingecko";
import { cn, formatCurrency, formatPercentage } from "@/lib/utils";
import DataTable from "@/components/DataTable";
import CoinsPagination from "@/components/coin/CoinsPagination";

/**
 * /coins — paginated market screener backed by CoinGecko (via our server-only
 * proxy in lib/coingecko.ts). 10 coins per page; CoinGecko doesn't return a
 * total count, so we infer "has next page" from whether we got a full page.
 *
 * Next.js 16: `searchParams` is a Promise — must be awaited.
 */
const CoinsPage = async ({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) => {
  const { page } = await searchParams;
  const currentPage = Math.max(1, Number(page) || 1);
  const perPage = 10;

  const coinsData = await getMarketScreener({ page: currentPage, perPage });
  const hasMorePages = coinsData.length === perPage;
  const estimatedTotalPages = currentPage >= 100 ? Math.ceil(currentPage / 100) * 100 + 100 : 100;

  const columns: DataTableColumn<(typeof coinsData)[number]>[] = [
    {
      header: "Rank",
      cellClassName: "rank-cell",
      cell: (coin) => (
        <>
          #{coin.market_cap_rank ?? "—"}
          <Link href={`/coins/${coin.id}`} aria-label={`View ${coin.name}`} />
        </>
      ),
    },
    {
      header: "Token",
      cellClassName: "token-cell",
      cell: (coin) => (
        <div className="token-info">
          <Image src={coin.image} alt={coin.name} width={36} height={36} />
          <p>
            {coin.name} ({coin.symbol.toUpperCase()})
          </p>
        </div>
      ),
    },
    {
      header: "Price",
      cellClassName: "price-cell",
      cell: (coin) => formatCurrency(coin.current_price),
    },
    {
      header: "24h Change",
      cellClassName: "change-cell",
      cell: (coin) => {
        const change = coin.price_change_percentage_24h_in_currency ?? 0;
        const isTrendingUp = change > 0;
        return (
          <span
            className={cn("change-value", {
              "text-green-500": isTrendingUp,
              "text-red-500": !isTrendingUp,
            })}
          >
            {isTrendingUp && "+"}
            {formatPercentage(change)}
          </span>
        );
      },
    },
    {
      header: "Market Cap",
      cellClassName: "market-cap-cell",
      cell: (coin) => formatCurrency(coin.market_cap),
    },
  ];

  return (
    <main id="coins-page">
      <div className="content">
        <h4>All Coins</h4>

        <DataTable
          tableClassName="coins-table"
          columns={columns}
          data={coinsData}
          rowKey={(coin) => coin.id}
        />

        <CoinsPagination
          currentPage={currentPage}
          totalPages={estimatedTotalPages}
          hasMorePages={hasMorePages}
        />
      </div>
    </main>
  );
};

export default CoinsPage;
