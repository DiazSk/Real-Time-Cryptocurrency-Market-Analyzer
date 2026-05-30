"use server";

/**
 * Server Actions exposing the server-only CoinGecko proxy to Client Components.
 * lib/coingecko.ts has `import "server-only"` which blocks client imports — this
 * file is the seam that lets the in-browser Candlestick chart trigger a
 * CoinGecko refetch (e.g. when switching period from 1D → 1Y).
 */

import { getCoinOHLC as _getCoinOHLC } from "./coingecko";

export async function fetchCoinOHLC(
  id: string,
  days: number | "max",
): Promise<OHLCData[]> {
  return _getCoinOHLC(id, days);
}
