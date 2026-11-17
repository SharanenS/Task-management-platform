import Link from "next/link";
import type { ReactNode } from "react";
import { AdminNavigation } from "./navigation";
export function AdminShell({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}) {
  return (
    <div className="admin-shell">
      <a className="admin-skip" href="#admin-content">
        Skip to content
      </a>
      <aside className="admin-sidebar">
        <Link href="/admin" className="admin-brand">
          <span aria-hidden="true">▦</span>Taskspace
        </Link>
        <p className="admin-sidebar-caption">ADMINISTRATION</p>
        <AdminNavigation />
        <div className="admin-sidebar-footer">
          <span className="admin-status-dot" />
          Secure workspace
        </div>
      </aside>
      <div className="admin-main">
        <header className="admin-header">
          <div>
            <span className="admin-header-label">YOUR WORKSPACE</span>
            <p>Administration</p>
          </div>
          <div className="admin-account">
            <span className="admin-avatar" aria-hidden="true">
              {name.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <strong>{name}</strong>
              <span>Administrator</span>
            </div>
            <form method="post" action="/auth/logout">
              <button className="admin-signout">Sign out</button>
            </form>
          </div>
        </header>
        <main id="admin-content" className="admin-content">
          {children}
        </main>
        <footer className="admin-footer">Taskspace · Work, connected.</footer>
      </div>
    </div>
  );
}
