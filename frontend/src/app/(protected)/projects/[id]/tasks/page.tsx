import { TaskDirectory } from "@/features/tasks/task-directory";

export default async function TasksPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TaskDirectory projectId={id} />;
}
