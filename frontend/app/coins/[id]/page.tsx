import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { getCoin, getCoinOHLC } from "@/lib/coingecko";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import Converter from "@/components/coin/Converter";
import LiveCoinDetail from "@/components/coin/LiveCoinDetail";
import { ExchangeListings } from "@/components/coin/ExchangeListings";

/**
 * /coins/[id] — coin detail page.
 *
 * Strategy:
 *   - All static metadata (header, links, market cap, etc.) comes from
 *     CoinGecko via our server-only proxy.
 *   - Initial OHLC also from CoinGecko (1D / hourly).
 *   - If the CoinGecko slug matches one of our 8 backend-tracked symbols,
 *     we hand the corresponding ticker to <LiveCoinDetail> so it can open a
 *     WebSocket, merge live candles into the chart, and surface the
 *     AlertsFeed.
 *
 * Next.js 16: `params` is a Promise — must be awaited.
 */
const CoinDetailPage = async ({
  params,
}: {
  params: Promise<{ id: string }>;
}) => {
  const { id } = await params;

  const [coin, coinOHLCData, supportedSymbols] = await Promise.all([
    getCoin(id),
    getCoinOHLC(id, 1).catch(() => [] as OHLCData[]),
    api.symbols().catch(() => []),
  ]);

  // Map coingecko slug → our ticker (e.g. "bitcoin" → "BTC"). null when this
  // coin isn't one of the symbols our Flink pipeline tracks.
  const match = supportedSymbols.find((s) => s.slug === id);
  const supportedSymbol = match?.symbol ?? null;

  const coinDetails = [
    {
      label: "Market Cap",
      value: formatCurrency(coin.market_data.market_cap.usd),
    },
    {
      label: "Market Cap Rank",
      value: coin.market_cap_rank ? `# ${coin.market_cap_rank}` : "—",
    },
    {
      label: "Total Volume",
      value: formatCurrency(coin.market_data.total_volume.usd),
    },
    {
      label: "Website",
      link: coin.links.homepage?.[0],
      linkText: "Homepage",
    },
    {
      label: "Explorer",
      link: coin.links.blockchain_site?.[0],
      linkText: "Explorer",
    },
    {
      label: "Community",
      link: coin.links.subreddit_url,
      linkText: "Community",
    },
  ];

  return (
    <main id="coin-details-page">
      <section className="primary">
        <LiveCoinDetail
          coinId={id}
          coin={coin}
          coinOHLCData={coinOHLCData}
          supportedSymbol={supportedSymbol}
        />

        <ExchangeListings tickers={coin.tickers ?? []} />
      </section>

      <section className="secondary">
        <Converter
          symbol={coin.symbol}
          icon={coin.image.small}
          priceList={coin.market_data.current_price}
        />

        <div className="details">
          <h4>Coin Details</h4>

          <ul className="details-grid">
            {coinDetails.map(({ label, value, link, linkText }, index) => (
              <li key={index}>
                <p className="label">{label}</p>

                {link ? (
                  <div className="link">
                    <Link href={link} target="_blank" rel="noreferrer noopener">
                      {linkText || label}
                    </Link>
                    <ArrowUpRight size={16} />
                  </div>
                ) : (
                  <p className="text-base font-medium">{value}</p>
                )}
              </li>
            ))}
          </ul>
        </div>

        {coin.description?.en && (
          <div className="details">
            <h4>About {coin.name}</h4>
            <div
              className="coin-description text-sm text-purple-100 leading-relaxed bg-dark-500 p-5 rounded-lg [&_a]:text-green-400 [&_a:hover]:underline"
              dangerouslySetInnerHTML={{ __html: coin.description.en }}
            />
          </div>
        )}
      </section>
    </main>
  );
};

export default CoinDetailPage;
