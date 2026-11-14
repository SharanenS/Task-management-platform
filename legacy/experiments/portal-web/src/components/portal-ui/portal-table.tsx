import * as React from "react";
import { cn } from "@/lib/utils";

const TableVariantContext = React.createContext<"light" | "dark">("light");

export function usePortalTableVariant() {
  return React.useContext(TableVariantContext);
}

export function PortalTableContainer({
  className,
  variant = "light",
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: "light" | "dark" }) {
  return (
    <TableVariantContext.Provider value={variant}>
      <div
        data-slot="portal-table-container"
        className={cn(
          "w-full overflow-x-auto rounded-xl border transition-colors",
          variant === "light"
            ? "border-[#d6e2ed] bg-white shadow-xs"
            : "border-[#1e3a5a] bg-[#0d233a] shadow-xs",
          className,
        )}
        {...props}
      >
        {children}
      </div>
    </TableVariantContext.Provider>
  );
}

export function PortalTable({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table
      data-slot="portal-table"
      className={cn(
        "w-full caption-bottom text-sm text-left border-collapse",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  const variant = usePortalTableVariant();
  return (
    <thead
      data-slot="portal-table-header"
      className={cn(
        "border-b text-xs font-semibold uppercase tracking-wider",
        variant === "light"
          ? "border-[#d6e2ed] bg-[#f0f6fa] text-[#52677d]"
          : "border-[#1e3a5a] bg-[#091929] text-[#8fa8c6]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableBody({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      data-slot="portal-table-body"
      className={cn(
        "divide-y divide-[#e8f0f6] dark:divide-[#142c44]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableRow({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableRowElement>) {
  const variant = usePortalTableVariant();
  return (
    <tr
      data-slot="portal-table-row"
      className={cn(
        "transition-colors",
        variant === "light"
          ? "hover:bg-[#f6fafc] data-[state=selected]:bg-[#eef4f8]"
          : "hover:bg-[#132f4c] data-[state=selected]:bg-[#18395c]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableHead({
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      data-slot="portal-table-head"
      className={cn(
        "h-10 px-4 text-left align-middle font-medium whitespace-nowrap text-xs",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableCell({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  const variant = usePortalTableVariant();
  return (
    <td
      data-slot="portal-table-cell"
      className={cn(
        "p-4 align-middle text-sm",
        variant === "light" ? "text-[#0f1d2e]" : "text-[#f0f6fc]",
        className,
      )}
      {...props}
    />
  );
}

export function PortalTableCaption({
  className,
  ...props
}: React.HTMLAttributes<HTMLTableCaptionElement>) {
  return (
    <caption
      data-slot="portal-table-caption"
      className={cn(
        "mt-3 text-xs text-[#52677d] dark:text-[#8fa8c6] px-4 pb-3",
        className,
      )}
      {...props}
    />
  );
}
