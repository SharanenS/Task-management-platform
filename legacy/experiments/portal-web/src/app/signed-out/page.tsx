import { CheckCircle2, LogIn } from "lucide-react";
import Link from "next/link";

export default function SignedOutPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 px-5 py-12">
      <section className="w-full max-w-md rounded-2xl border bg-card p-8 text-center shadow-sm sm:p-10">
        <CheckCircle2 className="mx-auto size-10 text-primary" />
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">
          You are signed out
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Your application session and organization sign-in session have ended.
        </p>
        <Link
          href="/sign-in"
          className="mt-8 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <LogIn className="size-4" /> Sign in again
        </Link>
      </section>
    </main>
  );
}
