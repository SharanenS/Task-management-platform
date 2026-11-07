import { Suspense } from "react";
import { getSession } from "@/auth/session";
import { ProjectDirectory } from "@/features/projects/project-directory";

export default async function ProjectsPage() {
  const session = await getSession();
  return (
    <Suspense>
      <ProjectDirectory role={session!.record.employee.role} />
    </Suspense>
  );
}
