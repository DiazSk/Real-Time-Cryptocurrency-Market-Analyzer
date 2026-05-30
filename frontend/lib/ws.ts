"use client";

import { useEffect, useRef, useState } from "react";
import { wsMessageSchema, type WsMessage } from "./types";

export const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export type WsStatus = "connecting" | "open" | "closed" | "error";

/**
 * Backend candle shape inside WS messages (matches Flink's Redis JSON dump,
 * which uses camelCase / epoch-second timestamps — different from REST).
 */
export type WsCandle = {
  symbol: string;
  windowStart: number;
  windowEnd: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volumeSum: number;
  eventCount: number;
};

type Listener = (msg: WsMessage) => void;

interface Options {
  /** Optional callback for every parsed message. */
  onMessage?: Listener;
}

const PING_INTERVAL_MS = 25_000;
const DEAD_THRESHOLD_MS = 60_000;
const RECONNECT_INITIAL_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

/**
 * Subscribes to ws://API/ws/prices/<symbol>. Handles:
 *   - Exponential backoff reconnect (1s → 30s)
 *   - Ping every 25s; reconnect if no frame seen in 60s
 *   - Zod-validated discriminated-union messages
 *
 * Returns the latest message, the most recent candle data per symbol,
 * the connection status, and lets the caller subscribe to a stream.
 */
export function useCryptoSocket(symbol: string, opts: Options = {}) {
  const [status, setStatus] = useState<WsStatus>("connecting");
  const [latestBySymbol, setLatestBySymbol] = useState<Record<string, WsCandle>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastFrameAtRef = useRef<number>(Date.now());
  const onMessageRef = useRef(opts.onMessage);

  // Keep the latest listener without re-opening the socket on identity churn.
  useEffect(() => {
    onMessageRef.current = opts.onMessage;
  }, [opts.onMessage]);

  useEffect(() => {
    let cancelled = false;

    function clearTimers() {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      reconnectTimerRef.current = null;
      pingTimerRef.current = null;
    }

    function scheduleReconnect() {
      if (cancelled) return;
      const attempt = reconnectAttemptsRef.current++;
      const delay = Math.min(
        RECONNECT_INITIAL_MS * 2 ** attempt,
        RECONNECT_MAX_MS,
      );
      reconnectTimerRef.current = setTimeout(connect, delay);
    }

    function connect() {
      if (cancelled) return;
      clearTimers();
      setStatus("connecting");

      const url = `${WS_BASE}/ws/prices/${symbol}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      lastFrameAtRef.current = Date.now();

      ws.onopen = () => {
        if (cancelled) return;
        reconnectAttemptsRef.current = 0;
        setStatus("open");

        pingTimerRef.current = setInterval(() => {
          if (Date.now() - lastFrameAtRef.current > DEAD_THRESHOLD_MS) {
            // No frames for too long — force a reconnect.
            ws.close();
            return;
          }
          try {
            ws.send(JSON.stringify({ type: "ping" }));
          } catch {
            ws.close();
          }
        }, PING_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        lastFrameAtRef.current = Date.now();

        let parsed: WsMessage;
        try {
          parsed = wsMessageSchema.parse(JSON.parse(event.data));
        } catch {
          return; // Drop frames that don't match the protocol.
        }

        onMessageRef.current?.(parsed);

        if (parsed.type === "initial_data" || parsed.type === "price_update") {
          const candle = parsed.data as WsCandle;
          if (candle && typeof candle.close === "number") {
            setLatestBySymbol((prev) => ({ ...prev, [candle.symbol]: candle }));
          }
        }
      };

      ws.onerror = () => {
        if (cancelled) return;
        setStatus("error");
      };

      ws.onclose = () => {
        if (cancelled) return;
        setStatus("closed");
        clearTimers();
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimers();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [symbol]);

  return { status, latestBySymbol };
}
