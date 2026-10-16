import { JobDetail } from "@/features/jobs/job-detail";

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <JobDetail id={(await params).id} />;
}
