export function fmtPrice(n: number, max = 8): string {
  if (!Number.isFinite(n)) return "—";
  const digits = n >= 1000 ? 2 : n >= 1 ? 4 : Math.min(max, 6);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtUsd(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return `$${fmtPrice(n)}`;
}

export function fmtVolume(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}

// Like fmtVolume but also handles trillions — market caps for BTC/ETH and the
// global cap are routinely in the T range and would otherwise read "$2347.12B".
export function fmtCap(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  return fmtVolume(n);
}

// Compact whole-number formatter for counts (active coins, markets).
export function fmtCount(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  return n.toLocaleString();
}

export function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}


export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

/** "just now" / "3 min ago" / "2 hours ago"; dates older than 4 weeks as YYYY-MM-DD. */
export function timeAgo(date: string | number | Date): string {
  const past = new Date(date);
  const seconds = Math.floor((Date.now() - past.getTime()) / 1000);
  if (!Number.isFinite(seconds)) return "—";
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 28) return `${days} d ago`;
  return past.toISOString().split("T")[0];
}

/** Compact age for the live provenance line: "2 s", "4 min". */
export function fmtAge(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 60) return `${Math.floor(seconds)} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  return `${Math.floor(seconds / 3600)} h`;
}
