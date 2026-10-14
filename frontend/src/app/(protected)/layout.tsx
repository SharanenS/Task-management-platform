import { redirect } from "next/navigation";

import { getSession } from "@/auth/session";
import { AppShell } from "@/components/layout/app-shell";

export default async function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await getSession();
  if (!session) redirect("/session-expired");
  return <AppShell user={session.record.employee}>{children}</AppShell>;
}
