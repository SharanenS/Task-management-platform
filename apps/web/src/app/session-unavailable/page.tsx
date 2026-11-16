import Link from "next/link";
import { AuthFrame } from "@/shared/ui/auth-frame";
export default function Unavailable() {
  return (
    <AuthFrame
      eyebrow="CONNECTION INTERRUPTED"
      title="We can’t check your session."
      description="Secure access is temporarily unavailable. Please try again shortly. If you were signing out, it has not been confirmed."
    >
      <Link className="primary-button" href="/auth/ready">
        Try again
      </Link>
      <form method="post" action="/auth/logout">
        <button className="secondary-button">Retry sign out</button>
      </form>
    </AuthFrame>
  );
}
