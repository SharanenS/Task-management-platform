import { redirect } from "next/navigation";
import { currentSession, sessionCookie } from "@/shared/auth/session";
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
  return (
    <AuthFrame
      eyebrow="SIGNED IN"
      title="You’re securely signed in."
      description="Your identity has been verified. Your workspace is not available yet."
    >
      <div className="account-summary">
        <span className="avatar" aria-hidden="true">
          ✓
        </span>
        <div>
          <strong>{session.displayName}</strong>
          <p>Signed-in account</p>
        </div>
      </div>
      <p className="support-note">You can sign out securely below.</p>
      <form method="post" action="/auth/logout">
        <button className="secondary-button">Sign out</button>
      </form>
    </AuthFrame>
  );
}
