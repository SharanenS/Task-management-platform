"use client";

import { useState, useSyncExternalStore } from "react";
import { ChevronDown, LogOut, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import type { EmployeeProfile } from "@/auth/types";

export function UserMenu({ user }: { user: EmployeeProfile }) {
  const hydrated = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const router = useRouter();

  async function signOut() {
    setSigningOut(true);
    try {
      const session = await fetch("/auth/session", { cache: "no-store" });
      const data = (await session.json()) as { csrfToken?: string };
      const response = await fetch("/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": data.csrfToken ?? "" },
      });
      const result = (await response.json()) as { logoutUrl?: string };
      if (!result.logoutUrl) {
        router.push("/sign-in?error=logged_out");
        return;
      }
      window.location.assign(result.logoutUrl);
    } catch {
      router.push("/sign-in?error=logged_out");
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        disabled={!hydrated}
        onClick={() => setOpen((value) => !value)}
        aria-label={`${user.displayName} ${user.role}`}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg border bg-background px-2.5 py-1.5 text-left hover:bg-muted"
      >
        <span className="flex size-7 items-center justify-center rounded-md bg-primary/10 text-primary">
          <UserRound className="size-4" />
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-36 truncate text-xs font-semibold">
            {user.displayName}
          </span>
          <span className="block text-[10px] text-muted-foreground">
            {user.role}
          </span>
        </span>
        <ChevronDown className="size-3 text-muted-foreground" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute top-full right-0 z-40 mt-2 w-64 rounded-xl border bg-card p-3 shadow-lg"
        >
          <p className="truncate text-sm font-semibold">{user.displayName}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {user.email}
          </p>
          <span className="mt-3 inline-flex rounded bg-muted px-2 py-1 text-[10px] font-semibold tracking-wide">
            {user.role}
          </span>
          <button
            type="button"
            role="menuitem"
            disabled={signingOut}
            onClick={signOut}
            className="mt-3 flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold hover:bg-muted disabled:opacity-60"
          >
            <LogOut className="size-3.5" />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
