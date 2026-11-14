"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Blocks,
  LayoutDashboard,
  FolderKanban,
  Users,
  Bell,
  FileChartColumn,
  Workflow,
  Activity,
  Menu,
  X,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";
import type { EmployeeProfile } from "@/auth/types";
import { UserMenu } from "@/components/layout/user-menu";
import { ConnectionStatus } from "@/features/system/connection-status";
import { UnreadNotificationLink } from "@/features/notifications/unread-notification-link";
import { portalForRole, portalHome } from "@/features/portals/portal-policy";
import { cn } from "@/lib/utils";
import { PortalPathContext } from "@/components/portal-ui/portal-link";

export function PortalShell({
  user,
  children,
}: {
  user: EmployeeProfile;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const home = portalHome(user.role);
  const name = portalForRole(user.role);
  const navigation = [
    { label: "Overview", path: "", icon: LayoutDashboard },
    {
      label: user.role === "MANAGER" ? "Project delivery" : "Projects",
      path: "/projects",
      icon: FolderKanban,
    },
    ...(user.role === "ADMIN"
      ? [{ label: "People & accounts", path: "/employees", icon: Users }]
      : []),
    ...(user.role !== "MEMBER"
      ? [{ label: "Automations", path: "/workflows", icon: Workflow }]
      : []),
    { label: "Reports", path: "/reports", icon: FileChartColumn },
    { label: "Notifications", path: "/notifications", icon: Bell },
    ...(user.role === "ADMIN"
      ? [
          { label: "Operations", path: "/operations", icon: ShieldCheck },
          { label: "System health", path: "/system", icon: Activity },
        ]
      : []),
  ];
  const active = navigation.findLast((item) =>
    item.path ? pathname.startsWith(home + item.path) : pathname === home,
  );
  const sidebar = (close?: () => void) => (
    <div className="flex min-h-full flex-col bg-[#091929] px-5 py-7 text-[#8fa8c6]">
      <Link
        href={home}
        onClick={close}
        className="flex items-center gap-3 text-white"
      >
        <span className="grid size-10 place-items-center rounded-xl bg-cyan-400/15 text-cyan-300">
          <Blocks className="size-5" />
        </span>
        <span className="text-xl font-semibold tracking-tight">
          Taskspace
          <span className="mt-1 block text-[10px] font-normal uppercase tracking-[.2em] text-[#8fa8c6]">
            Enterprise workspace
          </span>
        </span>
      </Link>
      <div className="my-9 rounded-xl border border-white/10 bg-white/5 p-4">
        <p className="text-xs font-medium capitalize text-white">
          {name} portal
        </p>
        <p className="mt-1 text-xs leading-5">
          Your work. A clearer perspective.
        </p>
      </div>
      <nav aria-label="Main navigation" className="space-y-1.5">
        {navigation.map(({ label, path, icon: Icon }) => {
          const href = home + path;
          const selected = active?.path === path;
          return (
            <Link
              key={path}
              href={href}
              onClick={close}
              aria-current={selected ? "page" : undefined}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-3 text-sm transition-colors hover:bg-white/5 hover:text-white focus-visible:outline-2 focus-visible:outline-cyan-300",
                selected && "bg-cyan-400/15 text-cyan-200",
              )}
            >
              <Icon className="size-[18px]" />
              <span>{label}</span>
              {selected && (
                <span className="ml-auto size-1.5 rounded-full bg-cyan-300" />
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto pt-12">
        <p className="border-t border-white/10 pt-5 text-xs leading-6">
          Connected teams.
          <br />
          Purposeful work.
        </p>
      </div>
    </div>
  );
  return (
    <PortalPathContext.Provider value={home}>
      <div className="portal-workspace min-h-screen bg-background text-foreground">
        <a
          href="#main-content"
          className="sr-only fixed left-4 top-4 z-[60] rounded-lg bg-white p-3 text-slate-900 focus:not-sr-only"
        >
          Skip to content
        </a>
        <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 overflow-y-auto lg:block">
          {sidebar()}
        </aside>
        <div className="min-w-0 lg:pl-64">
          <header className="flex min-h-20 flex-wrap items-center justify-between gap-3 border-b bg-white px-4 py-4 sm:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <Dialog.Root open={open} onOpenChange={setOpen}>
                <Dialog.Trigger asChild>
                  <button
                    className="rounded-lg p-2 focus-visible:outline-2 lg:hidden"
                    aria-label="Open navigation"
                  >
                    <Menu className="size-5" />
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-950/50" />
                  <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[90vw] overflow-y-auto">
                    <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                    <Dialog.Description className="sr-only">
                      Your portal pages
                    </Dialog.Description>
                    {sidebar(() => setOpen(false))}
                    <Dialog.Close asChild>
                      <button
                        aria-label="Close navigation"
                        className="absolute right-3 top-3 rounded p-2 text-white"
                      >
                        <X className="size-4" />
                      </button>
                    </Dialog.Close>
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <div>
                <p className="text-[10px] uppercase tracking-[.18em] text-muted-foreground">
                  {name} portal
                </p>
                <p className="mt-1 text-sm font-medium">
                  {active?.label ?? "Workspace"}
                </p>
              </div>
            </div>
            <div className="flex min-w-0 items-center gap-2 sm:gap-4">
              <ConnectionStatus />
              <UnreadNotificationLink />
              <UserMenu user={user} />
            </div>
          </header>
          <main
            id="main-content"
            tabIndex={-1}
            className="mx-auto min-w-0 max-w-[1600px] px-4 py-7 sm:px-8 lg:p-10"
          >
            {children}
          </main>
          <footer className="flex flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-muted-foreground sm:px-8">
            <span>
              Taskspace · {user.role === "MEMBER" ? "Employee" : name} workspace
            </span>
            <Link
              href={home + "/notifications"}
              className="inline-flex items-center gap-1"
            >
              Stay connected <ArrowUpRight className="size-3" />
            </Link>
          </footer>
        </div>
      </div>
    </PortalPathContext.Provider>
  );
}
