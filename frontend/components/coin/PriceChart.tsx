"use client";

import { memo, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Candlestick } from "@/components/charts/candlestick";
import {
  CandlestickChart,
  type OHLCDataPoint,
} from "@/components/charts/candlestick-chart";
import { Grid } from "@/components/charts/grid";
import { ChartTooltip } from "@/components/charts/tooltip";
import { XAxis } from "@/components/charts/x-axis";
import { YAxis } from "@/components/charts/y-axis";
import { Change } from "@/components/ui/change";
import { api, type CandleInterval } from "@/lib/api";
import { fetchCoinOHLC } from "@/lib/coingecko-actions";
import { fmtPrice, fmtUsd, fmtVolume } from "@/lib/format";
import type { WsCandle } from "@/lib/ws";

// ── CoinGecko periods (untracked coins) ────────────────────────────────────
// Candle granularity is decided by CoinGecko from `days`.
const PERIOD_CONFIG: Record<Period, { days: number | "max"; label: string; grain: string }> = {
  daily: { days: 1, label: "1D", grain: "30-min candles" },
  weekly: { days: 7, label: "1W", grain: "4-hour candles" },
  monthly: { days: 30, label: "1M", grain: "4-hour candles" },
  "3months": { days: 90, label: "3M", grain: "4-day candles" },
  "6months": { days: 180, label: "6M", grain: "4-day candles" },
  yearly: { days: 365, label: "1Y", grain: "4-day candles" },
  max: { days: "max", label: "Max", grain: "4-day candles, last 365 days" },
};
const PERIODS = Object.keys(PERIOD_CONFIG) as Period[];

// ── Our intervals (tracked symbols) ────────────────────────────────────────
// /historical serves the last 24 h by default; these limits fill the chart.
// `limit` is how far back we fetch; the chart then shows the most recent
// contiguous run (see `recentRun`), at least MIN_SLOTS wide.
const MIN_SLOTS = 30;
const INTERVALS: { value: CandleInterval; limit: number; stepMs: number }[] = [
  { value: "1m", limit: 120, stepMs: 60_000 },
  { value: "5m", limit: 144, stepMs: 300_000 },
  { value: "15m", limit: 96, stepMs: 900_000 },
  { value: "1h", limit: 24, stepMs: 3_600_000 },
];

type Point = OHLCDataPoint & { volume?: number; trades?: number };

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const dayFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const fullFmt = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const fmtClock = (d: Date) => timeFmt.format(d);
const fmtDay = (d: Date) => dayFmt.format(d);

interface PriceChartProps {
  /** Our ticker (e.g. "BTC") when the pipeline tracks this coin, else null. */
  symbol: string | null;
  /** CoinGecko id, used when `symbol` is null. */
  coinId?: string;
  /** Server-fetched CoinGecko 1D OHLC so the untracked chart paints immediately. */
  initialOhlc?: OHLCData[];
  /** The live 1m candle from the WebSocket, merged into the tail at 1m. */
  liveCandle?: WsCandle;
  height?: number;
}

/**
 * Candlestick for one coin.
 *  - Tracked: our /historical at 1m/5m/15m/1h, refetched every 60 s, with the
 *    live WS candle merged into the tail at 1m.
 *  - Untracked: CoinGecko OHLC with the period switcher.
 */
