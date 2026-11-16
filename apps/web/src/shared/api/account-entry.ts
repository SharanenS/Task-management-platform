import "server-only";
import { print } from "graphql";
import { AccountEntryDocument } from "./generated";
import type { Session } from "@/shared/auth/policy";
import type { AccountEntryQuery } from "./generated";

export class AccountDenied extends Error {}
export async function accountEntry(
  session: Session,
): Promise<AccountEntryQuery["viewer"]> {
  const endpoint = new URL(
    process.env.ACCOUNT_GRAPHQL_URL ?? "http://gateway:8000/graphql",
  );
  if (
    endpoint.username ||
    endpoint.password ||
    endpoint.search ||
    endpoint.hash ||
    endpoint.pathname !== "/graphql" ||
    (endpoint.protocol !== "https:" &&
      !(
        process.env.AUTH_ALLOW_LOCAL_HTTP === "true" &&
        endpoint.origin === "http://gateway:8000"
      ))
  )
    throw new Error("Invalid account API boundary");
  const response = await fetch(endpoint, {
    method: "POST",
    cache: "no-store",
    redirect: "error",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.accessToken}`,
    },
    body: JSON.stringify({ query: print(AccountEntryDocument) }),
    signal: AbortSignal.timeout(5000),
  });
  if (response.status === 401 || response.status === 403)
    throw new AccountDenied();
  if (!response.ok) throw new Error("Account service unavailable");
  const result = await response.json();
  const actor = result.data?.viewer;
  if (
    result.errors ||
    !actor ||
    typeof actor.accountId !== "string" ||
    typeof actor.employeeId !== "string" ||
    typeof actor.displayName !== "string" ||
    !Array.isArray(actor.companyRoles) ||
    actor.companyRoles.length !== 1 ||
    !actor.companyRoles.every(
      (role: unknown) =>
        typeof role === "string" &&
        ["ADMIN", "MANAGER", "EMPLOYEE", "HR"].includes(role),
    ) ||
    !Array.isArray(actor.permissions) ||
    actor.permissions.length !== 1 ||
    actor.permissions[0] !== "account:self:read"
  )
    throw new Error("Invalid account response");
  return actor;
}
