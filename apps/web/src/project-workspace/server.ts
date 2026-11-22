import "server-only";
import { redirect } from "next/navigation";
import { currentSession, sessionCookie } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";

export async function requireProjectViewer() {
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
  if (!["ADMIN", "MANAGER", "EMPLOYEE"].includes(actor.companyRoles[0]))
    redirect("/access-denied");
  return {
    session,
    actor,
    root:
      actor.companyRoles[0] === "ADMIN"
        ? "/admin/projects"
        : actor.companyRoles[0] === "MANAGER"
          ? "/manager/projects"
          : "/projects",
  };
}
