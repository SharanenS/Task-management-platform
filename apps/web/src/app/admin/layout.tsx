import type { ReactNode } from "react";
import { requireAdministrator } from "@/portals/admin/server";
import { AdminShell } from "@/portals/admin/shell";
import "@/portals/admin/admin.css";
export const dynamic = "force-dynamic";
export default async function AdminLayout({
  children,
}: {
  children: ReactNode;
}) {
  const { actor } = await requireAdministrator();
  return <AdminShell name={actor.displayName}>{children}</AdminShell>;
}
