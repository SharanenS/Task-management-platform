import { ProjectTasks } from "@/project-workspace/tasks";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string; candidatePage?: string }>;
}) {
  return <ProjectTasks id={(await params).id} {...await searchParams} />;
}
