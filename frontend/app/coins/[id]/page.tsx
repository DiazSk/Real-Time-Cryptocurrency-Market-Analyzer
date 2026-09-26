import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { getCoin, getCoinOHLC } from "@/lib/coingecko";
import { api } from "@/lib/api";
import { fmtCap, fmtUsd } from "@/lib/format";
import { AlertsFeed } from "@/components/alerts/AlertsFeed";
import Converter from "@/components/coin/Converter";
import LiveCoinDetail from "@/components/coin/LiveCoinDetail";
import { ExchangeListings } from "@/components/coin/ExchangeListings";
import { StatsPanel } from "@/components/stats/StatsPanel";
import { Change } from "@/components/ui/change";

/**
 * /coins/[id]. Metadata, listings and the untracked chart come from CoinGecko
 * via our server-only proxy. When the slug is one of the 8 pipeline-tracked
 * symbols, the live price, trade line, candles, stats and alerts are ours.
 *
 * Next.js 16: `params` is a Promise and must be awaited.
 */
function hostOf(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export default async function CoinDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const [coin, coinOHLCData, supportedSymbols] = await Promise.all([
    getCoin(id),
    getCoinOHLC(id, 1).catch(() => [] as OHLCData[]),
    api.symbols().catch(() => []),
  ]);

  const supportedSymbol = supportedSymbols.find((s) => s.slug === id)?.symbol ?? null;
  const md = coin.market_data;

  const facts: { label: string; value?: React.ReactNode; link?: string }[] = [
    { label: "Market cap", value: fmtCap(md.market_cap.usd) },
    { label: "Rank", value: coin.market_cap_rank ? `#${coin.market_cap_rank}` : "—" },
    { label: "Volume 24 h", value: fmtCap(md.total_volume.usd) },
    {
      label: "Change 24 h",
      value: (
        <Change value={md.price_change_24h_in_currency.usd}>
          {fmtUsd(Math.abs(md.price_change_24h_in_currency.usd))}
        </Change>
      ),
    },
    { label: "Change 30 d", value: <Change value={md.price_change_percentage_30d_in_currency.usd} /> },
    { label: "Website", link: coin.links.homepage?.[0] },
    { label: "Explorer", link: coin.links.blockchain_site?.[0] },
    { label: "Community", link: coin.links.subreddit_url },
  ];

  return (
    <main className="mx-auto grid w-full max-w-[1440px] flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-12 px-4 pt-6 pb-12 sm:px-8 lg:pt-8">
        <LiveCoinDetail
          coinId={id}
          coin={coin}
          coinOHLCData={coinOHLCData}
          supportedSymbol={supportedSymbol}
        />
        <ExchangeListings tickers={coin.tickers ?? []} />
      </div>

      <aside className="space-y-10 border-t px-4 pt-8 pb-12 sm:px-8 lg:border-t-0 lg:border-l lg:bg-mist/50 lg:px-6">
        {supportedSymbol ? (
          <>
            <StatsPanel symbol={supportedSymbol} />
            <AlertsFeed symbol={supportedSymbol} />
          </>
        ) : (
          <section aria-labelledby="alerts-na">
            <h2 id="alerts-na" className="heading mb-2">
              Anomaly alerts
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Z-score alerts come from our Flink detector, which runs only on the 8 tracked assets.{" "}
              {`${coin.name} isn't one of them, so there are none here.`}
            </p>
          </section>
        )}

        <Converter symbol={coin.symbol} icon={coin.image.small} priceList={md.current_price} />

        <section aria-labelledby="facts-heading">
          <h2 id="facts-heading" className="heading">
            Details
          </h2>
          <p className="caption mt-0.5 mb-3">CoinGecko</p>
          <dl className="divide-y">
            {facts.map(({ label, value, link }) =>
              link === undefined || link ? (
                <div key={label} className="flex items-center justify-between gap-4 py-2.5 text-sm">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="num text-right text-foreground">
                    {link ? (
                      <Link
                        href={link}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 hover:underline"
                      >
                        {hostOf(link)}
                        <ArrowUpRight size={13} strokeWidth={1.75} aria-hidden />
                      </Link>
                    ) : (
                      value
                    )}
                  </dd>
                </div>
              ) : null,
            )}
          </dl>
        </section>

        {coin.description?.en && (
          <section aria-labelledby="about-heading">
            <h2 id="about-heading" className="heading mb-2">
              About {coin.name}
            </h2>
            <div
              className="max-w-prose text-sm leading-relaxed text-muted-foreground [&_a]:text-foreground [&_a]:underline [&_a]:underline-offset-2"
              dangerouslySetInnerHTML={{ __html: coin.description.en }}
            />
          </section>
        )}
      </aside>
    </main>
  );
}
