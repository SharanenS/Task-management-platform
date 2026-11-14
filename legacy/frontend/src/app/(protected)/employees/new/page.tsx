import { ProvisionEmployeeForm } from "@/features/employees/provision-employee-form";

export default function NewEmployeePage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold tracking-[.14em] text-primary uppercase">
          Employee administration
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Provision employee
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Create a protected Keycloak identity and its linked application
          profile.
        </p>
      </div>
      <ProvisionEmployeeForm />
    </div>
  );
}
