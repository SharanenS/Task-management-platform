import Link from "next/link";
import type { ReactNode } from "react";
export function AuthFrame({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main className="auth-layout">
      <section className="brand-panel" aria-label="Taskspace introduction">
        <Link href="/sign-in" className="brand">
          <span className="brand-symbol" aria-hidden="true">
            ▦
          </span>
          Taskspace<span className="brand-caption">WORK, CONNECTED.</span>
        </Link>
        <div className="brand-story">
          <p className="eyebrow">A CLEARER WAY TO WORK</p>
          <h2>
            Good work starts
            <br />
            with a connected team.
          </h2>
          <p>
            One place to bring your people, projects and priorities together.
          </p>
          <div className="brand-lines" aria-hidden="true">
            <span />
            <span />
            <span />
            <i />
          </div>
        </div>
        <p className="brand-footer">
          Your people. Your projects. One Taskspace.
        </p>
      </section>
      <section className="form-panel">
        <div className="auth-card">
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p className="description">{description}</p>
          {children}
        </div>
        <footer>Taskspace · Secure workspace access</footer>
      </section>
    </main>
  );
}
