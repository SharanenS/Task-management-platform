import { AuthFrame } from "@/shared/ui/auth-frame";
export default async function SignIn({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const message =
    status === "unavailable"
      ? "We couldn’t reach the sign-in service. Please try again shortly."
      : status === "interrupted"
        ? "Your sign-in could not be completed. Please start again."
        : null;
  return (
    <AuthFrame
      eyebrow="WELCOME TO TASKSPACE"
      title="Make room for your best work."
      description="Sign in with your company account to continue."
    >
      {message && (
        <div role="alert" className="notice">
          {message}
        </div>
      )}
      <form method="post" action="/auth/login">
        <button className="primary-button">
          Continue to sign in <span aria-hidden="true">↗</span>
        </button>
      </form>
      <div className="security-note">
        <span aria-hidden="true">◇</span>
        <p>
          Your password is handled by your company’s secure sign-in service.
        </p>
      </div>
      <div className="help-block">
        <strong>Need an account or help signing in?</strong>
        <p>Contact your company administrator.</p>
      </div>
    </AuthFrame>
  );
}
