import Link from "next/link";
import { ManagerNavigation } from "./navigation";
import type { ReactNode } from "react";
export function ManagerShell({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}) {
  return (
    <div className="manager-shell">
      <a className="manager-skip" href="#main-content">
        Skip to main content
      </a>
      <aside className="manager-sidebar">
        <Link className="manager-brand" href="/manager">
          Taskspace<span>MANAGER WORKSPACE</span>
        </Link>
        <ManagerNavigation />
        <p>
          Create clear objectives.
          <br />
          Keep commitments visible.
        </p>
      </aside>
      <div className="manager-body">
        <header>
          <div>
            <strong>{name}</strong>
            <span>MANAGER</span>
          </div>
          <form action="/auth/logout" method="post">
            <button>Sign out</button>
          </form>
        </header>
        <main id="main-content">{children}</main>
      </div>
    </div>
  );
}
