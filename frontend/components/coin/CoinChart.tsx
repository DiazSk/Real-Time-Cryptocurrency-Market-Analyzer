"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import {
  CandlestickSeries,
  createChart,
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";
import {
  getCandlestickConfig,
  getChartConfig,
  LIVE_INTERVAL_BUTTONS,
  PERIOD_BUTTONS,
  PERIOD_CONFIG,
} from "@/lib/chart-config";
import { fetchCoinOHLC } from "@/lib/coingecko-actions";
import { convertOHLCData } from "@/lib/utils";

/**
 * Period-switching candlestick chart used on /coins/[id]. Lifted from
 * coinpulse with one wiring change: the period-fetch goes through our
 * server action `fetchCoinOHLC` (which calls our server-only CoinGecko
 * proxy), instead of coinpulse's bespoke fetcher.
 *
 * Optional `liveOhlcv` (an [ts, o, h, l, c] tuple) is merged into the tail
 * of the data set on each tick — wire it up from a WS source if you want
 * live candle updates.
 */
const CoinChart = ({
  children,
  data,
  coinId,
  height = 360,
  initialPeriod = "daily",
  liveOhlcv = null,
  mode = "historical",
  liveInterval,
  setLiveInterval,
}: CoinChartProps) => {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const prevOhlcDataLength = useRef<number>(data?.length || 0);

  const [period, setPeriod] = useState<Period>(initialPeriod);
  const [ohlcData, setOhlcData] = useState<OHLCData[]>(data ?? []);
  const [isPending, startTransition] = useTransition();

  // Sync external `data` prop changes (e.g. parent switched the active
  // symbol → fetched new initial OHLC) into internal state. Local period
  // changes are not affected because the period switcher updates ohlcData
  // directly without touching the parent's `data` prop.
  useEffect(() => {
    setOhlcData(data ?? []);
    prevOhlcDataLength.current = data?.length ?? 0;
  }, [data]);

  const handlePeriodChange = async (newPeriod: Period) => {
    if (newPeriod === period) return;

    setPeriod(newPeriod);
    try {
      const { days } = PERIOD_CONFIG[newPeriod];
      const newData = await fetchCoinOHLC(coinId, days);
      startTransition(() => {
        setOhlcData(newData ?? []);
      });
    } catch (e) {
      console.error("Failed to fetch OHLC data", e);
    }
  };

  // Bootstrap chart + handle resize. Re-runs when period changes (so x-axis
  // formatting can switch between intraday-with-time and date-only modes).
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const showTime = ["daily", "weekly", "monthly"].includes(period);

    const chart = createChart(container, {
      ...getChartConfig(height, showTime),
      width: container.clientWidth,
    });
    const series = chart.addSeries(CandlestickSeries, getCandlestickConfig());

    const convertedToSeconds = ohlcData.map(
      (item) => [Math.floor(item[0] / 1000), item[1], item[2], item[3], item[4]] as OHLCData,
    );

    series.setData(convertOHLCData(convertedToSeconds));
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleSeriesRef.current = series;

    const observer = new ResizeObserver((entries) => {
      if (!entries.length) return;
      chart.applyOptions({ width: entries[0].contentRect.width });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height, period]);

  // Push data / merge live tick when either changes.
  useEffect(() => {
    if (!candleSeriesRef.current) return;

    const convertedToSeconds = ohlcData.map(
      (item) => [Math.floor(item[0] / 1000), item[1], item[2], item[3], item[4]] as OHLCData,
    );

    let merged: OHLCData[];

    if (liveOhlcv) {
      const liveTimestamp = liveOhlcv[0];
      const lastHistoricalCandle = convertedToSeconds[convertedToSeconds.length - 1];

      if (lastHistoricalCandle && lastHistoricalCandle[0] === liveTimestamp) {
        merged = [...convertedToSeconds.slice(0, -1), liveOhlcv];
      } else {
        merged = [...convertedToSeconds, liveOhlcv];
      }
    } else {
      merged = convertedToSeconds;
    }

    merged.sort((a, b) => a[0] - b[0]);

    const converted = convertOHLCData(merged);
    candleSeriesRef.current.setData(converted);

    const dataChanged = prevOhlcDataLength.current !== ohlcData.length;

    if (dataChanged || mode === "historical") {
      chartRef.current?.timeScale().fitContent();
      prevOhlcDataLength.current = ohlcData.length;
    }
  }, [ohlcData, period, liveOhlcv, mode]);

  return (
    <div id="candlestick-chart">
      <div className="chart-header">
        <div className="flex-1">{children}</div>

        <div className="button-group">
          <span className="text-sm mx-2 font-medium text-purple-100/50">Period:</span>
          {PERIOD_BUTTONS.map(({ value, label }) => (
            <button
              key={value}
              className={period === value ? "config-button-active" : "config-button"}
              onClick={() => handlePeriodChange(value)}
              disabled={isPending}
            >
              {label}
            </button>
          ))}
        </div>

        {liveInterval && setLiveInterval && (
          <div className="button-group">
            <span className="text-sm mx-2 font-medium text-purple-100/50">Update Frequency:</span>
            {LIVE_INTERVAL_BUTTONS.map(({ value, label }) => (
              <button
                key={value}
                className={liveInterval === value ? "config-button-active" : "config-button"}
                onClick={() => setLiveInterval(value)}
                disabled={isPending}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={chartContainerRef} className="chart" style={{ height }} />
    </div>
  );
};

export default CoinChart;
