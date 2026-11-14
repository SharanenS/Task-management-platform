import { PortalOverview } from "@/features/portals/portal-overview";
import { requirePortalSession } from "@/features/portals/server-session";

export default async function PortalPage() {
  const session = await requirePortalSession();
  return <PortalOverview employee={session.record.employee} />;
}
