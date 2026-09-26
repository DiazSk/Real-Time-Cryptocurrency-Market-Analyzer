import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { fmtPct } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * A price move: green/red AND an arrow icon, so direction never rides on colour
 * alone. `children` replaces the default percentage text (e.g. a USD delta).
 */
export function Change({
  value,
  className,
  iconSize = 14,
  children,
}: {
  value: number | null | undefined;
  className?: string;
  iconSize?: number;
  children?: React.ReactNode;
}) {
  const known = value !== null && value !== undefined && Number.isFinite(value);
  const dir = !known || value === 0 ? "flat" : value > 0 ? "up" : "down";
  const Icon = dir === "up" ? ArrowUpRight : dir === "down" ? ArrowDownRight : Minus;

  return (
    <span
      className={cn(
        "num inline-flex items-center gap-0.5 whitespace-nowrap",
        dir === "up" && "text-up",
        dir === "down" && "text-down",
        dir === "flat" && "text-muted-foreground",
        className,
      )}
    >
      <Icon size={iconSize} strokeWidth={1.75} aria-hidden />
      <span className="sr-only">{dir === "up" ? "up" : dir === "down" ? "down" : "unchanged"}</span>
      {children ?? fmtPct(value)}
    </span>
  );
}
