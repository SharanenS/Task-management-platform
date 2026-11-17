import Link from "next/link";
import { AuthFrame } from "@/shared/ui/auth-frame";
export default function Denied() {
  return (
    <AuthFrame
      eyebrow="ACCESS RESTRICTED"
      title="You don’t have access to this page."
      description="This area is available to authorized administrators. Return to your account to continue."
    >
      <Link href="/auth/ready" className="primary-button">
        Back to your account
      </Link>
      <form method="post" action="/auth/logout">
        <button className="secondary-button">Sign out</button>
      </form>
    </AuthFrame>
  );
}
