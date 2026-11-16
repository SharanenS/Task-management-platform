import "server-only";
import { cookies } from "next/headers";
import { authConfig } from "./config";
import { authStore } from "./store";
import { readSession } from "./policy";

export async function sessionCookie() {
  return (await cookies()).get(authConfig().sessionCookie)?.value;
}
export async function currentSession() {
  return readSession(authStore, await sessionCookie());
}
export function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: authConfig().secure,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
