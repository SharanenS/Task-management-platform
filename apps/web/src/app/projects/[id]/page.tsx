import { ProjectMembership } from "@/project-workspace/memberships";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ProjectMembership id={(await params).id} />;
}
