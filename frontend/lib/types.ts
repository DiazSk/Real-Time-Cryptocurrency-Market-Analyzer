import { z } from "zod";

// Mirrors src/api/endpoints/latest.py LatestPriceResponse + the /all wrapper.
export const candleSchema = z.object({
  symbol: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  open: z.coerce.number(),
  high: z.coerce.number(),
  low: z.coerce.number(),
  close: z.coerce.number(),
  volume_sum: z.coerce.number(),
  event_count: z.number(),
});
export type Candle = z.infer<typeof candleSchema>;

export const latestAllSchema = z.object({
  timestamp: z.string(),
  prices: z.record(z.string(), candleSchema),
  cache_hit_rate: z.string(),
});
export type LatestAll = z.infer<typeof latestAllSchema>;

export const historicalCandleSchema = z.object({
  symbol: z.string(),
  window_start: z.string(),
  window_end: z.string(),
  open_price: z.coerce.number(),
  high_price: z.coerce.number(),
  low_price: z.coerce.number(),
  close_price: z.coerce.number(),
  avg_price: z.coerce.number(),
  volume_sum: z.coerce.number().nullable(),
  trade_count: z.number().nullable(),
});
export type HistoricalCandle = z.infer<typeof historicalCandleSchema>;

export const statsSchema = z.object({
  symbol: z.string(),
  start_time: z.string(),
  end_time: z.string(),
  lowest_price: z.number(),
  highest_price: z.number(),
  average_price: z.number(),
  total_volume: z.number(),
  candle_count: z.number(),
  price_range: z.number(),
  price_change_pct: z.number(),
});
export type Stats = z.infer<typeof statsSchema>;

export const alertSchema = z.object({
  symbol: z.string(),
  alert_type: z.enum(["PRICE_SPIKE", "PRICE_DROP"]),
  price_change_pct: z.number(),
  old_price: z.number(),
  new_price: z.number(),
  window_start: z.string().nullable(),
  window_end: z.string().nullable(),
  created_at: z.string().nullable(),
});
export type Alert = z.infer<typeof alertSchema>;

export const alertsResponseSchema = z.object({
  symbol: z.string(),
  alert_count: z.number(),
  lookback_hours: z.number(),
  alerts: z.array(alertSchema),
});

export const symbolMetaSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  slug: z.string(),
});
export type SymbolMeta = z.infer<typeof symbolMetaSchema>;

export const symbolsResponseSchema = z.object({
  symbols: z.array(symbolMetaSchema),
  count: z.number(),
});

export const trendingItemSchema = z.object({
  symbol: z.string(),
  name: z.string(),
  price: z.number(),
  volume_24h: z.number().nullable(),
  market_cap: z.number().nullable(),
  price_change_24h: z.number(),
  timestamp: z.string(),
});
export type TrendingItem = z.infer<typeof trendingItemSchema>;

export const trendingResponseSchema = z.object({
  direction: z.string(),
  count: z.number(),
  trending: z.array(trendingItemSchema),
});

// Discriminated union mirroring the WS protocol comment block in websocket.py.
export const wsMessageSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("connection"),
    message: z.string(),
    symbol: z.string(),
    timestamp: z.string(),
    mode: z.string().optional(),
  }),
  z.object({
    type: z.literal("initial_data"),
    symbol: z.string(),
    data: z.any(),
    timestamp: z.string(),
  }),
  z.object({
    type: z.literal("price_update"),
    symbol: z.string(),
    data: z.any(),
    timestamp: z.string(),
  }),
  z.object({
    type: z.literal("keepalive"),
    timestamp: z.string(),
    connections: z.number().optional(),
  }),
  z.object({
    type: z.literal("pong"),
    timestamp: z.string(),
  }),
]);
export type WsMessage = z.infer<typeof wsMessageSchema>;
