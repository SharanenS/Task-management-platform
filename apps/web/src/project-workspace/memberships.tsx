import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  ProjectMembershipDocument,
  ProjectCandidatesDocument,
  ProjectWorkspaceDocument,
} from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import type { ProjectWorkspaceQuery } from "@/shared/api/generated";
import { MembershipEditor } from "./membership-editor";

export async function AssignedProjects() {
  const { session, actor, root } = await requireProjectViewer();
  if (actor.companyRoles[0] !== "EMPLOYEE") redirect(root);
  let projects: ProjectWorkspaceQuery["projectWorkspace"]["projects"];
  try {
    projects = (
      await administrationRequest(session, ProjectWorkspaceDocument, {
        page: 0,
        search: "",
      })
    ).projectWorkspace.projects;
  } catch (error) {
    if (error instanceof AccountDenied && actor.companyRoles[0] === "EMPLOYEE")
      projects = [];
    else
      return (
        <>
          <h1>Assigned projects</h1>
          <p role="alert">
            Project services are unavailable. Please try again later.
          </p>
        </>
      );
  }
  return (
    <>
      <h1>Assigned projects</h1>
      <p>
        Open a project to see your current appointment. A team-leader
        appointment in one project does not grant authority in another.
      </p>
      {projects.length ? (
        <ul className="project-list">
          {projects.map((project) => (
            <li key={project.id}>
              <h2>
                <Link href={`${root}/${project.id}/members`}>
                  {project.name}
                </Link>
              </h2>
              <Link href={`${root}/${project.id}/tasks`}>
                Open work breakdown
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p>
          No active project appointments. Contact your project owner if you need
          access.
        </p>
      )}
      <Link href="/auth/ready">Back to account</Link>
    </>
  );
}

export async function ProjectMembership({
  id,
  page = "0",
  search = "",
}: {
  id: string;
  page?: string;
  search?: string;
}) {
  const { session, root } = await requireProjectViewer();
  const pageNumber =
    /^\d{1,5}$/.test(page) && Number(page) <= 10000 ? Number(page) : 0;
  let workspace;
  let candidates;
  try {
    workspace = (
      await administrationRequest(session, ProjectMembershipDocument, { id })
    ).projectMembership;
    if (workspace.canManage)
      candidates = (
        await administrationRequest(session, ProjectCandidatesDocument, {
          id,
          page: pageNumber,
          search: search.slice(0, 100),
        })
      ).projectCandidates;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Project membership</h1>
        <p role="alert">
          Project membership services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  const title =
    workspace.responsibility === "LEADER"
      ? "Team leader"
      : ["OWNER", "ADMIN"].includes(workspace.responsibility)
        ? "Project management"
        : "Contributor";
  const path = `${root}/${id}/members`;
  return (
    <>
      <p className="project-eyebrow">PROJECT CONTEXT</p>
      <h1 className="project-title">{workspace.project.name}</h1>
      <Link href={`${root}/${id}/tasks`}>Work breakdown</Link>
      <Link href={root}>Back to projects</Link>
      <section className="project-panel">
        <h2>Your role: {title}</h2>
        <p className="project-objectives">{workspace.project.objectives}</p>
        <p>
          Current owner: {workspace.project.ownerName}. Original creator:{" "}
          {workspace.project.creatorName}.
        </p>
        <p>
          Original agreed deadline: {workspace.project.deadlineLocal} (
          {workspace.project.timezone}).
        </p>
        <p>Task planning and progress tools are not available yet.</p>
      </section>
      <section className="project-panel">
        <h2>Project appointments</h2>
        {workspace.members.length ? (
          <ul className="project-list">
            {workspace.members.map((member) => (
              <li key={member.id}>
                <strong>{member.displayName}</strong>
                <p>
                  {member.responsibility === "LEADER"
                    ? "Team leader"
                    : "Contributor"}{" "}
                  · {member.active ? "Appointed" : "Removed"}
                </p>
                {member.duties !== null && (
                  <p className="project-objectives">
                    {member.duties || "No detailed responsibilities recorded."}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>No employees have been appointed.</p>
        )}
      </section>
      {workspace.canManage && candidates && (
        <>
          <section className="project-panel">
            <h2>Find eligible employees</h2>
            <form className="project-search" action={path}>
              <label>
                Employee name
                <input name="search" defaultValue={search} maxLength={100} />
              </label>
              <button>Search employees</button>
              <Link href={path}>Clear</Link>
            </form>
            <nav className="project-pages" aria-label="Eligible employee pages">
              {pageNumber > 0 && (
                <Link
                  href={`${path}?page=${pageNumber - 1}&search=${encodeURIComponent(search)}`}
                >
                  Previous
                </Link>
              )}
              <span>Page {pageNumber + 1}</span>
              {candidates.hasMore && (
                <Link
                  href={`${path}?page=${pageNumber + 1}&search=${encodeURIComponent(search)}`}
                >
                  Next
                </Link>
              )}
            </nav>
          </section>
          <MembershipEditor
            workspace={workspace}
            candidates={candidates.candidates}
          />
          <section className="project-panel">
            <h2>Recent membership history</h2>
            <p>
              The most recent 50 changes are shown. Earlier records are
              retained.
            </p>
            {workspace.history.length ? (
              <ul className="project-list">
                {workspace.history.map((change) => (
                  <li key={change.id}>
                    <p>
                      {change.action === "remove"
                        ? "Appointment removed"
                        : "Appointment saved"}{" "}
                      · {change.createdAt} · Project version{" "}
                      {change.projectVersion}
                    </p>
                    <details>
                      <summary>Change details</summary>
                      <p>
                        Actor reference: {change.actorId}. Employee account
                        reference: {change.targetId}.
                      </p>
                      <pre className="project-objectives">{change.before}</pre>
                      <pre className="project-objectives">{change.after}</pre>
                    </details>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No membership changes recorded.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
