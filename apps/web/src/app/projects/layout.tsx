import Link from "next/link";
import type { ReactNode } from "react";
import { requireProjectViewer } from "@/project-workspace/server";
import "@/project-workspace/project.css";
export default async function Layout({ children }: { children: ReactNode }) {
  const { actor } = await requireProjectViewer();
  return (
    <div className="project-context-shell">
      <a className="project-skip" href="#project-main">
        Skip to main content
      </a>
      <header>
        <Link href="/projects">Taskspace · Assigned projects</Link>
        <span>{actor.displayName}</span>
        <form action="/auth/logout" method="post">
          <button>Sign out</button>
        </form>
      </header>
      <main id="project-main">{children}</main>
    </div>
  );
}
