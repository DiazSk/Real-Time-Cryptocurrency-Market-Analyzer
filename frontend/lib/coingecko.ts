/**
 * Server-side CoinGecko REST proxy.
 *
 * All functions here MUST only be called from Server Components, Server Actions,
 * or Route Handlers. The `server-only` import below is a build-time guard:
 * if this module is ever pulled into a Client Component, the build fails
 * immediately rather than silently exposing process.env to the browser bundle.
 *
 * Caching is delegated to Next.js ISR (`fetch(url, { next: { revalidate } })`).
 * The browser never makes a CoinGecko request; the Next.js server caches and
 * serves stale-while-revalidate.
 */
import "server-only";

const BASE_URL = process.env.COINGECKO_BASE_URL ?? "https://api.coingecko.com/api/v3";
const API_KEY = process.env.COINGECKO_API_KEY ?? "";

type FetchOpts = {
  /** Seconds. Passed to Next.js `fetch` `{ next: { revalidate } }`. */
  revalidate: number;
  /** Query params. Falsy values are skipped. */
  params?: Record<string, string | number | boolean | undefined>;
};

async function cgFetch<T>(path: string, opts: FetchOpts): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }

  const headers: HeadersInit = { Accept: "application/json" };
  if (API_KEY) {
    // Demo / free tier auth header. Pro tier would use x-cg-pro-api-key.
    headers["x-cg-demo-api-key"] = API_KEY;
  }

  const res = await fetch(url.toString(), {
    headers,
    next: { revalidate: opts.revalidate },
  });

  if (!res.ok) {
    // Don't include the URL in the message because it may contain the api key in headers we control;
    // still keep the path so logs are actionable.
    throw new Error(`CoinGecko ${path} failed: HTTP ${res.status} ${res.statusText}`);
  }

  return (await res.json()) as T;
}

// ─────────────────────────────────────────────────────────────────────────────
// Endpoint wrappers + response types
// ─────────────────────────────────────────────────────────────────────────────

export interface GlobalStats {
  data: {
    active_cryptocurrencies: number;
    markets: number;
    total_market_cap: Record<string, number>;
    total_volume: Record<string, number>;
    market_cap_percentage: Record<string, number>;
    market_cap_change_percentage_24h_usd: number;
    updated_at: number;
  };
}

export function getGlobalStats(): Promise<GlobalStats> {
  return cgFetch<GlobalStats>("/global", { revalidate: 60 });
}

export interface MarketCoin {
  id: string;
  symbol: string;
  name: string;
  image: string;
  current_price: number | null;
  market_cap: number | null;
  market_cap_rank: number | null;
  total_volume: number | null;
  high_24h: number | null;
  low_24h: number | null;
  price_change_percentage_1h_in_currency: number | null;
  price_change_percentage_24h_in_currency: number | null;
  price_change_percentage_7d_in_currency: number | null;
  sparkline_in_7d: { price: number[] } | null;
}

export function getMarketScreener(args: {
  page?: number;
  perPage?: number;
}): Promise<MarketCoin[]> {
  return cgFetch<MarketCoin[]>("/coins/markets", {
    revalidate: 60,
    params: {
      vs_currency: "usd",
      order: "market_cap_desc",
      per_page: args.perPage ?? 10,
      page: args.page ?? 1,
      sparkline: true,
      price_change_percentage: "1h,24h,7d",
    },
  });
}

export interface TrendingResponse {
  coins: Array<{
    item: {
      id: string;
      coin_id: number;
      name: string;
      symbol: string;
      market_cap_rank: number | null;
      thumb: string;
      small: string;
      large: string;
      score: number;
      data?: {
        price?: number;
        price_change_percentage_24h?: { usd?: number };
        sparkline?: string;
      };
    };
  }>;
}

export function getTrending(): Promise<TrendingResponse> {
  return cgFetch<TrendingResponse>("/search/trending", { revalidate: 300 });
}

export interface Category {
  id: string;
  name: string;
  market_cap: number | null;
  market_cap_change_24h: number | null;
  content: string;
  top_3_coins: string[];
  volume_24h: number | null;
  updated_at: string;
}

export function getCategories(args: { limit?: number } = {}): Promise<Category[]> {
  return cgFetch<Category[]>("/coins/categories", {
    revalidate: 600,
    params: { order: "market_cap_desc" },
  }).then((rows) => (args.limit ? rows.slice(0, args.limit) : rows));
}

// ─────────────────────────────────────────────────────────────────────────────
// Coin detail — used by /coins/[id] route
// ─────────────────────────────────────────────────────────────────────────────

export interface Ticker {
  market: { name: string; identifier?: string };
  base: string;
  target: string;
  last: number;
  volume: number;
  converted_last: { usd: number } & Record<string, number>;
  timestamp: string;
  trade_url: string | null;
}

export interface CoinDetail {
  id: string;
  name: string;
  symbol: string;
  asset_platform_id?: string | null;
  image: {
    large: string;
    small: string;
    thumb: string;
  };
  market_data: {
    current_price: Record<string, number>;
    price_change_24h_in_currency: { usd: number } & Record<string, number>;
    price_change_percentage_24h_in_currency: { usd: number } & Record<string, number>;
    price_change_percentage_30d_in_currency: { usd: number } & Record<string, number>;
    market_cap: { usd: number } & Record<string, number>;
    total_volume: { usd: number } & Record<string, number>;
  };
  market_cap_rank: number | null;
  description: { en: string };
  links: {
    homepage: string[];
    blockchain_site: string[];
    subreddit_url: string;
  };
  tickers: Ticker[];
}

export function getCoin(id: string): Promise<CoinDetail> {
  return cgFetch<CoinDetail>(`/coins/${id}`, {
    revalidate: 60,
    params: {
      localization: false,
      tickers: true,
      community_data: false,
      developer_data: false,
      sparkline: false,
    },
  });
}

/**
 * CoinGecko /coins/{id}/ohlc returns an array of [timestamp(ms), o, h, l, c]
 * tuples. We pass through that shape — components convert to lightweight-charts
 * format at render time.
 *
 * Note: `interval` and `precision` are Pro-tier-only parameters; including
 * them with a demo-tier key returns 400. `days=max` is also Pro-only — clamp
 * to 365 for the demo tier. Candle granularity is server-determined from
 * `days` (1d → 30-min candles, 2-30d → 4h, 31+ → 4d).
 */
export function getCoinOHLC(id: string, days: number | "max"): Promise<OHLCData[]> {
  const safeDays = days === "max" ? 365 : days;
  return cgFetch<OHLCData[]>(`/coins/${id}/ohlc`, {
    revalidate: 60,
    params: {
      vs_currency: "usd",
      days: safeDays,
    },
  });
}
