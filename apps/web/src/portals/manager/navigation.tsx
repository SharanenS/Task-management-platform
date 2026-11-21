"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export function ManagerNavigation() {
  const path = usePathname();
  return (
    <nav aria-label="Manager workspace">
      {[
        { href: "/manager", label: "Overview" },
        { href: "/manager/projects", label: "Projects" },
      ].map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={
            (
              item.href === "/manager"
                ? path === item.href
                : path.startsWith(item.href)
            )
              ? "page"
              : undefined
          }
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
