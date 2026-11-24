import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  ProjectTasksDocument,
  TaskCandidatesDocument,
} from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import { TaskEditor } from "./task-editor";

const statusLabels: Record<string, string> = {
  PENDING: "Pending",
  IN_PROGRESS: "In progress",
  AWAITING_REVIEW: "Awaiting review",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};
const actionLabels: Record<string, string> = {
  CREATE: "Task created",
  EDIT: "Instructions updated",
  ASSIGN: "Task reassigned",
};

function HistorySnapshot({ value, label }: { value: string; label: string }) {
  let record: Record<string, unknown>;
  try {
    const candidate = JSON.parse(value);
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate))
      throw new Error();
    record = candidate;
  } catch {
    return <p>Historical detail is unavailable.</p>;
  }
  return (
    <div>
      <h5>{label}</h5>
      {typeof record.title === "string" ? (
        <>
          <p>Title: {record.title}</p>
          <p>
            Assignee:{" "}
            {typeof record.assignee_name === "string"
              ? record.assignee_name
              : "Recorded assignment"}
          </p>
          {typeof record.instructions === "string" && (
            <p className="project-objectives">
              Instructions: {record.instructions}
            </p>
          )}
          {typeof record.acceptance_criteria === "string" && (
            <p className="project-objectives">
              Acceptance criteria: {record.acceptance_criteria}
            </p>
          )}
        </>
      ) : (
        <p>No previous task.</p>
      )}
    </div>
  );
}

export async function ProjectTasks({
  id,
  page = "0",
  candidatePage = "0",
}: {
  id: string;
  page?: string;
  candidatePage?: string;
}) {
  const { session, root } = await requireProjectViewer();
  function number(value: string) {
    return /^\d{1,5}$/.test(value) && Number(value) <= 10000
      ? Number(value)
      : 0;
  }
  const currentPage = number(page);
  const currentCandidates = number(candidatePage);
  let workspace;
  let candidates;
  try {
    workspace = (
      await administrationRequest(session, ProjectTasksDocument, {
        id,
        page: currentPage,
      })
    ).projectTasks;
    candidates = workspace.canPlan
      ? (
          await administrationRequest(session, TaskCandidatesDocument, {
            id,
            page: currentCandidates,
          })
        ).taskCandidates
      : { candidates: [], hasMore: false };
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Project work breakdown</h1>
        <p role="alert">
          Task services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  const url = `${root}/${id}/tasks`;
  return (
    <>
      <p className="project-eyebrow">
        {workspace.canPlan ? "TEAM LEADER WORKSPACE" : "PROJECT TASKS"}
      </p>
      <h1>{workspace.project.name}</h1>
      <p>
        Work breakdown and clear ownership. Leadership applies only to this
        project.
      </p>
      <Link href={`${root}/${id}/members`}>Project membership</Link>
      {workspace.canPlan && (
        <section className="project-panel">
          <h2>Plan the work</h2>
          <p>
            Assign one active employee member to each task. You may assign work
            to yourself. Changes retain the previous assignment and require a
            reason.
          </p>
          {!candidates.candidates.length && (
            <p>
              No eligible members on this page. Ask the owner to review project
              membership.
            </p>
          )}
          <TaskEditor
            workspace={workspace}
            candidates={candidates.candidates}
          />
          <nav aria-label="Assignee pages">
            {currentCandidates > 0 && (
              <Link
                href={`${url}?page=${currentPage}&candidatePage=${currentCandidates - 1}`}
              >
                Previous members
              </Link>
            )}
            <span> Member page {currentCandidates + 1} </span>
            {candidates.hasMore && (
              <Link
                href={`${url}?page=${currentPage}&candidatePage=${currentCandidates + 1}`}
              >
                Next members
              </Link>
            )}
          </nav>
        </section>
      )}
      <section className="project-panel">
        <h2>Tasks</h2>
        {!workspace.tasks.length && (
          <p>No tasks have been created for this project.</p>
        )}
        {workspace.tasks.map((task) => (
          <article key={task.id} className="oversight-record">
            <h3>{task.title}</h3>
            <p>
              {statusLabels[task.status] ?? task.status} ·{" "}
              {task.assigneeName ?? "No active assignment"}
            </p>
            {task.details ? (
              <>
                <h4>Instructions</h4>
                <p className="project-objectives">
                  {task.details.instructions}
                </p>
                <h4>Acceptance criteria</h4>
                <p className="project-objectives">
                  {task.details.acceptanceCriteria}
                </p>
                <p>Assigned: {task.details.assignedAt}</p>
                {workspace.canPlan && task.status === "PENDING" && (
                  <details>
                    <summary>Planning changes</summary>
                    <TaskEditor
                      workspace={workspace}
                      candidates={candidates.candidates}
                      task={task}
                      action="EDIT"
                    />
                    <TaskEditor
                      workspace={workspace}
                      candidates={candidates.candidates}
                      task={task}
                      action="ASSIGN"
                    />
                  </details>
                )}
                {task.details.history.length > 0 && (
                  <details>
                    <summary>Planning and reassignment history</summary>
                    <p>
                      The most recent 50 changes are shown. Earlier records are
                      retained.
                    </p>
                    {task.details.history.map((change) => (
                      <section key={change.id}>
                        <h4>
                          {actionLabels[change.action] ?? change.action} ·
                          Version {change.version}
                        </h4>
                        <p>
                          {change.actorName} · {change.createdAt}
                        </p>
                        <p>{change.reason}</p>
                        <HistorySnapshot label="Before" value={change.before} />
                        <HistorySnapshot label="After" value={change.after} />
                      </section>
                    ))}
                  </details>
                )}
              </>
            ) : (
              <p>
                Private task details are available to its current assignee and
                authorized supervisors.
              </p>
            )}
          </article>
        ))}
        <nav aria-label="Task pages">
          {currentPage > 0 && (
            <Link
              href={`${url}?page=${currentPage - 1}&candidatePage=${currentCandidates}`}
            >
              Previous tasks
            </Link>
          )}
          <span> Page {currentPage + 1} </span>
          {workspace.hasMore && (
            <Link
              href={`${url}?page=${currentPage + 1}&candidatePage=${currentCandidates}`}
            >
              Next tasks
            </Link>
          )}
        </nav>
      </section>
    </>
  );
}
