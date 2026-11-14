import { getSession } from "@/auth/session";
import { TaskDetail } from "@/features/tasks/task-detail";

export default async function TaskPage({
  params,
}: {
  params: Promise<{ id: string; taskId: string }>;
}) {
  const [{ id, taskId }, session] = await Promise.all([params, getSession()]);
  return (
    <TaskDetail
      projectId={id}
      taskId={taskId}
      employeeId={session!.record.employee.id}
      applicationRole={session!.record.employee.role}
    />
  );
}
