import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { requireProjectAuthor } from "@/portals/manager/server";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  ProjectWorkspaceDocument,
  ProjectDetailDocument,
} from "@/shared/api/generated";
import { ProjectCreate } from "./project-create";
export async function ProjectList({
  overview = false,
  params = {},
}: {
  overview?: boolean;
  params?: { page?: string; search?: string };
}) {
  const { session, actor, root } = await requireProjectAuthor();
  const candidate = Number(params.page ?? 0);
  const page =
    Number.isInteger(candidate) && candidate >= 0 && candidate <= 10000
      ? candidate
      : 0;
  const search =
    typeof params.search === "string" ? params.search.slice(0, 100) : "";
  let data;
  try {
    data = (
      await administrationRequest(session, ProjectWorkspaceDocument, {
        page,
        search,
      })
    ).projectWorkspace;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    return (
      <>
        <h1>Projects</h1>
        <p role="alert">
          Project services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">PROJECT OWNERSHIP</p>
      <h1>{overview ? "Manager workspace" : "Projects"}</h1>
      <p className="project-intro">
        {actor.companyRoles[0] === "ADMIN"
          ? "Oversee company projects or create a project you will own."
          : "Manage projects you own. Your manager role does not grant access to unrelated projects."}
      </p>
      <Link className="project-action" href={`${root}/new`}>
        Create project
      </Link>
      <section className="project-panel">
        <h2>{overview ? "Your projects" : "Project directory"}</h2>
        <form method="get" action={root} className="project-search">
          <label>
            Search projects
            <input name="search" defaultValue={search} maxLength={100} />
          </label>
          <button>Search</button>
          <Link href={root}>Clear</Link>
        </form>
        {!data.projects.length ? (
          <p>
            No projects found. Create your first project when its objectives and
            agreed deadline are ready.
          </p>
        ) : (
          <ul className="project-list">
            {data.projects.map((p) => (
              <li key={p.id}>
                <h2>
                  <Link href={`${root}/${p.id}`}>{p.name}</Link>
                </h2>
                <p>
                  Current owner: {p.ownerName}. Original creator:{" "}
                  {p.creatorName}.
                </p>
                <p>
                  Original agreed deadline: {p.deadlineDate} · {p.timezone}
                </p>
              </li>
            ))}
          </ul>
        )}
        <nav className="project-pages" aria-label="Project pages">
          {page > 0 && (
            <Link
              href={`${root}?page=${page - 1}&search=${encodeURIComponent(search)}`}
            >
              Previous
            </Link>
          )}
          <span>Page {page + 1}</span>
          {data.hasMore && (
            <Link
              href={`${root}?page=${page + 1}&search=${encodeURIComponent(search)}`}
            >
              Next
            </Link>
          )}
        </nav>
      </section>
    </>
  );
}
export async function NewProject() {
  const { session, root } = await requireProjectAuthor();
  let data;
  try {
    data = (
      await administrationRequest(session, ProjectWorkspaceDocument, {
        page: 0,
        search: "",
      })
    ).projectWorkspace;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    return (
      <>
        <h1>Create project</h1>
        <p role="alert">Project services are unavailable.</p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">INITIAL PROJECT COMMITMENT</p>
      <h1>Create project</h1>
      <p className="project-intro">
        Define the objectives and review the initial agreed deadline. You will
        be recorded separately as original creator and initial project owner.
      </p>
      <Link href={root}>Back to projects</Link>
      {data.calendar ? (
        <ProjectCreate calendar={data.calendar} />
      ) : (
        <section className="project-panel">
          <h2>Company calendar required</h2>
          <p>
            Ask your administrator to publish the company working calendar
            before creating a project.
          </p>
          {root.startsWith("/admin") && (
            <Link href="/admin/calendar">Configure working calendar</Link>
          )}
        </section>
      )}
    </>
  );
}
export async function ProjectDetails({ id }: { id: string }) {
  const { session, root } = await requireProjectAuthor();
  let project;
  try {
    project = (
      await administrationRequest(session, ProjectDetailDocument, { id })
    ).project;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Project unavailable</h1>
        <p role="alert">Project services are unavailable.</p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">PROJECT DETAILS</p>
      <h1>{project.name}</h1>
      <Link href={`${root}/${id}/tasks`}>Work breakdown</Link>
      <Link href={`${root}/${id}/schedule`}>Task schedule</Link>
      <Link href={root}>Back to projects</Link>
      <p>
        <Link href={`${root}/${project.id}/members`}>Project membership</Link>
        {root !== "/projects" && (
          <>
            {" "}
            ·{" "}
            <Link href={`${root}/${project.id}/coordination`}>
              Project coordination
            </Link>
            {" · "}
            <Link href={`${root}/${project.id}/oversight`}>
              Delivery oversight
            </Link>
          </>
        )}
      </p>
      <section className="project-panel">
        <h2>Objectives</h2>
        <p className="project-objectives">{project.objectives}</p>
      </section>
      <section className="project-panel">
        <h2>Ownership and original commitment</h2>
        <dl className="project-snapshot">
          <div>
            <dt>Original creator</dt>
            <dd>{project.creatorName}</dd>
          </div>
          <div>
            <dt>Current owner</dt>
            <dd>{project.ownerName}</dd>
          </div>
          <div>
            <dt>Original agreed deadline</dt>
            <dd>
              {project.deadlineLocal} ({project.timezone})
            </dd>
          </div>
          <div>
            <dt>Original UTC deadline</dt>
            <dd>{project.approvedDeadline}</dd>
          </div>
          <div>
            <dt>Calendar commitment</dt>
            <dd>
              Version {project.calendarNumber} · timezone rules{" "}
              {project.tzdbVersion}
            </dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{project.createdAt}</dd>
          </div>
        </dl>
        <details>
          <summary>Ownership references</summary>
          <p>Original creator: {project.creatorId}</p>
          <p>Current owner: {project.ownerId}</p>
        </details>
        <p className="project-intro">
          The original commitment is retained. Open Delivery oversight to review
          approved revisions and available assessments. Manage appointments
          through Project membership.
        </p>
      </section>
    </>
  );
}
