import * as React from "react";
import { cn } from "@/lib/utils";

export interface PortalHeadingProps extends React.HTMLAttributes<HTMLHeadingElement> {
  level?: 1 | 2 | 3 | 4 | 5;
  variant?: "light" | "dark";
}

export function PortalHeading({
  level = 2,
  variant = "light",
  className,
  children,
  ...props
}: PortalHeadingProps) {
  const Component = `h${level}` as unknown as React.ElementType;

  const sizeClasses = {
    1: "text-2xl sm:text-3xl font-semibold tracking-tight",
    2: "text-xl sm:text-2xl font-semibold tracking-tight",
    3: "text-lg font-medium tracking-tight",
    4: "text-base font-medium tracking-normal",
    5: "text-sm font-medium tracking-normal",
  }[level];

  return (
    <Component
      data-slot="portal-heading"
      className={cn(
        sizeClasses,
        variant === "light" ? "text-[#0f1d2e]" : "text-[#f0f6fc]",
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function PortalEyebrow({
  className,
  variant = "light",
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & {
  variant?: "light" | "dark";
}) {
  return (
    <p
      data-slot="portal-eyebrow"
      className={cn(
        "text-[11px] font-semibold uppercase tracking-[0.18em]",
        variant === "light" ? "text-[#52677d]" : "text-[#00b4d8]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalText({
  className,
  variant = "light",
  tone = "primary",
  size = "default",
  ...props
}: React.HTMLAttributes<HTMLParagraphElement> & {
  variant?: "light" | "dark";
  tone?: "primary" | "secondary" | "muted";
  size?: "default" | "sm" | "xs";
}) {
  const colorClass =
    variant === "light"
      ? {
          primary: "text-[#0f1d2e]",
          secondary: "text-[#52677d]",
          muted: "text-[#7e94a8]",
        }[tone]
      : {
          primary: "text-[#f0f6fc]",
          secondary: "text-[#8fa8c6]",
          muted: "text-[#627d98]",
        }[tone];

  const sizeClass = {
    default: "text-sm leading-relaxed",
    sm: "text-xs leading-normal",
    xs: "text-[11px] leading-normal",
  }[size];

  return (
    <p
      data-slot="portal-text"
      className={cn(sizeClass, colorClass, className)}
      {...props}
    />
  );
}
