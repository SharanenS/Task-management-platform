import { ProjectReviews } from "@/project-workspace/reviews";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  return (
    <ProjectReviews id={(await params).id} page={(await searchParams).page} />
  );
}
