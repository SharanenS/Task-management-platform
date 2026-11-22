import { redirect } from "next/navigation";
import Link from "next/link";
import { currentSession, sessionCookie } from "@/shared/auth/session";
import { accountEntry, AccountDenied } from "@/shared/api/account-entry";
import { AuthFrame } from "@/shared/ui/auth-frame";
export const dynamic = "force-dynamic";
export default async function ReadyPage() {
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
    if (error instanceof AccountDenied)
      return (
        <AuthFrame
          eyebrow="ACCESS RESTRICTED"
          title="Your account isn’t ready."
          description="Your account does not currently have access. Contact your company administrator."
        >
          <form method="post" action="/auth/logout">
            <button className="secondary-button">Sign out</button>
          </form>
        </AuthFrame>
      );
    redirect("/session-unavailable");
  }
  if (actor.companyRoles[0] === "ADMIN") redirect("/admin");
  if (actor.companyRoles[0] === "MANAGER") redirect("/manager");
  return (
    <AuthFrame
      eyebrow="SIGNED IN"
      title="You’re securely signed in."
      description={
        actor.companyRoles[0] === "EMPLOYEE"
          ? "Your identity and active account have been verified. Open assigned projects to see your current project access."
          : "Your identity and active account have been verified. Your workspace is not available yet."
      }
    >
      <div className="account-summary">
        <span className="avatar" aria-hidden="true">
          ✓
        </span>
        <div>
          <strong>{actor.displayName}</strong>
          <p>{actor.companyRoles.join(", ")} · Verified account</p>
        </div>
      </div>
      {actor.companyRoles[0] === "EMPLOYEE" && (
        <p>
          <Link href="/projects">Open assigned projects</Link>
        </p>
      )}
      <p className="support-note">You can sign out securely below.</p>
      <form method="post" action="/auth/logout">
        <button className="secondary-button">Sign out</button>
      </form>
    </AuthFrame>
  );
}
