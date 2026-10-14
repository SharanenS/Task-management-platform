import Link from "next/link";
import { ShieldX } from "lucide-react";

export default function AccessDeniedPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 px-5">
      <section className="max-w-md rounded-2xl border bg-card p-9 text-center shadow-sm">
        <ShieldX className="mx-auto size-9 text-amber-700" />
        <h1 className="mt-5 text-2xl font-semibold">
          Workspace access unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Your identity is valid, but no active employee profile is linked to
          this account. Contact an administrator if you believe this is
          unexpected.
        </p>
        <Link
          className="mt-7 inline-flex rounded-lg border px-5 py-2.5 text-sm font-semibold"
          href="/sign-in"
        >
          Back to sign in
        </Link>
      </section>
    </main>
  );
}
