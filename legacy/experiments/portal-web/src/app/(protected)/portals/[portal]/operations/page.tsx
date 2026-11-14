import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { requirePortalSession as getSession } from "@/features/portals/server-session";
import { OperationsPanel } from "@/features/operations/operations-panel";

export const metadata: Metadata = { title: "Operations" };

export default async function OperationsPage() {
  const session = await getSession();
  if (!session || session.record.employee.role !== "ADMIN") {
    redirect("/access-denied");
  }

  return <OperationsPanel />;
}
