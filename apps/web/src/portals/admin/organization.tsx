import Link from "next/link";
import { randomUUID } from "node:crypto";
import { redirect } from "next/navigation";
import { requireAdministrator } from "./server";
import { administrationRequest } from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  OrganizationWorkspaceDocument,
  type OrganizationWorkspaceQuery,
} from "@/shared/api/generated";

export function Hidden({
  name,
  value,
}: {
  name: string;
  value: string | number;
}) {
  return <input type="hidden" name={name} value={value} />;
}
function Command({
  action,
  destination,
  children,
}: {
  action: string;
  destination: string;
  children: React.ReactNode;
}) {
  return (
    <form
      method="post"
      action="/admin/organization/command"
      className="people-form"
    >
      <Hidden name="requestId" value={randomUUID()} />
      <Hidden name="action" value={action} />
      <Hidden name="destination" value={destination} />
      {children}
    </form>
  );
}
function Confirm() {
  return (
    <label className="accounts-confirm">
      <input type="checkbox" name="confirm" value="yes" required /> I confirm
      this change
    </label>
  );
}
const notices: Record<string, string> = {
  complete: "The change was saved and recorded in history.",
  rejected:
    "The change was rejected. Refresh and check the current record. Names must be unique within each structure type; reporting must not contain cycles. Assigned structures cannot be archived. Account links require an active, verified identity and cannot replace an existing link.",
  confirmation: "Confirm the change before submitting.",
  unavailable:
    "People services are unavailable. Refresh to check the recorded outcome before trying again.",
};
function EmploymentFields({
  person,
  data,
}: {
  person?: OrganizationWorkspaceQuery["organizationWorkspace"]["employees"][number];
  data: OrganizationWorkspaceQuery["organizationWorkspace"];
}) {
  const units = [
    { kind: "DEPARTMENT", label: "Department", rows: data.departments },
    { kind: "JOB_TITLE", label: "Job title", rows: data.jobTitles },
  ];
  return (
    <>
      <label>
        Full name
        <input
          name="name"
          required
          maxLength={150}
          defaultValue={person?.displayName}
          autoComplete="off"
        />
      </label>
      {units.map((unit) => (
        <label key={unit.kind}>
          {unit.label}
          <select
            aria-label={unit.label}
            name={unit.kind === "DEPARTMENT" ? "departmentId" : "jobTitleId"}
            defaultValue={
              (unit.kind === "DEPARTMENT"
                ? person?.departmentId
                : person?.jobTitleId) ?? ""
            }
          >
            <option value="">Not assigned</option>
            {unit.rows
              .filter(
                (row) =>
                  row.active ||
                  row.id ===
                    (unit.kind === "DEPARTMENT"
                      ? person?.departmentId
                      : person?.jobTitleId),
              )
              .map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                  {!row.active ? " (archived; choose an active value)" : ""}
                </option>
              ))}
          </select>
        </label>
      ))}
      <label>
        Reports to
        <select
          aria-label="Reports to"
          name="managerId"
          defaultValue={person?.managerId ?? ""}
        >
          <option value="">No reporting manager</option>
          {data.managerOptions
            .filter((row) => row.id !== person?.id)
            .map((row) => (
              <option key={row.id} value={row.id}>
                {row.displayName}
              </option>
            ))}
        </select>
      </label>
    </>
  );
}

