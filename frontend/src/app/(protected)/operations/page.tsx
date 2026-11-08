import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getSession } from "@/auth/session";
import { OperationsPanel } from "@/features/operations/operations-panel";

export const metadata: Metadata = { title: "Operations" };

export default async function OperationsPage() {
  const session = await getSession();
  if (!session || session.record.employee.role !== "ADMIN") {
    redirect("/access-denied");
  }

  return <OperationsPanel />;
}
