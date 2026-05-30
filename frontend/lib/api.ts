import {
  alertsResponseSchema,
  candleSchema,
  historicalCandleSchema,
  latestAllSchema,
  statsSchema,
  symbolsResponseSchema,
  trendingResponseSchema,
  type Candle,
  type HistoricalCandle,
  type LatestAll,
  type Stats,
  type SymbolMeta,
  type TrendingItem,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, schema: { parse: (v: unknown) => T }): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return schema.parse(await res.json());
}

export const api = {
  latestAll: () => fetchJson<LatestAll>("/api/v1/latest/all", latestAllSchema),

  latest: (symbol: string) =>
    fetchJson<Candle>(`/api/v1/latest/${symbol}`, candleSchema),

  historical: (
    symbol: string,
    opts: { limit?: number; order_by?: "asc" | "desc" } = {},
  ) => {
    const q = new URLSearchParams();
    if (opts.limit) q.set("limit", String(opts.limit));
    if (opts.order_by) q.set("order_by", opts.order_by);
    const qs = q.toString();
    return fetch(`${API_BASE}/api/v1/historical/${symbol}${qs ? `?${qs}` : ""}`, {
      cache: "no-store",
    }).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status} historical/${symbol}`);
      const raw = (await res.json()) as unknown[];
      return raw.map((r) => historicalCandleSchema.parse(r)) as HistoricalCandle[];
    });
  },

  stats: (symbol: string) =>
    fetchJson<Stats>(`/api/v1/historical/${symbol}/stats`, statsSchema),

  alerts: (symbol: string, opts: { limit?: number; hours?: number } = {}) => {
    const q = new URLSearchParams();
    if (opts.limit) q.set("limit", String(opts.limit));
    if (opts.hours) q.set("hours", String(opts.hours));
    const qs = q.toString();
    return fetchJson(
      `/api/v1/alerts/${symbol}${qs ? `?${qs}` : ""}`,
      alertsResponseSchema,
    );
  },

  symbols: async (): Promise<SymbolMeta[]> => {
    const res = await fetchJson(`/api/v1/symbols`, symbolsResponseSchema);
    return res.symbols;
  },

  trending: async (
    opts: { limit?: number; direction?: "abs" | "gainers" | "losers" } = {},
  ): Promise<TrendingItem[]> => {
    const q = new URLSearchParams();
    if (opts.limit) q.set("limit", String(opts.limit));
    if (opts.direction) q.set("direction", opts.direction);
    const qs = q.toString();
    const res = await fetchJson(
      `/api/v1/trending${qs ? `?${qs}` : ""}`,
      trendingResponseSchema,
    );
    return res.trending;
  },
};
