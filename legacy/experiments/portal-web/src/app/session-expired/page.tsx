import Link from "next/link";
import { Clock3 } from "lucide-react";

export default function SessionExpiredPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 px-5">
      <section className="max-w-md rounded-2xl border bg-card p-9 text-center shadow-sm">
        <Clock3 className="mx-auto size-9 text-primary" />
        <h1 className="mt-5 text-2xl font-semibold">
          Your session has expired
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Sign in again to continue. Your intended workspace data remains
          unchanged.
        </p>
        <Link
          className="mt-7 inline-flex rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white"
          href="/sign-in"
        >
          Return to sign in
        </Link>
      </section>
    </main>
  );
}
