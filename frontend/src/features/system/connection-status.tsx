"use client";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useSystemInfo } from "./use-system-info";
export function ConnectionStatus() {
  const query = useSystemInfo();
  const connected =
    !query.isError && query.data?.systemInfo.status === "AVAILABLE";
  return (
    <Link
      href="/system"
      className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
      aria-label="View gateway connection status"
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          query.isPending
            ? "animate-pulse bg-amber-500"
            : connected
              ? "bg-emerald-600"
              : "bg-amber-600",
        )}
      />
      <span role="status">
        {query.isPending
          ? "Connecting…"
          : connected
            ? "Gateway connected"
            : "Gateway unavailable"}
      </span>
    </Link>
  );
}
