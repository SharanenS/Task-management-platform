import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import { ProjectReviewsDocument } from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import { ReviewEditor } from "./review-editor";
import { scheduleTime } from "./schedule-time";

function SubmissionSnapshot({ value }: { value: string }) {
  let record: Record<string, unknown>;
  try {
    record = JSON.parse(value);
    if (!record || typeof record !== "object" || Array.isArray(record))
      throw new Error();
  } catch {
    return <p>Submitted details are unavailable.</p>;
  }
  return (
    <details>
      <summary>Details recorded at submission</summary>
      {typeof record.instructions === "string" && (
        <p>Instructions: {record.instructions}</p>
      )}
      {typeof record.acceptance_criteria === "string" && (
        <p>Acceptance criteria: {record.acceptance_criteria}</p>
      )}
      {typeof record.progress === "number" && (
        <p>Reported progress: {record.progress}%</p>
      )}
      <p>
        Blocker:{" "}
        {typeof record.blocker === "string" ? record.blocker : "None recorded"}
      </p>
    </details>
  );
}

export async function ProjectReviews({
  id,
  page = "0",
}: {
  id: string;
  page?: string;
}) {
  const { session, root } = await requireProjectViewer();
  const current =
    /^\d{1,5}$/.test(page) && Number(page) <= 10000 ? Number(page) : 0;
  let workspace;
  try {
    workspace = (
      await administrationRequest(session, ProjectReviewsDocument, {
        id,
        page: current,
      })
    ).projectReviews;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Completion reviews</h1>
        <p role="alert">
          Review services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">PROJECT COMPLETION</p>
      <h1>{workspace.project.name}</h1>
      <h2>Completion reviews and my work</h2>
      <p>
        Submission and approval are separate. Planned dates remain unchanged
        when work starts. An awaiting-review prerequisite is not completed.
      </p>
      <p>
        <Link href={`${root}/${id}/tasks`}>Work breakdown</Link>
        {" · "}
        <Link href={`${root}/${id}/schedule`}>Task schedule</Link>
      </p>
      {workspace.fallbackId && (
        <p role="status">
          Review-scoped owner/administrator fallback is active. Decisions retain
          its absence record.
        </p>
      )}
      {!workspace.canReview && !workspace.isLeader && (
        <p>
          Review decisions require current leadership or authorized fallback.
        </p>
      )}
      <p>
        Times use the project timezone: {workspace.project.timezone}. The latest
        25 submissions per task are shown; earlier records remain retained.
      </p>
      {!workspace.tasks.length && (
        <p>No accessible work or submissions on this page.</p>
      )}
      {workspace.tasks.map((task) => (
        <article className="project-panel" key={task.id}>
          <h3>{task.title}</h3>
          <p>
            {task.status.replaceAll("_", " ")} · {task.assigneeName}
          </p>
          <h4>Acceptance criteria</h4>
          <p className="project-objectives">{task.acceptanceCriteria}</p>
          <h4>Instructions</h4>
          <p className="project-objectives">{task.instructions}</p>
          <dl className="project-snapshot">
            <div>
              <dt>
                {task.status === "COMPLETED"
                  ? "Last reported progress"
                  : "Reported progress"}
              </dt>
              <dd>{task.progress}%</dd>
            </div>
            <div>
              <dt>
                {task.status === "COMPLETED"
                  ? "Last reported blocker"
                  : "Current blocker"}
              </dt>
              <dd>{task.blocker || "None recorded"}</dd>
            </div>
            <div>
              <dt>Actually started</dt>
              <dd>
                {task.startedAt
                  ? scheduleTime(task.startedAt, workspace.project.timezone)
                  : "Not started"}
              </dd>
            </div>
            <div>
              <dt>Approved completion</dt>
              <dd>
                {task.completedAt
                  ? scheduleTime(task.completedAt, workspace.project.timezone)
                  : "Not completed"}
              </dd>
            </div>
          </dl>
          {workspace.isLeader && task.own && task.canAct && (
            <>
              {task.status === "PENDING" && (
                <>
                  <p>
                    Starting validates the working-date and prerequisite gates
                    on the server.
                  </p>
                  <ReviewEditor
                    workspace={workspace}
                    task={task}
                    action="START"
                  />
                </>
              )}
              {task.status === "IN_PROGRESS" && (
                <>
                  <ReviewEditor
                    workspace={workspace}
                    task={task}
                    action="PROGRESS"
                  />
                  <ReviewEditor
                    workspace={workspace}
                    task={task}
                    action="SUBMIT"
                  />
                </>
              )}
            </>
          )}
          {task.workHistory.length > 0 && (
            <details>
              <summary>Work update history</summary>
              <p>
                The latest 25 updates are shown; earlier records remain
                retained.
              </p>
              {task.workHistory.map((update) => (
                <section key={update.id}>
                  <h5>
                    {(
                      {
                        START: "Work started",
                        PROGRESS: "Progress recorded",
                        SUBMIT: "Submitted for review",
                      } as Record<string, string>
                    )[update.action] || "Work update"}
                  </h5>
                  <p>
                    {update.actorName} ·{" "}
                    {scheduleTime(update.createdAt, workspace.project.timezone)}
                  </p>
                  <p>{update.note}</p>
                  <p>
                    Reported progress: {update.progress}% · Blocker:{" "}
                    {update.blocker || "None recorded"}
                  </p>
                </section>
              ))}
            </details>
          )}
          <h4>Submissions and decisions</h4>
          {!task.submissions.length && <p>No completion submission yet.</p>}
          {task.submissions.map((submission) => (
            <section key={submission.id} className="oversight-record">
              <h5>
                {submission.pending ? "Awaiting review" : "Reviewed submission"}{" "}
                · Version {submission.version}
              </h5>
              <p>
                {submission.submitterName} ·{" "}
                {scheduleTime(
                  submission.submittedAt,
                  workspace.project.timezone,
                )}
              </p>
              <p className="project-objectives">{submission.summary}</p>
              <SubmissionSnapshot value={submission.snapshot} />
              {submission.decision && (
                <>
                  <p>
                    {submission.decision.outcome === "APPROVE"
                      ? "Completion approved"
                      : "Returned for changes"}{" "}
                    by {submission.decision.actorName} ·{" "}
                    {scheduleTime(
                      submission.decision.decidedAt,
                      workspace.project.timezone,
                    )}
                  </p>
                  <p>{submission.decision.feedback}</p>
                  <p>
                    {submission.decision.selfApproval
                      ? "Explicit self-approval"
                      : submission.decision.fallbackId
                        ? "Authorized absence fallback review"
                        : "Leader review"}
                  </p>
                </>
              )}
              {submission.pending &&
                task.canReview &&
                task.status === "AWAITING_REVIEW" && (
                  <ReviewEditor
                    workspace={workspace}
                    task={task}
                    action="DECIDE"
                    submissionId={submission.id}
                  />
                )}
            </section>
          ))}
        </article>
      ))}
      <nav aria-label="Review pages">
        {current > 0 && (
          <Link href={`${root}/${id}/reviews?page=${current - 1}`}>
            Previous work
          </Link>
        )}
        <span> Page {current + 1} </span>
        {workspace.hasMore && (
          <Link href={`${root}/${id}/reviews?page=${current + 1}`}>
            Next work
          </Link>
        )}
      </nav>
    </>
  );
}
