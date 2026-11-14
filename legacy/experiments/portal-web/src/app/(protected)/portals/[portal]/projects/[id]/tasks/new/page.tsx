import { CreateTaskForm } from "@/features/tasks/create-task-form";

export default async function NewTaskPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CreateTaskForm projectId={id} />;
}
