"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

/** Flip <html data-theme> and remember it; the icon swaps via the dark: variant, so no React state. */
function toggleTheme() {
  const root = document.documentElement;
  const next = root.dataset.theme === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch {
    // private mode: the toggle still works for this page view
  }
}

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
                    ? "fringe-bottom nav-fringe text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </Link>
            );
          })}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle dark mode"
            title="Toggle dark mode"
            className="ml-1 flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-[var(--mist)] hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--violet-edge)]"
          >
            <Moon aria-hidden className="size-4 dark:hidden" strokeWidth={1.5} />
            <Sun aria-hidden className="hidden size-4 dark:block" strokeWidth={1.5} />
          </button>
        </nav>
      </div>
    </header>
  );
}

export default Header;
