import { SessionOptions, getIronSession } from "iron-session";
import { cookies } from "next/headers";

export interface SessionData {
  accessToken?: string;
  refreshToken?: string;
  idToken?: string;
  expiresAt?: number; // Unix timestamp in seconds
  idTokenClaims?: Record<string, unknown>;
}

export const sessionCookieConfig = {
  cookieName: "task_platform_session",
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
  },
} as const;

export const { cookieName, cookieOptions } = sessionCookieConfig;

export function getSessionOptions(): SessionOptions {
  const secret = process.env.SESSION_SECRET;
  if (!secret) {
    throw new Error(
      "SESSION_SECRET environment variable is missing. It must be configured with at least 32 characters."
    );
  }
  if (secret.length < 32) {
    throw new Error(
      `SESSION_SECRET environment variable must be at least 32 characters long (received ${secret.length} characters).`
    );
  }

  return {
    password: secret,
    cookieName: sessionCookieConfig.cookieName,
    cookieOptions: sessionCookieConfig.cookieOptions,
  };
}

export const sessionOptions: SessionOptions = {
  get password() {
    return getSessionOptions().password;
  },
  cookieName: sessionCookieConfig.cookieName,
  cookieOptions: sessionCookieConfig.cookieOptions,
};

export async function getSession() {
  const cookieStore = await cookies();
  // Next.js 16 ReadonlyRequestCookies priority type is stricter than iron-session 8 CookieStore
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return getIronSession<SessionData>(cookieStore as any, getSessionOptions());
}
