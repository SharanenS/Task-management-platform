import { ProjectSchedule } from "@/project-workspace/scheduling";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProjectSchedule id={id} />;
}
