import { Suspense } from "react";
import { requirePortalSession as getSession } from "@/features/portals/server-session";
import { ProjectDirectory } from "@/features/projects/project-directory";

export default async function ProjectsPage() {
  const session = await getSession();
  return (
    <Suspense>
      <ProjectDirectory role={session!.record.employee.role} />
    </Suspense>
  );
}
