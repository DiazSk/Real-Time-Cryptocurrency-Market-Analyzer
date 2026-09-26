import type { Metadata } from "next";
import { Onest } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Header } from "@/components/Header";

// Onest: open, humanist-geometric shapes that stay airy at 200, the closest free
// match to the board's thin display voice. Variable 100-900 (one file serves the
// 200 price and the 400/500 body) and, unlike Albert Sans, it ships real tabular
// figures (tnum), so the rolling price never jitters.
const onest = Onest({
  variable: "--font-onest",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Crypto Market Analyzer",
  description:
    "Real-time crypto market terminal: live Coinbase trades through a Kafka and Flink pipeline, with CoinGecko market context.",
};

// Direction contract. Rendered as a real HTML comment in the served markup.
const CONTRACT = `<!--
THESIS: A market terminal whose live numbers are visibly its own: every tracked price is a Coinbase trade that crossed our Kafka and Flink pipeline seconds ago.
OWN-WORLD: A newly formed cloud edge diffracting sunlight. Cloud-white and mist ground, slate ink, colour only as a mint, rose and violet hairline on live edges.
STORY: The eye lands on one thin, very large price rolling per trade, reads where it came from in small slate type, then follows the live line into the candles. CoinGecko context waits below.
FIRST VIEWPORT: Slim bar. Wide column: coin, rolling price, arrowed change, provenance, live trade line, candlestick with 1m/5m/15m/1h. Narrow rail: 8-coin watchlist, stats, z-score alerts.
FORM: Iridescent Edge, from my ordered list, seed 156c1908
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
-->`;

// Runs before first paint: saved choice (header toggle) wins, else follow the OS,
// and keep following OS changes until the visitor picks a theme.
const THEME_SCRIPT = `(function(){try{var r=document.documentElement,m=matchMedia('(prefers-color-scheme: dark)'),s=localStorage.getItem('theme');r.dataset.theme=s==='light'||s==='dark'?s:(m.matches?'dark':'light');m.addEventListener('change',function(e){if(!localStorage.getItem('theme'))r.dataset.theme=e.matches?'dark':'light'})}catch(e){}})()`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // suppressHydrationWarning: THEME_SCRIPT sets data-theme before React hydrates.
    <html lang="en" className={`${onest.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <div hidden dangerouslySetInnerHTML={{ __html: CONTRACT }} />
        <Providers>
          <Header />
          {children}
        </Providers>
      </body>
    </html>
  );
}
