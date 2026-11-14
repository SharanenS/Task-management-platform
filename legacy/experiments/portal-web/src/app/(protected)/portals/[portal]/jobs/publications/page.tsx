import { redirect } from "next/navigation";

import { requirePortalSession as getSession } from "@/features/portals/server-session";
import { PublicationDirectory } from "@/features/jobs/publication-directory";

export default async function PublicationsPage() {
  const session = await getSession();
  if (!session || session.record.employee.role !== "ADMIN")
    redirect("/access-denied");
  return <PublicationDirectory />;
}
