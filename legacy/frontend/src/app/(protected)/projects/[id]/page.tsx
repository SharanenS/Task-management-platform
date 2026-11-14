import { getSession } from "@/auth/session";
import { ProjectDetail } from "@/features/projects/project-detail";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [{ id }, session] = await Promise.all([params, getSession()]);
  return (
    <ProjectDetail
      id={id}
      employeeId={session!.record.employee.id}
      applicationRole={session!.record.employee.role}
    />
  );
}
