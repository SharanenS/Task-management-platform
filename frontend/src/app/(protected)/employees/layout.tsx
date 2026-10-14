import { redirect } from "next/navigation";

import { getSession } from "@/auth/session";

export default async function EmployeeAdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await getSession();
  if (!session) redirect("/session-expired");
  if (session.record.employee.role !== "ADMIN") redirect("/access-denied");
  return children;
}
