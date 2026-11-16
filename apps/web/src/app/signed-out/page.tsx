import Link from "next/link";
import { AuthFrame } from "@/shared/ui/auth-frame";
export default async function SignedOut({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  return (
    <AuthFrame
      eyebrow="SIGNED OUT"
      title="See you next time."
      description="Your Taskspace application session has ended."
    >
      {status === "provider" && (
        <div role="alert" className="notice">
          Your company sign-in service was unavailable. Its separate sign-in
          session may still be active. Close this browser on a shared device.
        </div>
      )}
      <Link className="primary-button" href="/sign-in">
        Back to sign in
      </Link>
    </AuthFrame>
  );
}
