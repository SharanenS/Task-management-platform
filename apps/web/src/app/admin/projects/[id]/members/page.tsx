import { ProjectMembership } from "@/project-workspace/memberships";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string; search?: string }>;
}) {
  return <ProjectMembership id={(await params).id} {...await searchParams} />;
}
