import type { ReactNode } from "react";
import { requireProjectAuthor } from "@/portals/manager/server";
import { ManagerShell } from "@/portals/manager/shell";
import "@/portals/manager/manager.css";
import "@/project-workspace/project.css";
export const dynamic = "force-dynamic";
export default async function ManagerLayout({
  children,
}: {
  children: ReactNode;
}) {
  const { actor } = await requireProjectAuthor("MANAGER");
  return <ManagerShell name={actor.displayName}>{children}</ManagerShell>;
}
