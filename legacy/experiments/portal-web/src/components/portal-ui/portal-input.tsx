import * as React from "react";
import { cn } from "@/lib/utils";

export interface PortalInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  supportingText?: string;
  error?: string;
  variant?: "light" | "dark";
  containerClassName?: string;
}

export const PortalInput = React.forwardRef<HTMLInputElement, PortalInputProps>(
  (
    {
      className,
      type = "text",
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
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId();
    const inputId = customId || generatedId;
    const errorId = `${inputId}-error`;
    const hintId = `${inputId}-hint`;

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
        data-slot="portal-input-container"
        className={cn("flex flex-col gap-1.5 w-full", containerClassName)}
      >
        {label && (
          <label
            htmlFor={inputId}
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
        <input
          data-slot="portal-input"
          ref={ref}
          id={inputId}
          type={type}
          disabled={disabled}
          required={required}
          aria-invalid={error ? "true" : externalInvalid}
          aria-describedby={describedBy}
          className={cn(
            "h-9 w-full rounded-lg px-3 py-1.5 text-sm transition-all outline-none",
            "focus-visible:ring-2 focus-visible:ring-[#00b4d8] focus-visible:ring-offset-1",
            "disabled:cursor-not-allowed disabled:opacity-50",
            variant === "light"
              ? "border border-[#d6e2ed] bg-white text-[#0f1d2e] placeholder:text-[#52677d] hover:border-[#b8cedf]"
              : "border border-[#1e3a5a] bg-[#091929] text-[#f0f6fc] placeholder:text-[#8fa8c6] hover:border-[#2d5580]",
            error && "border-rose-500 focus-visible:ring-rose-500",
            className,
          )}
          {...props}
        />
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
PortalInput.displayName = "PortalInput";