export async function PeopleWorkspace({
  employees,
  params,
}: {
  employees: boolean;
  params: { page?: string; search?: string; notice?: string };
}) {
  const { session } = await requireAdministrator();
  const number = Number(params.page ?? 0);
  const page =
    Number.isInteger(number) && number >= 0 && number <= 10000 ? number : 0;
  const search = (params.search ?? "").slice(0, 100);
  let data: OrganizationWorkspaceQuery["organizationWorkspace"];
  try {
    data = (
      await administrationRequest(session, OrganizationWorkspaceDocument, {
        page,
        search,
      })
    ).organizationWorkspace;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    return (
      <>
        <h1>{employees ? "Employees" : "Company structure"}</h1>
        <p role="alert">
          People services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  const destination = employees ? "employees" : "organization";
  const units = [
    { kind: "DEPARTMENT", label: "Department", rows: data.departments },
    { kind: "JOB_TITLE", label: "Job title", rows: data.jobTitles },
  ];
  return (
    <>
      <p className="admin-eyebrow">PEOPLE & ORGANIZATION</p>
      <h1>{employees ? "Employees" : "Company structure"}</h1>
      <p className="admin-intro">
        {employees
          ? "Build your directory before creating login accounts. Titles and reporting relationships do not grant company roles or project access."
          : "Maintain departments and job titles for the shared employee directory. Archive unused entries to preserve their history."}
      </p>
      {params.notice && notices[params.notice] && (
        <p role="status" className="accounts-notice">
          {notices[params.notice]}
        </p>
      )}
      {!employees ? (
        <div className="people-grid">
          {units.map((unit) => (
            <section key={unit.kind} className="accounts-panel">
              <h2>
                {unit.label === "Department" ? "Departments" : "Job titles"}
              </h2>
              <Command action="UNIT_CREATE" destination={destination}>
                <Hidden name="kind" value={unit.kind} />
                <label>
                  {unit.label} name
                  <input name="name" required maxLength={100} />
                </label>
                <button className="admin-primary-button">
                  Add {unit.label.toLowerCase()}
                </button>
              </Command>
              {!unit.rows.length && (
                <p>No {unit.label.toLowerCase()} records yet.</p>
              )}
              {unit.rows.map((row) => (
                <details key={row.id} className="people-record">
                  <summary>
                    {row.name} · {row.active ? "Active" : "Archived"}
                  </summary>
                  <Command action="UNIT_UPDATE" destination={destination}>
                    <Hidden name="kind" value={unit.kind} />
                    <Hidden name="entityId" value={row.id} />
                    <Hidden name="version" value={row.version} />
                    <label>
                      Name
                      <input
                        name="name"
                        required
                        maxLength={100}
                        defaultValue={row.name}
                      />
                    </label>
                    <label>
                      Status
                      <select name="active" defaultValue={String(row.active)}>
                        <option value="true">Active</option>
                        <option value="false">Archived</option>
                      </select>
                    </label>
                    <Confirm />
                    <button>Save {unit.label.toLowerCase()}</button>
                  </Command>
                </details>
              ))}
            </section>
          ))}
        </div>
      ) : (
        <>
          <section className="accounts-panel">
            <h2>Add an employee</h2>
            <p>
              A directory record has no login or authorization until linked to a
              verified account.
            </p>
            <Command action="EMPLOYEE_CREATE" destination={destination}>
              <EmploymentFields data={data} />
              <button className="admin-primary-button">Add employee</button>
            </Command>
          </section>
          <section className="accounts-panel">
            <h2>Employee directory</h2>
            <form method="get" className="people-search">
              <label>
                Search employees
                <input name="search" maxLength={100} defaultValue={search} />
              </label>
              <button>Search</button>
              <Link href="/admin/employees">Clear</Link>
            </form>
            {!data.employees.length && <p>No employees found.</p>}
            {data.employees.map((person) => (
              <details key={person.id} className="people-record">
                <summary>
                  {person.displayName} ·{" "}
                  {person.accountId
                    ? `${person.companyRole || "No valid role"} account`
                    : "No login account"}
                  {!person.active ? " · Inactive" : ""}
                </summary>
                <Command action="EMPLOYEE_UPDATE" destination={destination}>
                  <Hidden name="entityId" value={person.id} />
                  <Hidden name="version" value={person.version} />
                  <EmploymentFields data={data} person={person} />
                  <button>Save employee</button>
                </Command>
                <p>
                  Company role: {person.companyRole || "Not assigned"}.
                  Employment changes keep account permissions intact.
                </p>
                {!person.accountId && person.active && (
                  <>
                    <Link
                      href={`/admin/accounts?employeeId=${encodeURIComponent(person.id)}`}
                    >
                      Create login for this employee
                    </Link>
                    {data.availableAccounts.length > 0 && (
                      <Command action="ACCOUNT_LINK" destination={destination}>
                        <Hidden name="entityId" value={person.id} />
                        <Hidden name="version" value={person.version} />
                        <label>
                          Existing account
                          <select
                            aria-label="Existing account"
                            name="accountId"
                            required
                          >
                            <option value="">Choose verified account</option>
                            {data.availableAccounts.map((account) => (
                              <option key={account.id} value={account.id}>
                                {account.id} · {account.companyRole}
                              </option>
                            ))}
                          </select>
                        </label>
                        <p>
                          Verify the exact account identifier before linking.
                          This association is permanent through this screen.
                        </p>
                        <Confirm />
                        <button>Link account</button>
                      </Command>
                    )}
                  </>
                )}
              </details>
            ))}
            <nav aria-label="Employee pages">
              {page > 0 && (
                <Link
                  href={`/admin/employees?page=${page - 1}&search=${encodeURIComponent(search)}`}
                >
                  Previous
                </Link>
              )}
              <span>Page {page + 1}</span>
              {data.hasMore && (
                <Link
                  href={`/admin/employees?page=${page + 1}&search=${encodeURIComponent(search)}`}
                >
                  Next
                </Link>
              )}
            </nav>
          </section>
        </>
      )}
      <section className="accounts-panel">
        <h2>Recent organization changes</h2>
        {!data.history.length ? (
          <p>No changes recorded yet.</p>
        ) : (
          <ul className="people-history">
            {data.history.map((item) => (
              <li key={item.id}>
                <strong>{item.entityName}</strong> ·{" "}
                {item.action.toLowerCase().replaceAll("_", " ")}
                <span>
                  {item.actorName} ·{" "}
                  <time dateTime={item.createdAt}>
                    {new Date(item.createdAt).toLocaleString("en-GB", {
                      timeZone: "UTC",
                    })}{" "}
                    UTC
                  </time>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
