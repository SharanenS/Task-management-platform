import { createHash, randomBytes } from "node:crypto";

export const TRANSACTION_TTL = 300;
export const SESSION_LIMIT = 30 * 60;
export function identifier() {
  return randomBytes(32).toString("base64url");
}
export function validIdentifier(value: string | undefined): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{43}$/.test(value);
}
export function storageKey(kind: "session" | "transaction", id: string) {
  if (!validIdentifier(id))
    throw new Error("Invalid authentication identifier");
  return `taskspace:portals:auth:v1:${kind}:${createHash("sha256").update(id).digest("hex")}`;
}
export function returnPath(value: string | null | undefined) {
  return value === "/auth/ready" || value === "/admin/security"
    ? value
    : "/auth/ready";
}
export function sameOrigin(origin: string | null, expected: string) {
  return origin === expected;
}
export function sessionLifetime(
  expiresIn: number,
  claimExpiry: number,
  now = Date.now(),
) {
  return Math.max(
    0,
    Math.min(
      SESSION_LIMIT,
      Math.floor(expiresIn),
      Math.floor(claimExpiry - now / 1000),
    ),
  );
}
export type Session = {
  subject: string;
  displayName: string;
  accessToken: string;
  idToken: string;
  expiresAt: number;
};
export type Transaction = {
  state: string;
  nonce: string;
  verifier: string;
  returnTo: string;
  createdAt: number;
  expectedSubject?: string;
};
export interface Store {
  put(key: string, value: string, ttl: number): Promise<void>;
  get(key: string): Promise<string | null>;
  take(key: string): Promise<string | null>;
  remove(key: string): Promise<void>;
}
export async function readSession(
  store: Store,
  id: string | undefined,
  now = Date.now(),
): Promise<Session | null> {
  if (!validIdentifier(id)) return null;
  const key = storageKey("session", id);
  const raw = await store.get(key);
  if (!raw) return null;
  try {
    const record: Session = JSON.parse(raw);
    if (
      typeof record.subject !== "string" ||
      !record.subject ||
      typeof record.displayName !== "string" ||
      typeof record.accessToken !== "string" ||
      !record.accessToken ||
      typeof record.idToken !== "string" ||
      !record.idToken ||
      !Number.isFinite(record.expiresAt) ||
      record.expiresAt <= now
    )
      throw new Error("Invalid session");
    return record;
  } catch {
    await store.remove(key);
    return null;
  }
}
export async function consumeTransaction(
  store: Store,
  id: string | undefined,
  state: string | null,
  now = Date.now(),
): Promise<Transaction> {
  if (!validIdentifier(id))
    throw new Error("Authentication transaction unavailable");
  const raw = await store.take(storageKey("transaction", id));
  if (!raw) throw new Error("Authentication transaction unavailable");
  const value: Transaction = JSON.parse(raw);
  if (
    !state ||
    state !== value.state ||
    typeof value.nonce !== "string" ||
    typeof value.verifier !== "string" ||
    (value.expectedSubject !== undefined &&
      (typeof value.expectedSubject !== "string" || !value.expectedSubject)) ||
    !Number.isFinite(value.createdAt) ||
    value.createdAt > now ||
    now - value.createdAt >= TRANSACTION_TTL * 1000
  ) {
    throw new Error("Authentication transaction rejected");
  }
  return value;
}
