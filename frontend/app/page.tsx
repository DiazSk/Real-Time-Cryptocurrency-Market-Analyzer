import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { LiveDashboardSection } from "@/components/LiveDashboardSection";
import { GlobalStatsBar, GlobalStatsBarSkeleton } from "@/components/cg/GlobalStatsBar";
import { MarketScreener, MarketScreenerSkeleton } from "@/components/cg/MarketScreener";
import { TrendingTile, TrendingTileSkeleton } from "@/components/cg/TrendingTile";
import { CategoriesTile, CategoriesTileSkeleton } from "@/components/cg/CategoriesTile";

/**
 * Dashboard. The live section (our pipeline) owns the first viewport; the
 * CoinGecko market context sits below the fold, labelled as CoinGecko data.
 */
export default function Dashboard() {
  return (
    <main className="flex flex-1 flex-col">
      <LiveDashboardSection />

      <section aria-labelledby="context-heading" className="border-t bg-mist/40">
        <div className="mx-auto max-w-[1440px] space-y-12 px-4 py-12 sm:px-8 lg:py-16">
          <div>
            <h2 id="context-heading" className="text-2xl font-light tracking-[-0.015em]">
              Market context
            </h2>
            <p className="caption mt-1">
              CoinGecko data, not our pipeline · cached 1 to 10 min on our server
            </p>
          </div>

          <Suspense fallback={<GlobalStatsBarSkeleton />}>
            <GlobalStatsBar />
          </Suspense>

          <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
            <Suspense fallback={<TrendingTileSkeleton />}>
              <TrendingTile />
            </Suspense>
            <Suspense fallback={<CategoriesTileSkeleton />}>
              <CategoriesTile />
            </Suspense>
          </div>

          <div>
            <div className="mb-2 flex items-baseline justify-between gap-4">
              <h3 className="heading">Top 10 by market cap</h3>
              <Link
                href="/coins"
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
              >
                All markets <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
              </Link>
            </div>
            <Suspense fallback={<MarketScreenerSkeleton />}>
              <MarketScreener />
            </Suspense>
          </div>
        </div>
      </section>
    </main>
  );
}
