import { redirect } from "next/navigation";
import { requirePortalSession } from "@/features/portals/server-session";
import { portalHome } from "@/features/portals/portal-policy";

export default async function HomePage() {
  const session = await requirePortalSession();
  redirect(portalHome(session.record.employee.role));
}
