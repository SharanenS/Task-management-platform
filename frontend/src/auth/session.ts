import { randomBytes, randomUUID } from "node:crypto";

import { cookies } from "next/headers";

import { authConfig, CSRF_COOKIE, SESSION_COOKIE } from "@/auth/config";
import { fetchEmployeeProfile } from "@/auth/gateway";
import { getOidcConfiguration, oidc } from "@/auth/oidc";
import { getRedis } from "@/auth/redis";
import type { EmployeeProfile, SessionRecord } from "@/auth/types";

const SESSION_TTL_SECONDS = 8 * 60 * 60;

function cookieOptions(httpOnly: boolean) {
  return {
    httpOnly,
    secure: authConfig.secureCookies,
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  };
}

export async function createSession(
  tokens: {
    access_token: string;
    refresh_token?: string;
    id_token?: string;
    expires_in?: number;
    refresh_expires_in?: number;
  },
  employee: EmployeeProfile,
): Promise<void> {
  const sessionId = randomUUID();
  const csrfToken = randomBytes(32).toString("base64url");
  const now = Date.now();
  const record: SessionRecord = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    idToken: tokens.id_token,
    accessTokenExpiresAt: now + (tokens.expires_in ?? 60) * 1000,
    refreshTokenExpiresAt: tokens.refresh_expires_in
      ? now + tokens.refresh_expires_in * 1000
      : undefined,
    csrfToken,
    employee,
  };
  const redis = await getRedis();
  await redis.set(`session:${sessionId}`, JSON.stringify(record), {
    expiration: { type: "EX", value: SESSION_TTL_SECONDS },
  });
  const store = await cookies();
  store.set(SESSION_COOKIE, sessionId, cookieOptions(true));
  store.set(CSRF_COOKIE, csrfToken, cookieOptions(false));
}

async function loadRecord(sessionId: string): Promise<SessionRecord | null> {
  const value = await (await getRedis()).get(`session:${sessionId}`);
  if (!value) return null;
  try {
    return JSON.parse(value) as SessionRecord;
  } catch {
    return null;
  }
}

async function refreshSession(
  sessionId: string,
  current: SessionRecord,
): Promise<SessionRecord | null> {
  if (
    !current.refreshToken ||
    (current.refreshTokenExpiresAt ?? 0) <= Date.now()
  )
    return null;
  const redis = await getRedis();
  const lockKey = `session-refresh:${sessionId}`;
  const lockValue = randomUUID();
  const acquired = await redis.set(lockKey, lockValue, {
    condition: "NX",
    expiration: { type: "PX", value: 10_000 },
  });
  if (!acquired) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    return loadRecord(sessionId);
  }
  try {
    const tokens = await oidc.refreshTokenGrant(
      getOidcConfiguration(),
      current.refreshToken,
    );
    if (!tokens.access_token) return null;
    const employee = await fetchEmployeeProfile(tokens.access_token);
    const now = Date.now();
    const refreshed: SessionRecord = {
      ...current,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token ?? current.refreshToken,
      idToken: tokens.id_token ?? current.idToken,
      accessTokenExpiresAt: now + (tokens.expires_in ?? 60) * 1000,
      employee,
    };
    await redis.set(`session:${sessionId}`, JSON.stringify(refreshed), {
      expiration: { type: "EX", value: SESSION_TTL_SECONDS },
    });
    return refreshed;
  } catch {
    return null;
  } finally {
    if ((await redis.get(lockKey)) === lockValue) await redis.del(lockKey);
  }
}

export async function getSession(): Promise<{
  id: string;
  record: SessionRecord;
} | null> {
  const sessionId = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!sessionId) return null;
  const record = await loadRecord(sessionId);
  if (!record) return null;
  if (record.accessTokenExpiresAt > Date.now() + 30_000)
    return { id: sessionId, record };
  const refreshed = await refreshSession(sessionId, record);
  if (!refreshed) {
    await (await getRedis()).del(`session:${sessionId}`);
    return null;
  }
  return { id: sessionId, record: refreshed };
}

export async function deleteSession(
  sessionId?: string,
): Promise<SessionRecord | null> {
  const store = await cookies();
  const id = sessionId ?? store.get(SESSION_COOKIE)?.value;
  const record = id ? await loadRecord(id) : null;
  if (id) await (await getRedis()).del(`session:${id}`);
  store.delete(SESSION_COOKIE);
  store.delete(CSRF_COOKIE);
  return record;
}
