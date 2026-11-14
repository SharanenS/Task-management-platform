import { getSession } from "@/auth/session";
import { WorkspaceDashboard } from "@/features/dashboard/workspace-dashboard";

export default async function DashboardPage() {
  const session = await getSession();
  return <WorkspaceDashboard employee={session!.record.employee} />;
}
