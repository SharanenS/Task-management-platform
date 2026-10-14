"use client";

import { useRef, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ApplicationRole,
  ProvisionEmployeeDocument,
} from "@/graphql/generated/graphql";
import { GraphQLRequestError, requestGraphQL } from "@/lib/graphql";

const fieldClass =
  "mt-1.5 h-10 w-full rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring";
const ROLES: ApplicationRole[] = ["ADMIN", "MANAGER", "MEMBER"];

export function ProvisionEmployeeForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [employeeId, setEmployeeId] = useState<string | null>(null);
  const idempotencyKey = useRef<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    const form = new FormData(event.currentTarget);
    idempotencyKey.current ??= crypto.randomUUID();
    try {
      const result = await requestGraphQL(ProvisionEmployeeDocument, {
        input: {
          idempotencyKey: idempotencyKey.current,
          username: String(form.get("username") ?? ""),
          email: String(form.get("email") ?? ""),
          displayName: String(form.get("displayName") ?? ""),
          role: String(form.get("role")) as ApplicationRole,
          active: form.get("active") === "on",
          temporaryPassword: String(form.get("temporaryPassword") ?? ""),
        },
      });
      setEmployeeId(result.provisionEmployee.id);
      event.currentTarget.reset();
    } catch (caught) {
      setError(
        caught instanceof GraphQLRequestError
          ? caught.message
          : "Employee provisioning is temporarily unavailable.",
      );
    } finally {
      setPending(false);
    }
  }

  if (employeeId) {
    return (
      <Card className="max-w-2xl p-6 sm:p-8" role="status">
        <h2 className="text-xl font-semibold">Employee provisioned</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          The linked identity and employee profile are ready. The temporary
          credential was not retained or returned.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild>
            <Link href={`/employees/${employeeId}`}>View employee</Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              idempotencyKey.current = null;
              setEmployeeId(null);
            }}
          >
            Provision another
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="max-w-2xl p-6 sm:p-8">
      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Username
            <input
              required
              name="username"
              minLength={3}
              maxLength={100}
              pattern="[A-Za-z0-9.-]+"
              autoComplete="off"
              className={fieldClass}
            />
            <span className="mt-1 block text-xs font-normal text-muted-foreground">
              Letters, numbers, periods, and hyphens.
            </span>
          </label>
          <label className="text-sm font-medium">
            Email
            <input
              required
              name="email"
              type="email"
              maxLength={320}
              autoComplete="off"
              className={fieldClass}
            />
          </label>
        </div>
        <label className="block text-sm font-medium">
          Display name
          <input
            required
            name="displayName"
            minLength={2}
            maxLength={200}
            autoComplete="off"
            className={fieldClass}
          />
        </label>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Application role
            <select name="role" defaultValue="MEMBER" className={fieldClass}>
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm font-medium">
            Temporary password
            <input
              required
              name="temporaryPassword"
              type="password"
              minLength={12}
              maxLength={200}
              autoComplete="new-password"
              className={fieldClass}
            />
            <span className="mt-1 block text-xs font-normal text-muted-foreground">
              At least 12 characters. Keycloak requires a change at first login.
            </span>
          </label>
        </div>
        <label className="flex items-start gap-3 rounded-lg border p-4 text-sm">
          <input
            name="active"
            type="checkbox"
            defaultChecked
            className="mt-0.5 size-4"
          />
          <span>
            <span className="font-medium">Activate after provisioning</span>
            <span className="mt-1 block text-xs leading-5 text-muted-foreground">
              The identity remains disabled until the application profile is
              safely stored.
            </span>
          </span>
        </label>
        {error && (
          <p
            role="alert"
            className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
          >
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={pending}>
            {pending ? "Provisioning…" : "Provision employee"}
          </Button>
          <Button asChild variant="outline">
            <Link href="/employees">Cancel</Link>
          </Button>
        </div>
      </form>
    </Card>
  );
}
