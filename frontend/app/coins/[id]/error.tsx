"use client";

import { useEffect, useState } from "react";
import { CircleAlert, RotateCw, Timer } from "lucide-react";

/** Coin page failure. CoinGecko's free tier rate limit gets a countdown. */
export default function CoinDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retryMatch = error.message.match(/Retry after (\d+)s/);
  const isRateLimit = retryMatch !== null;
  const [secondsLeft, setSecondsLeft] = useState(retryMatch ? parseInt(retryMatch[1], 10) : 0);

  useEffect(() => {
    const id = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, []);

  const Icon = isRateLimit ? Timer : CircleAlert;
  const waiting = isRateLimit && secondsLeft > 0;

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="surface fringe-top w-full max-w-md p-8 text-center">
        <Icon className="mx-auto text-muted-foreground" size={28} strokeWidth={1.5} aria-hidden />
        <h1 className="mt-4 text-2xl font-light tracking-[-0.015em]">
          {isRateLimit ? "CoinGecko rate limit reached" : "This coin didn't load"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {isRateLimit
            ? "Coin details come from CoinGecko's free tier, which just asked us to slow down. Our own live data is unaffected."
            : "Fetching coin details from CoinGecko failed. It's usually temporary."}
        </p>
        <button type="button" onClick={reset} disabled={waiting} className="pill mt-6">
          <RotateCw size={14} strokeWidth={1.75} aria-hidden />
          {waiting ? <span className="num">Try again in {secondsLeft} s</span> : "Try again"}
        </button>
      </div>
    </main>
  );
}
