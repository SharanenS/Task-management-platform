import { redirect } from "next/navigation";
import { PortalShell } from "@/components/portal-shell/portal-shell";
import { requirePortalSession } from "@/features/portals/server-session";
import { canOpenPortal } from "@/features/portals/portal-policy";

export default async function PortalLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ portal: string }>;
}) {
  const [{ portal }, session] = await Promise.all([
    params,
    requirePortalSession(),
  ]);
  if (!canOpenPortal(session.record.employee.role, portal))
    redirect("/access-denied");
  return <PortalShell user={session.record.employee}>{children}</PortalShell>;
}
