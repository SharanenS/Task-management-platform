import "server-only";
import { print } from "graphql";
import type { TypedDocumentNode } from "@graphql-typed-document-node/core";
import type { Session } from "@/shared/auth/policy";
import { AccountDenied } from "./account-entry";
export class AccountChangeRejected extends Error {}
export class CalendarChangeRejected extends Error {
  constructor(readonly reason: string) {
    super("Calendar request rejected");
  }
}
export async function administrationRequest<T, V>(
  session: Session,
  document: TypedDocumentNode<T, V>,
  variables: V,
): Promise<T> {
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
    body: JSON.stringify({ query: print(document), variables }),
    signal: AbortSignal.timeout(25000),
  });
  if ([401, 403].includes(response.status)) throw new AccountDenied();
  if (!response.ok) throw new Error("Account service unavailable");
  const value = await response.json();
  if (
    value.errors?.some(
      (e: { extensions?: { code?: string } }) =>
        e.extensions?.code === "FORBIDDEN",
    )
  )
    throw new AccountDenied();
  if (
    value.errors?.some(
      (e: { extensions?: { code?: string } }) =>
        e.extensions?.code === "ACCOUNT_CHANGE_REJECTED",
    )
  )
    throw new AccountChangeRejected();
  const calendarError = value.errors?.find(
    (e: { extensions?: { code?: string; reason?: string } }) =>
      e.extensions?.code === "CALENDAR_REJECTED",
  );
  if (calendarError)
    throw new CalendarChangeRejected(
      String(calendarError.extensions?.reason ?? "calendar_rejected"),
    );
  if (value.errors || !value.data)
    throw new Error("Account service unavailable");
  return value.data;
}