function PriceChartImpl({ symbol, coinId, initialOhlc, liveCandle, height = 236 }: PriceChartProps) {
  const [interval, setInterval_] = useState<CandleInterval>("1m");
  const [period, setPeriod] = useState<Period>("daily");
  const tracked = symbol !== null;
  const spec = INTERVALS.find((i) => i.value === interval)!;

  const ours = useQuery({
    queryKey: ["candles", symbol, interval, "chart"],
    queryFn: () =>
      api.historical(symbol as string, {
        interval,
        limit: spec.limit,
        order_by: "desc",
        start_time: new Date(Date.now() - spec.limit * spec.stepMs).toISOString(),
      }),
    enabled: tracked,
    refetchInterval: 60_000,
  });

  const cg = useQuery({
    queryKey: ["cg-ohlc", coinId, period],
    queryFn: () => fetchCoinOHLC(coinId as string, PERIOD_CONFIG[period].days),
    enabled: !tracked && !!coinId,
    initialData: period === "daily" && initialOhlc?.length ? initialOhlc : undefined,
    staleTime: 60_000,
  });

  const points = useMemo<Point[]>(() => {
    if (tracked) {
      const rows = [...(ours.data ?? [])].reverse();
      const pts: Point[] = rows.map((r) => ({
        date: new Date(r.window_start),
        open: r.open_price,
        high: r.high_price,
        low: r.low_price,
        close: r.close_price,
        volume: r.quote_volume,
        trades: r.trade_count,
      }));
      if (interval === "1m" && liveCandle && liveCandle.symbol === symbol) {
        const t = liveCandle.windowStart * 1000;
        const live: Point = {
          date: new Date(t),
          open: liveCandle.open,
          high: liveCandle.high,
          low: liveCandle.low,
          close: liveCandle.close,
          volume: liveCandle.quoteVolume,
          trades: liveCandle.tradeCount,
        };
        const last = pts.at(-1);
        if (last && last.date.getTime() === t) pts[pts.length - 1] = live;
        else if (!last || t > last.date.getTime()) pts.push(live);
      }
      return pts;
    }
    const seen = new Set<number>();
    return (cg.data ?? [])
      .filter(([t]) => (seen.has(t) ? false : (seen.add(t), true)))
      .map(([t, o, h, l, c]) => ({ date: new Date(t), open: o, high: h, low: l, close: c }));
  }, [tracked, ours.data, cg.data, interval, liveCandle, symbol]);

  // Our candles: keep only the latest contiguous run so stale orphans (a lone
  // candle from hours ago) stay out of the x and y domains. The x axis spans
  // that run in real time, so short trade-less gaps inside it stay visible.
  const { shown, xDomain, slots, trimmed } = useMemo(() => {
    if (!tracked || points.length === 0) {
      return { shown: points, xDomain: undefined, slots: undefined, trimmed: false };
    }
    const run = recentRun(points, spec.stepMs * 5);
    const first = run[0].date.getTime();
    const last = run.at(-1)!.date.getTime();
    const n = Math.min(spec.limit, Math.max(Math.min(MIN_SLOTS, spec.limit), (last - first) / spec.stepMs + 1));
    const domain: [Date, Date] = [new Date(last - (n - 1) * spec.stepMs), new Date(last)];
    return { shown: run, xDomain: domain, slots: n, trimmed: run.length < points.length };
  }, [tracked, points, spec]);

  const q = tracked ? ours : cg;
  const intraday = tracked || period === "daily" || period === "weekly";
  const caption = tracked
    ? shown.length
      ? `${interval} candles from ${fmtClock(shown[0].date)} · our pipeline · refreshed every 60 s${trimmed ? " · older candles before a gap hidden" : ""}`
      : `${interval} candles · our pipeline · refreshed every 60 s`
    : `CoinGecko OHLC · ${PERIOD_CONFIG[period].grain}`;

  return (
    <section aria-label="Candlestick chart" className="fringe-top pt-5">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="heading">Candles</h2>
          <p className="caption mt-0.5">{caption}</p>
        </div>

        {tracked ? (
          <div className="segmented" role="group" aria-label="Candle interval">
            {INTERVALS.map(({ value }) => (
              <button
                key={value}
                type="button"
                aria-pressed={interval === value}
                onClick={() => setInterval_(value)}
              >
                {value}
              </button>
            ))}
          </div>
        ) : (
          <div className="segmented scroll-x max-w-full" role="group" aria-label="Chart period">
            {PERIODS.map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={period === p}
                onClick={() => setPeriod(p)}
              >
                {PERIOD_CONFIG[p].label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ height }} className="relative">
        {q.isLoading ? (
          <div className="skeleton h-full w-full" aria-label="Loading candles" />
        ) : q.error ? (
          <ChartNote>
            {tracked
              ? "Couldn't load candles from our API. It retries every 60 s."
              : "Couldn't load CoinGecko OHLC (the free tier may be rate limited). Try another period in a minute."}
          </ChartNote>
        ) : shown.length < (tracked ? 1 : 2) ? (
          <ChartNote>
            {tracked
              ? `No ${interval} candles for ${symbol} in the last 24 h yet. The pipeline writes one candle per minute that has trades, and rollups fill in as minutes accumulate.`
              : "CoinGecko returned no candles for this period."}
          </ChartNote>
        ) : (
          <CandlestickChart
            key={`${symbol ?? coinId}-${tracked ? interval : period}`}
            data={shown}
            xDomain={xDomain}
            xDomainSlotCount={slots}
            dateFormat={intraday ? fmtClock : fmtDay}
            aspectRatio="auto"
            style={{ height, touchAction: "pan-y" }}
            margin={{ top: 8, right: 76, bottom: 30, left: 44 }}
            animationDuration={600}
          >
            <Grid horizontal numTicksRows={4} strokeDasharray="2 4" />
            <Candlestick positiveFill="var(--up)" negativeFill="var(--down)" />
            <YAxis orientation="right" numTicks={4} formatValue={(v) => fmtPrice(v)} />
            <XAxis
              numTicks={5}
              tickMode={xDomain ? "domain" : "data"}
              formatLabel={intraday ? fmtClock : fmtDay}
            />
            <ChartTooltip
              showDatePill={false}
              showDots={false}
              content={({ point }) => <OhlcTooltip point={point as unknown as Point} tracked={tracked} />}
            />
          </CandlestickChart>
        )}
      </div>
    </section>
  );
}

/** The trailing points whose neighbours are at most `maxGapMs` apart. */
function recentRun<T extends { date: Date }>(pts: T[], maxGapMs: number): T[] {
  let i = pts.length - 1;
  while (i > 0 && pts[i].date.getTime() - pts[i - 1].date.getTime() <= maxGapMs) i--;
  return pts.slice(i);
}

function ChartNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center rounded-[var(--radius-md)] bg-mist px-6 text-center text-sm text-muted-foreground">
      <p className="max-w-md">{children}</p>
    </div>
  );
}

function OhlcTooltip({ point, tracked }: { point: Point; tracked: boolean }) {
  const pct = point.open ? ((point.close - point.open) / point.open) * 100 : 0;
  const rows: [string, string][] = [
    ["Open", fmtUsd(point.open)],
    ["High", fmtUsd(point.high)],
    ["Low", fmtUsd(point.low)],
    ["Close", fmtUsd(point.close)],
  ];
  if (tracked && point.volume !== undefined) rows.push(["Volume", fmtVolume(point.volume)]);
  if (tracked && point.trades !== undefined) rows.push(["Trades", point.trades.toLocaleString()]);

  return (
    <div className="min-w-44 px-3 py-2.5 text-xs">
      <div className="mb-1.5 flex items-center justify-between gap-4">
        <span className="text-muted-foreground">{fullFmt.format(point.date)}</span>
        <Change value={pct} iconSize={12} />
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="num text-right text-foreground">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export const PriceChart = memo(PriceChartImpl);
export default PriceChart;
