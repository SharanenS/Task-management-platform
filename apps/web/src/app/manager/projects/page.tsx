import { ProjectList } from "@/project-workspace/projects";
export default async function Projects({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; search?: string }>;
}) {
  return <ProjectList params={await searchParams} />;
}
