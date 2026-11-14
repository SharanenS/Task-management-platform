import { WorkflowDetail } from "@/features/workflows/workflow-detail";
export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <WorkflowDetail id={id} />;
}
