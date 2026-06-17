"use client";

import { useEffect, useState } from "react";

export default function CoinDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retryMatch = error.message.match(/Retry after (\d+)s/);
  const isRateLimit = retryMatch !== null;
  const initialSeconds = retryMatch ? parseInt(retryMatch[1], 10) : 0;

  const [secondsLeft, setSecondsLeft] = useState(initialSeconds);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          clearInterval(id);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <main className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="rounded-xl border border-purple-600/20 bg-dark-500 p-10 max-w-md w-full flex flex-col items-center gap-4">
        {isRateLimit ? (
          <>
            <span className="text-4xl">⏱</span>
            <h2 className="text-xl font-semibold text-white">Rate limit reached</h2>
            <p className="text-sm text-purple-100">
              CoinGecko&apos;s free-tier limit was hit. The page will be ready
              to retry shortly.
            </p>
            {secondsLeft > 0 ? (
              <p className="text-2xl font-bold text-green-400 tabular-nums">
                {secondsLeft}s
              </p>
            ) : null}
            <button
              onClick={reset}
              disabled={secondsLeft > 0}
              className="mt-2 rounded-lg bg-green-500 px-5 py-2 text-sm font-medium text-gray-900 hover:bg-green-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {secondsLeft > 0 ? `Try again in ${secondsLeft}s` : "Try again"}
            </button>
          </>
        ) : (
          <>
            <span className="text-4xl">⚠️</span>
            <h2 className="text-xl font-semibold text-white">Failed to load coin</h2>
            <p className="text-sm text-purple-100">
              Something went wrong fetching coin data. Please try again.
            </p>
            <button
              onClick={reset}
              className="mt-2 rounded-lg bg-green-500 px-5 py-2 text-sm font-medium text-gray-900 hover:bg-green-400 transition-colors"
            >
              Try again
            </button>
          </>
        )}
      </div>
    </main>
  );
}
