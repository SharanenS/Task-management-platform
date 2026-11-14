import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PortalSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  supportingText?: string;
  error?: string;
  variant?: "light" | "dark";
  containerClassName?: string;
}

export const PortalSelect = React.forwardRef<
  HTMLSelectElement,
  PortalSelectProps
>(
  (
    {
      className,
      label,
      supportingText,
      error,
      variant = "light",
      containerClassName,
      id: customId,
      required,
      "aria-describedby": externalDescription,
      "aria-invalid": externalInvalid,
      disabled,
      children,
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId();
    const selectId = customId || generatedId;
    const errorId = `${selectId}-error`;
    const hintId = `${selectId}-hint`;

    const describedBy =
      [
        externalDescription,
        error ? errorId : null,
        !error && supportingText ? hintId : null,
      ]
        .filter(Boolean)
        .join(" ") || undefined;

    return (
      <div
        data-slot="portal-select-container"
        className={cn("flex flex-col gap-1.5 w-full", containerClassName)}
      >
        {label && (
          <label
            htmlFor={selectId}
            className={cn(
              "text-xs font-medium tracking-tight",
              variant === "light" ? "text-[#0f1d2e]" : "text-[#f0f6fc]",
            )}
          >
            {label}
            {required && (
              <span className="text-rose-500 ml-1" aria-hidden="true">
                *
              </span>
            )}
          </label>
        )}
        <div className="relative flex items-center">
          <select
            data-slot="portal-select"
            ref={ref}
            id={selectId}
            disabled={disabled}
            required={required}
            aria-invalid={error ? "true" : externalInvalid}
            aria-describedby={describedBy}
            className={cn(
              "h-9 w-full appearance-none rounded-lg pl-3 pr-8 py-1.5 text-sm transition-all outline-none cursor-pointer",
              "focus-visible:ring-2 focus-visible:ring-[#00b4d8] focus-visible:ring-offset-1",
              "disabled:cursor-not-allowed disabled:opacity-50",
              variant === "light"
                ? "border border-[#d6e2ed] bg-white text-[#0f1d2e] hover:border-[#b8cedf]"
                : "border border-[#1e3a5a] bg-[#091929] text-[#f0f6fc] hover:border-[#2d5580]",
              error && "border-rose-500 focus-visible:ring-rose-500",
              className,
            )}
            {...props}
          >
            {children}
          </select>
          <ChevronDown
            className={cn(
              "pointer-events-none absolute right-2.5 size-4 shrink-0",
              variant === "light" ? "text-[#52677d]" : "text-[#8fa8c6]",
            )}
            aria-hidden="true"
          />
        </div>
        {error && (
          <p
            id={errorId}
            role="alert"
            className={cn(
              "text-xs font-medium",
              variant === "light" ? "text-rose-700" : "text-rose-300",
            )}
          >
            {error}
          </p>
        )}
        {!error && supportingText && (
          <p
            id={hintId}
            className={cn(
              "text-xs leading-normal",
              variant === "light" ? "text-[#52677d]" : "text-[#8fa8c6]",
            )}
          >
            {supportingText}
          </p>
        )}
      </div>
    );
  },
);
PortalSelect.displayName = "PortalSelect";
