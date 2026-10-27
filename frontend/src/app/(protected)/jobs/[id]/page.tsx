import { JobDetail } from "@/features/jobs/job-detail";
import { getSession } from "@/auth/session";

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await getSession();
  return (
    <JobDetail
      id={(await params).id}
      isAdmin={session?.record.employee.role === "ADMIN"}
    />
  );
}
