"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { useEffect, useState } from "react";
import { UnreadNotificationCountDocument } from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

export function UnreadNotificationLink() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const value = await requestGraphQL(UnreadNotificationCountDocument);
        if (active) setCount(value.unreadNotificationCount);
      } catch {
        if (active) setCount(0);
      }
    };
    void load();
    const timer = window.setInterval(() => void load(), 30_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  return (
    <Link
      href="/notifications"
      aria-label={count ? `${count} unread notifications` : "Notifications"}
      className="relative rounded-md p-2 hover:bg-muted"
    >
      <Bell className="size-4" />
      {count > 0 && (
        <span className="absolute -top-1 -right-1 min-w-4 rounded-full bg-primary px-1 text-center text-[10px] text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
