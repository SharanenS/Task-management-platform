import { redirect } from "next/navigation";

import { requirePortalSession as getSession } from "@/features/portals/server-session";

export default async function EmployeeAdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await getSession();
  if (!session) redirect("/session-expired");
  if (session.record.employee.role !== "ADMIN") redirect("/access-denied");
  return children;
}
