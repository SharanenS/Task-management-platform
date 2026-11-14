import * as React from "react";
import { cn } from "@/lib/utils";

export interface PortalCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "light" | "dark";
}

const CardVariantContext = React.createContext<"light" | "dark">("light");

export function usePortalCardVariant() {
  return React.useContext(CardVariantContext);
}

export function PortalCard({
  className,
  variant = "light",
  ...props
}: PortalCardProps) {
  return (
    <CardVariantContext.Provider value={variant}>
      <div
        data-slot="portal-card"
        data-variant={variant}
        className={cn(
          "min-w-0 rounded-2xl transition-shadow",
          variant === "light"
            ? "border border-[#d6e2ed] bg-white text-[#0f1d2e] shadow-[0_2px_8px_-2px_rgba(13,35,58,0.06)]"
            : "border border-[#1e3a5a] bg-[#0d233a] text-[#f0f6fc] shadow-[0_4px_16px_-4px_rgba(7,22,38,0.35)]",
          className,
        )}
        {...props}
      />
    </CardVariantContext.Provider>
  );
}

export function PortalCardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="portal-card-header"
      className={cn("flex flex-col gap-1.5 p-5 pb-3", className)}
      {...props}
    />
  );
}

export function PortalCardTitle({
  className,
  as: Component = "h3",
  ...props
}: React.HTMLAttributes<HTMLHeadingElement> & {
  as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
}) {
  const variant = usePortalCardVariant();
  return (
    <Component
      data-slot="portal-card-title"
      className={cn(
        "text-base font-semibold tracking-tight leading-snug",
        variant === "light" ? "text-[#0f1d2e]" : "text-[#f0f6fc]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalCardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  const variant = usePortalCardVariant();
  return (
    <p
      data-slot="portal-card-description"
      className={cn(
        "text-xs leading-relaxed",
        variant === "light" ? "text-[#52677d]" : "text-[#8fa8c6]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalCardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="portal-card-content"
      className={cn("p-5 pt-0", className)}
      {...props}
    />
  );
}

export function PortalCardFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="portal-card-footer"
      className={cn("flex items-center gap-3 p-5 pt-0", className)}
      {...props}
    />
  );
}
