"use client";

import NumberFlow from "@number-flow/react";
import { Change } from "@/components/ui/change";
import { fmtAge } from "@/lib/format";
import type { WsStatus } from "@/lib/ws";

function digitsFor(n: number) {
  return n >= 1000 ? 2 : n >= 1 ? 4 : 6;
}

/**
 * Coin name, a very large thin price that rolls per trade, the change with an
 * arrow, and a quiet provenance line. `aside` sits beside the name (e.g. a link).
 */
export function PriceHero({
  name,
  symbol,
  price,
  change,
  changeLabel,
  provenance,
  aside,
}: {
  name: string;
  symbol?: string;
  price: number | undefined;
  change: number | null;
  changeLabel: string;
  provenance: React.ReactNode;
  aside?: React.ReactNode;
}) {
  const d = price === undefined ? 2 : digitsFor(price);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-light tracking-[-0.015em] text-foreground sm:text-[28px]">
          {name}
          {symbol && <span className="num ml-2 text-base text-muted-foreground">{symbol}</span>}
        </h1>
        {aside}
      </div>

      <div className="mt-2 flex flex-wrap items-end gap-x-5 gap-y-2">
        <p
          className="display num text-[clamp(2.75rem,8vw,5.5rem)] text-foreground"
          aria-live="off"
        >
          {price === undefined ? (
            <span className="skeleton inline-block h-[0.9em] w-[5.5em] align-bottom" aria-label="Loading price" />
          ) : (
            <NumberFlow
              value={price}
              format={{
                style: "currency",
                currency: "USD",
                minimumFractionDigits: d,
                maximumFractionDigits: d,
              }}
              willChange
            />
          )}
        </p>
        <p className="mb-2 flex items-center gap-2 text-base sm:mb-3">
          <Change value={change} iconSize={16}>
            {change === null ? "—" : `${Math.abs(change).toFixed(2)}%`}
          </Change>
          <span className="text-sm text-muted-foreground">{changeLabel}</span>
        </p>
      </div>

      <p className="caption mt-2 flex items-center gap-2">{provenance}</p>
    </div>
  );
}

/** "Live · Coinbase trades through our pipeline · updated 2 s ago", or the honest reason it isn't. */
export function LiveProvenance({
  status,
  symbol,
  lastTradeAt,
  now,
}: {
  status: WsStatus;
  symbol: string;
  lastTradeAt: number | undefined;
  now: number;
}) {
  const age = lastTradeAt === undefined ? undefined : Math.max(0, now - lastTradeAt);
  const open = status === "open";
  const fresh = open && age !== undefined && age < 15;

  let text: string;
  if (open && age === undefined) text = `Connected · waiting for the first ${symbol} trade`;
  else if (open && fresh) text = `Live · Coinbase trades through our pipeline · updated ${fmtAge(age!)} ago`;
  else if (open) text = `Live stream open · no ${symbol} trades for ${fmtAge(age!)}`;
  else if (status === "connecting") text = "Connecting to our live stream…";
  else
    text =
      age === undefined
        ? "Live stream disconnected · reconnecting"
        : `Live stream disconnected · reconnecting · last trade ${fmtAge(age)} ago`;

  return (
    <>
      <span className="live-dot" data-state={fresh ? "live" : "idle"} aria-hidden />
      <span>{text}</span>
    </>
  );
}
