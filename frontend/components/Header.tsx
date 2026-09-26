"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Live", match: (p: string) => p === "/" },
  { href: "/coins", label: "Markets", match: (p: string) => p.startsWith("/coins") },
];

/**
 * Slim top bar. Sticky with a misted-glass backdrop because content really does
 * scroll underneath it; the active link carries the fringe as its underline.
 */
export function Header() {
  const pathname = usePathname() ?? "/";

  return (
    <header className="sticky top-0 z-30 border-b bg-[var(--glass)] backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-6 px-4 sm:px-8">
        <Link
          href="/"
          className="text-[15px] font-normal tracking-[-0.01em] text-foreground"
        >
          Crypto Market Analyzer
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-1 sm:gap-4">
          {NAV.map(({ href, label, match }) => {
            const active = match(pathname);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-14 items-center px-2 text-sm transition-colors",
                  active
                    ? "fringe-bottom text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

export default Header;
