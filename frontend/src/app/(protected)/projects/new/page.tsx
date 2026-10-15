import { redirect } from "next/navigation";

import { getSession } from "@/auth/session";
import { CreateProjectForm } from "@/features/projects/create-project-form";

export default async function NewProjectPage() {
  const session = await getSession();
  if (!session || session.record.employee.role === "MEMBER")
    redirect("/access-denied");
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-[.14em] text-primary uppercase">
          Project management
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Create project
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Create a draft project with an immutable key.
        </p>
      </div>
      <CreateProjectForm />
    </div>
  );
}
