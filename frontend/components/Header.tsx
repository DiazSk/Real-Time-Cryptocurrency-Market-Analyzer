"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

/**
 * Top navigation bar. Adopts coinpulse's visual chrome (logo + nav links).
 * Search modal is intentionally a placeholder for now — wiring it to our
 * `/api/v1/symbols` and `/api/v1/trending` endpoints is a follow-up.
 */
export function Header() {
  const pathname = usePathname();

  return (
    <header>
      <div className="main-container inner">
        <Link href="/" className="flex items-center gap-3">
          <Image
            src="/logo.svg"
            alt="Crypto Market Analyzer"
            width={132}
            height={40}
            priority
          />
        </Link>

        <nav>
          <Link
            href="/"
            className={cn("nav-link", {
              "is-active": pathname === "/",
              "is-home": true,
            })}
          >
            Home
          </Link>

          <Link
            href="/coins"
            className={cn("nav-link", {
              "is-active": pathname === "/coins" || pathname?.startsWith("/coins/"),
            })}
          >
            All Coins
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default Header;
