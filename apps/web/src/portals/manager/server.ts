import "server-only";
import { redirect } from "next/navigation";
import { currentSession, sessionCookie } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
export async function requireProjectAuthor(role?: "ADMIN" | "MANAGER") {
  if (!(await sessionCookie())) redirect("/sign-in");
  let session;
  try {
    session = await currentSession();
  } catch {
    redirect("/session-unavailable");
  }
  if (!session) redirect("/auth/expired");
  let actor;
  try {
    actor = await accountEntry(session);
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    redirect("/session-unavailable");
  }
  if (
    !["ADMIN", "MANAGER"].includes(actor.companyRoles[0]) ||
    (role && actor.companyRoles[0] !== role)
  )
    redirect("/access-denied");
  return {
    actor,
    session,
    root:
      actor.companyRoles[0] === "ADMIN"
        ? "/admin/projects"
        : "/manager/projects",
  };
}
