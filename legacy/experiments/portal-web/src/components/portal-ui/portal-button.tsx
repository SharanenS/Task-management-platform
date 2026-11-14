import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const portalButtonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-[#00b4d8] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 cursor-pointer",
  {
    variants: {
      variant: {
        primary:
          "bg-[#00b4d8] text-[#071626] shadow-sm hover:bg-[#0096c7] active:bg-[#0077b6] active:text-white focus-visible:ring-offset-background",
        secondary:
          "border border-[#d6e2ed] bg-white text-[#0f1d2e] shadow-xs hover:bg-[#f0f6fa] hover:border-[#b8cedf] active:bg-[#e4eff7]",
        "secondary-dark":
          "border border-[#1e3a5a] bg-[#0d233a] text-[#f0f6fc] shadow-xs hover:bg-[#132f4c] hover:border-[#2d5580] active:bg-[#18395c]",
        quiet:
          "text-[#52677d] hover:bg-[#e8f0f6] hover:text-[#0f1d2e] active:bg-[#dbe6f0]",
        "quiet-dark":
          "text-[#8fa8c6] hover:bg-[#132f4c] hover:text-[#f0f6fc] active:bg-[#18395c]",
        danger:
          "bg-[#e11d48] text-white shadow-sm hover:bg-[#be123c] active:bg-[#9f1239] focus-visible:ring-[#e11d48]",
      },
      size: {
        default: "h-9 px-4 py-2 text-sm",
        sm: "h-8 px-3 text-xs rounded-md",
        lg: "h-11 px-6 text-base rounded-xl",
        icon: "size-9 p-0",
        "icon-sm": "size-8 p-0 rounded-md",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface PortalButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof portalButtonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const PortalButton = React.forwardRef<
  HTMLButtonElement,
  PortalButtonProps
>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      disabled,
      children,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        data-slot="portal-button"
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading ? "true" : undefined}
        className={cn(portalButtonVariants({ variant, size, className }))}
        {...props}
      >
        {loading ? (
          <>
            <Loader2
              className="animate-spin size-4 shrink-0"
              aria-hidden="true"
            />
            <span>{children}</span>
          </>
        ) : (
          children
        )}
      </Comp>
    );
  },
);
PortalButton.displayName = "PortalButton";
