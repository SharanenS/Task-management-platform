import { getSession } from "@/auth/session";
import { ProjectDirectory } from "@/features/projects/project-directory";

export default async function ProjectsPage() {
  const session = await getSession();
  return <ProjectDirectory role={session!.record.employee.role} />;
}
