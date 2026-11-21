"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
const items = [
  { href: "/admin/projects", label: "Projects", symbol: "08" },
  { href: "/admin/calendar", label: "Working calendar", symbol: "07" },
  { href: "/admin/organization", label: "Company structure", symbol: "05" },
  { href: "/admin/employees", label: "Employees", symbol: "06" },
  { href: "/admin/accounts", label: "User accounts", symbol: "04" },
  { href: "/admin", label: "Overview", symbol: "01" },
  { href: "/admin/profile", label: "Your profile", symbol: "02" },
  { href: "/admin/security", label: "Account security", symbol: "03" },
];
export function AdminNavigation() {
  const path = usePathname();
  return (
    <nav aria-label="Administration">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={path === item.href ? "page" : undefined}
        >
          <span aria-hidden="true">{item.symbol}</span>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
