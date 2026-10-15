"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Activity,
  ArrowUpRight,
  Blocks,
  BookOpen,
  ChevronRight,
  CircleHelp,
  FolderKanban,
  LayoutDashboard,
  Menu,
  Palette,
  Users,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConnectionStatus } from "@/features/system/connection-status";
import { cn } from "@/lib/utils";
import type { EmployeeProfile } from "@/auth/types";
import { canViewEmployeeNavigation } from "@/auth/authorization";
import { UserMenu } from "@/components/layout/user-menu";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Projects", href: "/projects", icon: FolderKanban },
  { label: "Employees", href: "/employees", icon: Users },
  { label: "Workflows", icon: Workflow, phase: 10 },
  { label: "Background jobs", icon: Zap, phase: 6 },
];
const foundation = [
  { label: "System status", href: "/system", icon: Activity },
  { label: "Design system", href: "/design-system", icon: Palette },
];

function Sidebar({
  close,
  user,
}: {
  close?: () => void;
  user: EmployeeProfile;
}) {
  const pathname = usePathname();
  return (
    <div className="flex h-full flex-col bg-sidebar px-4 py-6">
      <Link
        href="/"
        onClick={close}
        className="mb-9 flex items-center gap-3 px-3"
      >
        <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-white">
          <Blocks className="size-5" />
        </span>
        <span className="text-lg font-semibold tracking-tight">
          Taskspace
          <span className="mt-0.5 block text-[10px] font-medium tracking-[.14em] text-muted-foreground uppercase">
            Enterprise platform
          </span>
        </span>
      </Link>
      <div className="mb-6 flex items-center gap-3 rounded-lg border bg-card/60 px-3 py-3">
        <span className="flex size-8 items-center justify-center rounded-md border bg-background text-xs font-semibold">
          WS
        </span>
        <div>
          <p className="text-xs font-semibold">Development workspace</p>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Single enterprise deployment
          </p>
        </div>
      </div>
      <nav aria-label="Main navigation">
        <p className="nav-label">Workspace</p>
        <div className="mt-2 space-y-1">
          {navigation
            .filter(
              ({ label }) =>
                label !== "Employees" || canViewEmployeeNavigation(user.role),
            )
            .map(({ label, href, icon: Icon, phase }) =>
              href ? (
                <Link
                  key={label}
                  href={href}
                  onClick={close}
                  aria-current={pathname === href ? "page" : undefined}
                  className={cn("nav-item", pathname === href && "nav-active")}
                >
                  <Icon />
                  <span>{label}</span>
                </Link>
              ) : (
                <button
                  key={label}
                  disabled
                  title={`Available in Phase ${phase}`}
                  className="nav-item w-full cursor-not-allowed opacity-55"
                >
                  <Icon />
                  <span>{label}</span>
                  <span className="ml-auto text-[9px] font-medium uppercase tracking-wider">
                    Soon
                  </span>
                </button>
              ),
            )}
        </div>
        <p className="nav-label mt-8">Foundation</p>
        <div className="mt-2 space-y-1">
          {foundation.map(({ label, href, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              onClick={close}
              aria-current={pathname === href ? "page" : undefined}
              className={cn("nav-item", pathname === href && "nav-active")}
            >
              <Icon />
              {label}
            </Link>
          ))}
        </div>
      </nav>
      <div className="mt-auto pt-10">
        <div className="rounded-xl border border-emerald-900/10 bg-emerald-900/[.035] p-4">
          <span className="text-[10px] font-semibold uppercase tracking-[.15em] text-primary">
            Building the foundation
          </span>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            A considered workspace.
            <br />
            One verified feature at a time.
          </p>
          <Link
            href="/system"
            onClick={close}
            className="mt-3 flex items-center gap-2 text-xs font-semibold text-primary"
          >
            Explore Phase 1 <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
        <div className="mt-5 flex items-center justify-between px-2 text-[10px] text-muted-foreground">
          <span>v0.1.0 · Development</span>
          <CircleHelp className="size-3.5" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}

export function AppShell({
  children,
  user,
}: {
  children: React.ReactNode;
  user: EmployeeProfile;
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const title =
    pathname === "/system"
      ? "System status"
      : pathname === "/design-system"
        ? "Design system"
        : pathname.startsWith("/employees")
          ? "Employees"
          : pathname.startsWith("/projects")
            ? "Projects"
            : "Overview";
  return (
    <div className="min-h-screen">
      <a
        href="#main-content"
        className="sr-only fixed top-3 left-3 z-50 rounded bg-primary px-4 py-2 text-white focus:not-sr-only"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r lg:block">
        <Sidebar user={user} />
      </aside>
      <div className="lg:pl-64">
        <header className="flex h-[76px] items-center justify-between gap-3 border-b bg-card px-5 sm:px-8 lg:px-10">
          <div className="flex items-center gap-3">
            <Dialog.Root open={open} onOpenChange={setOpen}>
              <Dialog.Trigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Open navigation"
                  className="lg:hidden"
                >
                  <Menu />
                </Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[90vw] overflow-y-auto shadow-xl">
                  <Dialog.Title className="sr-only">Navigation</Dialog.Title>
                  <Dialog.Description className="sr-only">
                    Workspace and foundation pages
                  </Dialog.Description>
                  <Sidebar close={() => setOpen(false)} user={user} />
                  <Dialog.Close asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-2 right-2"
                      aria-label="Close navigation"
                    >
                      <X />
                    </Button>
                  </Dialog.Close>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Workspace
            </span>
            <ChevronRight className="hidden size-3 text-muted-foreground sm:block" />
            <span className="text-xs font-medium">{title}</span>
          </div>
          <div className="flex items-center gap-4">
            <ConnectionStatus />
            <span className="hidden h-5 border-l sm:block" />
            <UserMenu user={user} />
          </div>
        </header>
        <main
          id="main-content"
          className="mx-auto max-w-[1600px] px-5 py-8 sm:px-8 lg:px-10 lg:py-10"
        >
          {children}
        </main>
        <footer className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-5 pb-6 text-[11px] text-muted-foreground sm:px-8 lg:px-10">
          <span>
            Enterprise Task Platform <span className="mx-2 text-border">/</span>{" "}
            Authenticated workspace
          </span>
          <Link
            href="/design-system"
            className="inline-flex items-center gap-1.5 hover:text-primary"
          >
            <BookOpen className="size-3" /> Interface guidelines
          </Link>
        </footer>
      </div>
    </div>
  );
}
