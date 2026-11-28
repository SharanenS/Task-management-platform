import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import { ProjectScheduleDocument } from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import { ScheduleEditor } from "./schedule-editor";
import { scheduleTime as date } from "./schedule-time";
import "./schedule.css";
const readiness: Record<string, string> = {
  READY: "Prerequisites complete; planned start reached",
  WAITING_FOR_DATE: "Waiting for planned start",
  WAITING_FOR_PREREQUISITES: "Waiting for prerequisite approval/completion",
  UNASSESSED: "Readiness cannot be assessed",
};
const issues: Record<string, string> = {
  CANCELLED: "Cancelled task",
  MISSING_PLAN: "Start and duration are not set",
  ASSIGNEE_INELIGIBLE: "Assignee is no longer eligible",
  PREREQUISITE_UNASSESSED: "A prerequisite has no reliable schedule",
  INCOMPLETE_PAST_FINISH:
    "Unfinished past scheduled finish; forecast needs reassessment",
};
export async function ProjectSchedule({ id }: { id: string }) {
  const { session, root } = await requireProjectViewer();
  let workspace;
  try {
    workspace = (
      await administrationRequest(session, ProjectScheduleDocument, { id })
    ).projectSchedule;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Project schedule</h1>
        <p role="alert">
          Scheduling is temporarily unavailable. No dates have been guessed.
        </p>
      </>
    );
  }
  const labels = new Map(workspace.tasks.map((t) => [t.plan.id, t.title]));
  const scheduled = workspace.tasks.filter(
    (t) => t.plan.startsAt && t.plan.dueAt,
  );
  const first = scheduled.length
    ? Math.min(...scheduled.map((t) => new Date(t.plan.startsAt!).valueOf()))
    : 0;
  const last = scheduled.length
    ? Math.max(...scheduled.map((t) => new Date(t.plan.dueAt!).valueOf()))
    : 1;
  const span = Math.max(1, last - first);

  return (
    <>
      <p className="project-eyebrow">PROJECT SCHEDULE</p>
      <h1>{workspace.project.name} schedule</h1>
      <Link href={`${root}/${id}/tasks`}>Work breakdown</Link> ·{" "}
      <Link href={`${root}/${id}`}>Project details</Link>
      <p>
        Calendar version {workspace.calendarNumber} · {workspace.timezone}. A
        working start counts as day one; dependent work hands off the next
        working day.
      </p>
      {workspace.state && (
        <section className="schedule-card" aria-label="Project forecast">
          <h2>Dependency forecast</h2>
          <p>
            {workspace.forecastAt
              ? date(workspace.forecastAt, workspace.timezone)
              : "Unassessed - a reliable completion date is not available."}
          </p>
          <p>
            Original project commitment:{" "}
            {date(workspace.project.approvedDeadline, workspace.timezone)}.
            Current approved commitment:{" "}
            {date(workspace.currentDeadline, workspace.timezone)}.
          </p>
          <p>
            Dates are schedule windows, not hourly effort or a capacity
            guarantee. Starting work will not reset commitments.
          </p>
          {workspace.overlaps.length > 0 && (
            <div role="status">
              <h3>Workload warnings</h3>
              <ul>
                {workspace.overlaps.map((pair, i) => (
                  <li key={i}>
                    {labels.get(pair.taskId)} overlaps{" "}
                    {labels.get(pair.otherTaskId)} for the same employee. Review
                    their workload.
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
      <section aria-labelledby="timeline-heading">
        <h2 id="timeline-heading">Task timeline</h2>
        {!workspace.tasks.length && (
          <p>
            No private task schedules are available for your current assignment.
          </p>
        )}
        <ol className="schedule-timeline">
          {workspace.tasks.map((task) => (
            <li key={task.plan.id} className="schedule-card">
              <h3>{task.title}</h3>
              <p>Status: {task.status.replaceAll("_", " ").toLowerCase()}</p>
              {task.plan.startsAt && task.plan.dueAt && (
                <div className="schedule-window" aria-hidden="true">
                  <span
                    style={{
                      marginLeft: `${(100 * (new Date(task.plan.startsAt).valueOf() - first)) / span}%`,
                      width: `${(100 * (new Date(task.plan.dueAt).valueOf() - new Date(task.plan.startsAt).valueOf())) / span}%`,
                    }}
                  />
                </div>
              )}

              <p>{task.assigneeName ?? "No current assignee"}</p>
              <p>
                Requested start: {task.plan.requestedStart ?? "Not set"} ·
                Effective start: {task.plan.effectiveStart ?? "Unknown"} ·
                Duration: {task.plan.duration ?? "Not set"} working days.
              </p>
              <p>
                Scheduled finish: {date(task.plan.dueAt, workspace.timezone)}
                {task.plan.adjusted
                  ? " - Start adjusted for calendar or dependency handoff."
                  : ""}
              </p>
              {task.original && (
                <p>
                  Original task commitment:{" "}
                  {date(task.original.dueAt, workspace.timezone)}.
                </p>
              )}
              <p>
                {readiness[task.plan.readiness] ?? "Readiness unavailable"}.
                This does not start or complete work.
              </p>
              {task.plan.issue && (
                <p role="status">
                  {issues[task.plan.issue] ?? "Schedule needs assessment"}.
                </p>
              )}
              {task.plan.prerequisites.length > 0 && (
                <p>
                  Prerequisites:{" "}
                  {task.plan.prerequisites
                    .map((key) => labels.get(key) ?? "Project prerequisite")
                    .join(", ")}
                  .
                </p>
              )}
            </li>
          ))}
        </ol>
      </section>
      {workspace.canPlan && <ScheduleEditor workspace={workspace} />}
      {workspace.history.length > 0 && (
        <section aria-label="Schedule revision history">
          <h2>Latest 25 schedule revisions</h2>
          {workspace.history.map((row) => (
            <details key={row.id} className="schedule-card">
              <summary>
                {row.actorName} · {date(row.createdAt, workspace.timezone)}
              </summary>
              <p>{row.reason}</p>
              <p>
                Previous forecast:{" "}
                {date(row.before.forecastAt, workspace.timezone)}. Revised
                forecast: {date(row.after.forecastAt, workspace.timezone)}.
              </p>
              <ul>
                {row.after.tasks.map((task) => (
                  <li key={task.id}>
                    {labels.get(task.id) ?? "Retained task"}: requested{" "}
                    {task.requestedStart ?? "Not set"},{" "}
                    {task.duration ?? "Unknown"} working days; finish{" "}
                    {date(task.dueAt, workspace.timezone)}. Previous requested
                    start:{" "}
                    {row.before.tasks.find((t) => t.id === task.id)
                      ?.requestedStart ?? "Not set"}
                    ; previous duration:{" "}
                    {row.before.tasks.find((t) => t.id === task.id)?.duration ??
                      "Unknown"}{" "}
                    working days; previous finish:{" "}
                    {date(
                      row.before.tasks.find((t) => t.id === task.id)?.dueAt,
                      workspace.timezone,
                    )}
                    .
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </section>
      )}
    </>
  );
}
