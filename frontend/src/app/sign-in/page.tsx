import { Blocks, LogIn, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { safeReturnPath } from "@/auth/return-path";

const messages: Record<string, { title: string; detail: string }> = {
  callback: {
    title: "Sign-in could not be completed",
    detail:
      "The authentication response was invalid or expired. Start again to continue.",
  },
  unavailable: {
    title: "Authentication service unavailable",
    detail:
      "The identity service could not be reached. Wait a moment and try again.",
  },
  logged_out: {
    title: "You are signed out",
    detail: "Your local session has ended safely.",
  },
};

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ returnTo?: string; error?: string; reason?: string }>;
}) {
  const params = await searchParams;
  const returnTo = safeReturnPath(params.returnTo);
  const message = params.error ? messages[params.error] : undefined;
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 px-5 py-12">
      <section className="w-full max-w-md rounded-2xl border bg-card p-8 shadow-sm sm:p-10">
        <div className="flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl bg-primary text-white">
            <Blocks className="size-6" />
          </span>
          <div>
            <p className="font-semibold">Taskspace</p>
            <p className="text-xs text-muted-foreground">
              Enterprise Task Platform
            </p>
          </div>
        </div>
        <div className="mt-10">
          <h1 className="text-2xl font-semibold tracking-tight">
            {message?.title ?? "Sign in to your workspace"}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {message?.detail ??
              "Use your organization account to access your employee workspace."}
          </p>
        </div>
        <Link
          href={`/auth/login?returnTo=${encodeURIComponent(returnTo)}`}
          prefetch={false}
          className="mt-8 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          <LogIn className="size-4" /> Sign in
        </Link>
        <div className="mt-8 flex items-start gap-3 border-t pt-6 text-xs leading-5 text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
          Credentials are handled by the organization identity service. This
          application does not expose authentication tokens to browser storage.
        </div>
      </section>
    </main>
  );
}
