import { ProjectCoordination } from "@/project-workspace/coordination";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  return <ProjectCoordination id={(await params).id} {...await searchParams} />;
}
