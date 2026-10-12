import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";
export function Badge({
  className,
  tone = "neutral",
  ...props
}: ComponentProps<"span"> & { tone?: "neutral" | "success" | "warning" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium leading-none",
        {
          "bg-muted text-muted-foreground": tone === "neutral",
          "bg-emerald-50 text-emerald-800": tone === "success",
          "bg-amber-50 text-amber-800": tone === "warning",
        },
        className,
      )}
      {...props}
    />
  );
}
