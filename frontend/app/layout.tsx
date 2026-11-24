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
        <Providers>
          <Header />
          {children}
        </Providers>
      </body>
    </html>
  );
}
