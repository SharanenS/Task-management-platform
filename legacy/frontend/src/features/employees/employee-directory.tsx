"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import {
  ApplicationRole,
  EmployeeDirectoryDocument,
  type EmployeeDirectoryQuery,
} from "@/graphql/generated/graphql";
import { requestGraphQL } from "@/lib/graphql";

const PAGE_SIZE = 12;
const ROLES: ApplicationRole[] = ["ADMIN", "MANAGER", "MEMBER"];
type DirectoryEmployee = EmployeeDirectoryQuery["employees"]["nodes"][number];

export function EmployeeDirectory() {
  const [items, setItems] = useState<DirectoryEmployee[]>([]);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [role, setRole] = useState<ApplicationRole | "">("");
  const [active, setActive] = useState<"" | "true" | "false">("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [history, setHistory] = useState<Array<string | null>>([]);
  const [pageInfo, setPageInfo] = useState({
    hasNextPage: false,
    endCursor: null as string | null,
  });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const data = await requestGraphQL(EmployeeDirectoryDocument, {
        first: PAGE_SIZE,
        after: cursor,
        search: appliedSearch || null,
        role: role || null,
        active: active === "" ? null : active === "true",
      });
      setItems(data.employees.nodes);
      setPageInfo(data.employees.pageInfo);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [active, appliedSearch, cursor, role]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function applyFilters(event: React.FormEvent) {
    event.preventDefault();
    setHistory([]);
    setCursor(null);
    setAppliedSearch(search.trim());
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[.14em] text-primary uppercase">
            Administration
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Employees
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Manage application access, roles, and linked identities.
          </p>
        </div>
        <Button asChild>
          <Link href="/employees/new">
            <Plus /> Provision employee
          </Link>
        </Button>
      </div>

      <Card className="p-4 sm:p-5">
        <form
          onSubmit={applyFilters}
          className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_180px_180px_auto]"
        >
          <label className="relative">
            <span className="sr-only">Search employees</span>
            <Search className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Name, username, or email"
              className="h-10 w-full rounded-lg border bg-background pr-3 pl-10 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <label>
            <span className="sr-only">Role</span>
            <select
              value={role}
              onChange={(event) =>
                setRole(event.target.value as ApplicationRole | "")
              }
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
            >
              <option value="">All roles</option>
              {ROLES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="sr-only">Access status</span>
            <select
              value={active}
              onChange={(event) =>
                setActive(event.target.value as typeof active)
              }
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
            >
              <option value="">All statuses</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
          <Button type="submit">Apply</Button>
        </form>
      </Card>

      {state === "loading" && (
        <Card className="space-y-3 p-5" aria-label="Loading employees">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </Card>
      )}
      {state === "error" && (
        <ErrorState
          title="Unable to load employees"
          description="Employee administration could not be reached."
          onRetry={() => void load()}
        />
      )}
      {state === "ready" && items.length === 0 && (
        <Card>
          <EmptyState
            title="No employees found"
            description="Adjust the filters or provision the first matching employee."
          />
        </Card>
      )}
      {state === "ready" && items.length > 0 && (
        <Card className="overflow-hidden">
          <div className="divide-y">
            {items.map((employee) => (
              <Link
                key={employee.id}
                href={`/employees/${employee.id}`}
                className="grid gap-2 p-4 transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary sm:grid-cols-[1.2fr_1.4fr_auto] sm:items-center sm:px-5"
              >
                <div>
                  <p className="font-medium">{employee.displayName}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    @{employee.username}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground break-all">
                  {employee.email}
                </p>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Badge>{employee.role}</Badge>
                  <Badge tone={employee.active ? "success" : "neutral"}>
                    {employee.active ? "Active" : "Inactive"}
                  </Badge>
                  {employee.provisioningStatus !== "COMPLETE" && (
                    <Badge tone="warning">Needs reconciliation</Badge>
                  )}
                </div>
              </Link>
            ))}
          </div>
          <div className="flex items-center justify-between border-t p-4">
            <Button
              variant="outline"
              disabled={history.length === 0}
              onClick={() => {
                const previous = history.at(-1) ?? null;
                setHistory((current) => current.slice(0, -1));
                setCursor(previous);
              }}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Up to {PAGE_SIZE} employees per page
            </span>
            <Button
              variant="outline"
              disabled={!pageInfo.hasNextPage || !pageInfo.endCursor}
              onClick={() => {
                setHistory((current) => [...current, cursor]);
                setCursor(pageInfo.endCursor);
              }}
            >
              Next
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
