"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/states";
import {
  ApplicationRole,
  EmployeeDetailDocument,
  ReconcileEmployeeDocument,
  SetEmployeeActiveDocument,
  UpdateEmployeeRoleDocument,
  type EmployeeDetailQuery,
} from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

type Detail = EmployeeDetailQuery["employee"];
type PendingAction =
  | { kind: "active"; value: boolean }
  | { kind: "role"; value: ApplicationRole }
  | { kind: "reconcile" };
const ROLES: ApplicationRole[] = ["ADMIN", "MANAGER", "MEMBER"];

export function EmployeeDetail({ id }: { id: string }) {
  const [employee, setEmployee] = useState<Detail | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    try {
      const result = await requestGraphQL(EmployeeDetailDocument, { id });
      setEmployee(result.employee);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [id]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function confirmAction() {
    if (!pending || !employee || saving) return;
    setSaving(true);
    setMessage(null);
    try {
      if (pending.kind === "active")
        await requestGraphQL(SetEmployeeActiveDocument, {
          employeeId: id,
          active: pending.value,
        });
      if (pending.kind === "role")
        await requestGraphQL(UpdateEmployeeRoleDocument, {
          employeeId: id,
          role: pending.value,
        });
      if (pending.kind === "reconcile")
        await requestGraphQL(ReconcileEmployeeDocument, { employeeId: id });
      setPending(null);
      setMessage("Employee access was updated.");
      await load();
    } catch (caught) {
      setMessage(
        caught instanceof GraphQLRequestError
          ? caught.message
          : "The update could not be completed.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (state === "loading")
    return (
      <Card className="space-y-4 p-6" aria-label="Loading employee">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-28" />
      </Card>
    );
  if (state === "error" || !employee)
    return (
      <ErrorState
        title="Unable to load employee"
        description="The employee record could not be retrieved."
        onRetry={() => void load()}
      />
    );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/employees"
            className="text-xs font-medium text-primary hover:underline"
          >
            ← Employee directory
          </Link>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            {employee.displayName}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            @{employee.username}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge tone={employee.active ? "success" : "neutral"}>
            {employee.active ? "Active" : "Inactive"}
          </Badge>
          <Badge>{employee.role}</Badge>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
        <Card className="p-6">
          <h2 className="font-semibold">Employee profile</h2>
          <dl className="mt-5 grid gap-5 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-muted-foreground">Email</dt>
              <dd className="mt-1 text-sm break-all">{employee.email}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Username</dt>
              <dd className="mt-1 text-sm">{employee.username}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Created</dt>
              <dd className="mt-1 text-sm">
                {new Date(String(employee.createdAt)).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Last updated</dt>
              <dd className="mt-1 text-sm">
                {new Date(String(employee.updatedAt)).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                Identity synchronization
              </dt>
              <dd className="mt-1 text-sm">
                {employee.provisioningStatus === "COMPLETE"
                  ? "Complete"
                  : "Reconciliation required"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Record version</dt>
              <dd className="mt-1 text-sm">{employee.version}</dd>
            </div>
          </dl>
        </Card>
        <Card className="p-6">
          <h2 className="font-semibold">Administrative actions</h2>
          <div className="mt-5 space-y-5">
            <label className="block text-sm font-medium">
              Application role
              <select
                value={employee.role}
                onChange={(event) =>
                  setPending({
                    kind: "role",
                    value: event.target.value as ApplicationRole,
                  })
                }
                className="mt-2 h-10 w-full rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring"
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="outline"
              onClick={() =>
                setPending({ kind: "active", value: !employee.active })
              }
            >
              {employee.active ? "Deactivate employee" : "Activate employee"}
            </Button>
            {employee.provisioningStatus !== "COMPLETE" && (
              <Button
                variant="outline"
                onClick={() => setPending({ kind: "reconcile" })}
              >
                Retry reconciliation
              </Button>
            )}
          </div>
        </Card>
      </div>
      {pending && (
        <Card
          className="border-amber-200 bg-amber-50 p-5"
          role="alertdialog"
          aria-labelledby="confirm-title"
        >
          <h2 id="confirm-title" className="font-semibold text-amber-950">
            Confirm administrative change
          </h2>
          <p className="mt-2 text-sm text-amber-900">
            This action changes application access. Final-admin and
            self-protection rules are enforced by the server.
          </p>
          <div className="mt-4 flex gap-3">
            <Button onClick={() => void confirmAction()} disabled={saving}>
              {saving ? "Updating…" : "Confirm"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setPending(null)}
              disabled={saving}
            >
              Cancel
            </Button>
          </div>
        </Card>
      )}
      {message && (
        <p role="status" className="rounded-lg border bg-card p-4 text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
