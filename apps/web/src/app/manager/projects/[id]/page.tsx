import { ProjectDetails } from "@/project-workspace/projects";
export default async function Details({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ProjectDetails id={(await params).id} />;
}
