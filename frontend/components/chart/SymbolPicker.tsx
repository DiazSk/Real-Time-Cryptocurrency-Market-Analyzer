"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import clsx from "clsx";

export function SymbolPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (sym: string) => void;
}) {
  const { data: symbols } = useQuery({
    queryKey: ["symbols"],
    queryFn: api.symbols,
    staleTime: 60 * 60 * 1000,
  });

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {symbols?.map((s) => (
        <button
          key={s.symbol}
          onClick={() => onChange(s.symbol)}
          className={clsx(
            "rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
            value === s.symbol
              ? "border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/10 text-foreground"
              : "border-[color:var(--color-border)] bg-[color:var(--color-background-elev)] text-muted-foreground hover:text-foreground",
          )}
        >
          <span className="num">{s.symbol}</span>
          <span className="ml-2 text-xs text-muted-foreground">{s.name}</span>
        </button>
      ))}
    </div>
  );
}
