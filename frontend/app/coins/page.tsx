import { Suspense } from "react";
import { MarketScreener, MarketScreenerSkeleton } from "@/components/cg/MarketScreener";

const PER_PAGE = 25;

/**
 * /coins: the CoinGecko market screener, paginated by `?page=N`.
 * Next.js 16: `searchParams` is a Promise and must be awaited.
 */
export default async function CoinsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const { page } = await searchParams;
  const currentPage = Math.max(1, Number(page) || 1);

  return (
    <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-8 sm:px-8 lg:py-12">
      <h1 className="text-[clamp(2rem,4vw,3rem)] font-extralight tracking-[-0.03em]">Markets</h1>
      <p className="caption mt-2 max-w-prose">
        All coins by market cap from CoinGecko, cached for 60 s on our server. The 8 assets our pipeline
        tracks (BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, POL) open with live trades; every other coin charts from
        CoinGecko.
      </p>

      <div className="mt-8">
        <Suspense key={currentPage} fallback={<MarketScreenerSkeleton perPage={PER_PAGE} />}>
          <MarketScreener page={currentPage} perPage={PER_PAGE} paginate />
        </Suspense>
      </div>
    </main>
  );
}
