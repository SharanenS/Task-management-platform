import { OwnerOversight } from "@/project-workspace/owner-oversight";
export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string }>;
}) {
  return <OwnerOversight id={(await params).id} {...await searchParams} />;
}
