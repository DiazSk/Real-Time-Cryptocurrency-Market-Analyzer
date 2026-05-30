import { Suspense } from "react";
import { LiveTickerBar } from "@/components/ticker/LiveTickerBar";
import { LiveDashboardSection } from "@/components/LiveDashboardSection";
import {
  GlobalStatsBar,
  GlobalStatsBarSkeleton,
} from "@/components/cg/GlobalStatsBar";
import {
  MarketScreener,
  MarketScreenerSkeleton,
} from "@/components/cg/MarketScreener";
import {
  TrendingTile,
  TrendingTileSkeleton,
} from "@/components/cg/TrendingTile";
import {
  CategoriesTile,
  CategoriesTileSkeleton,
} from "@/components/cg/CategoriesTile";
import {
  CoinOverview,
  CoinOverviewSkeleton,
} from "@/components/cg/CoinOverview";

/**
 * Dashboard root. Server Component so it can host async CoinGecko-proxy tiles
 * (GlobalStatsBar, CoinOverview, MarketScreener, Trending, Categories)
 * alongside our WebSocket-driven live section (LiveDashboardSection).
 *
 * Next.js 16: `searchParams` is a Promise — must be awaited.
 */
export default async function Dashboard({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const params = await searchParams;
  const page = Number(params.page ?? "1") || 1;

  return (
    <main className="flex min-h-screen flex-col bg-background">
      <LiveTickerBar />

      <div className="px-6 pt-4">
        <Suspense fallback={<GlobalStatsBarSkeleton />}>
          <GlobalStatsBar />
        </Suspense>
      </div>

      <section className="px-6 pt-4">
        <div className="home-grid">
          <Suspense fallback={<CoinOverviewSkeleton />}>
            <CoinOverview />
          </Suspense>
          <Suspense fallback={<TrendingTileSkeleton />}>
            <TrendingTile />
          </Suspense>
        </div>
      </section>

      <LiveDashboardSection />

      <section className="space-y-4 px-6 pb-8">
        <Suspense fallback={<CategoriesTileSkeleton />}>
          <CategoriesTile />
        </Suspense>

        <Suspense
          key={`screener-${page}`}
          fallback={<MarketScreenerSkeleton />}
        >
          <MarketScreener page={page} />
        </Suspense>
      </section>
    </main>
  );
}
