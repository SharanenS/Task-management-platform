import "server-only";
import { redirect } from "next/navigation";
import { authConfig } from "@/shared/auth/config";
import { currentSession, sessionCookie } from "@/shared/auth/session";
import { AccountDenied, adminWorkspace } from "@/shared/api/account-entry";

export async function requireAdministrator() {
  const destination = (path: string): never =>
    redirect(new URL(path, authConfig().origin).href);
  if (!(await sessionCookie())) return destination("/sign-in");
  let session;
  try {
    session = await currentSession();
  } catch {
    return destination("/session-unavailable");
  }
  if (!session) return destination("/auth/expired");
  try {
    return { actor: await adminWorkspace(session), session };
  } catch (error) {
    if (error instanceof AccountDenied) return destination("/access-denied");
    return destination("/session-unavailable");
  }
}
