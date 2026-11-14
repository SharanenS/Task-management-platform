import * as React from "react";
import { cn } from "@/lib/utils";

export type PortalBadgeStatus =
  | "pending"
  | "in_progress"
  | "review"
  | "completed"
  | "blocked"
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger";

export interface PortalBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status?: PortalBadgeStatus;
  variant?: "light" | "dark";
  showDot?: boolean;
}

const statusConfig: Record<
  PortalBadgeStatus,
  {
    label: string;
    lightClass: string;
    darkClass: string;
    dotColor: string;
  }
> = {
  pending: {
    label: "Pending",
    lightClass: "bg-slate-100 text-slate-700 border-slate-200",
    darkClass: "bg-slate-800/80 text-slate-300 border-slate-700",
    dotColor: "bg-slate-400",
  },
  in_progress: {
    label: "In progress",
    lightClass: "bg-cyan-50 text-cyan-800 border-cyan-200",
    darkClass: "bg-cyan-950/70 text-cyan-300 border-cyan-800",
    dotColor: "bg-cyan-500",
  },
  review: {
    label: "Review",
    lightClass: "bg-amber-50 text-amber-800 border-amber-200",
    darkClass: "bg-amber-950/70 text-amber-300 border-amber-800",
    dotColor: "bg-amber-500",
  },
  completed: {
    label: "Completed",
    lightClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
    darkClass: "bg-emerald-950/70 text-emerald-300 border-emerald-800",
    dotColor: "bg-emerald-500",
  },
  blocked: {
    label: "Blocked",
    lightClass: "bg-rose-50 text-rose-800 border-rose-200",
    darkClass: "bg-rose-950/70 text-rose-300 border-rose-800",
    dotColor: "bg-rose-500",
  },
  neutral: {
    label: "Neutral",
    lightClass: "bg-slate-100 text-slate-700 border-slate-200",
    darkClass: "bg-slate-800/80 text-slate-300 border-slate-700",
    dotColor: "bg-slate-400",
  },
  info: {
    label: "Info",
    lightClass: "bg-sky-50 text-sky-800 border-sky-200",
    darkClass: "bg-sky-950/70 text-sky-300 border-sky-800",
    dotColor: "bg-sky-500",
  },
  success: {
    label: "Success",
    lightClass: "bg-emerald-50 text-emerald-800 border-emerald-200",
    darkClass: "bg-emerald-950/70 text-emerald-300 border-emerald-800",
    dotColor: "bg-emerald-500",
  },
  warning: {
    label: "Warning",
    lightClass: "bg-amber-50 text-amber-800 border-amber-200",
    darkClass: "bg-amber-950/70 text-amber-300 border-amber-800",
    dotColor: "bg-amber-500",
  },
  danger: {
    label: "Danger",
    lightClass: "bg-rose-50 text-rose-800 border-rose-200",
    darkClass: "bg-rose-950/70 text-rose-300 border-rose-800",
    dotColor: "bg-rose-500",
  },
};

export function PortalBadge({
  className,
  status = "neutral",
  variant = "light",
  showDot = true,
  children,
  ...props
}: PortalBadgeProps) {
  const config = statusConfig[status] ?? statusConfig.neutral;
  const content = children ?? config.label;

  return (
    <span
      role="status"
      data-slot="portal-badge"
      data-status={status}
      data-variant={variant}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium leading-normal tracking-tight transition-colors",
        variant === "light" ? config.lightClass : config.darkClass,
        className,
      )}
      {...props}
    >
      {showDot && (
        <span
          className={cn("size-1.5 shrink-0 rounded-full", config.dotColor)}
          aria-hidden="true"
        />
      )}
      <span>{content}</span>
    </span>
  );
}
