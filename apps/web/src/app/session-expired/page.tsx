import Link from "next/link";
import { AuthFrame } from "@/shared/ui/auth-frame";
export default function Expired() {
  return (
    <AuthFrame
      eyebrow="SESSION ENDED"
      title="Let’s get you signed in."
      description="Your session has ended. Sign in again to continue securely."
    >
      <Link className="primary-button" href="/sign-in">
        Back to sign in
      </Link>
    </AuthFrame>
  );
}
