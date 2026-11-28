"use client";
import { scheduleTime } from "./schedule-time";
import { useState } from "react";
import type {
  ProjectScheduleQuery,
  PreviewTaskScheduleMutation,
} from "@/shared/api/generated";
type Workspace = ProjectScheduleQuery["projectSchedule"];
type Preview = PreviewTaskScheduleMutation["previewTaskSchedule"];
export function ScheduleEditor({ workspace }: { workspace: Workspace }) {
  const [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState("");
  const [busy, setBusy] = useState(false),
    [requestId, setRequestId] = useState("");
  const labels = new Map(workspace.tasks.map((t) => [t.plan.id, t.title]));
  async function send(action: string, input: unknown) {
    const response = await fetch("/projects/schedule-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, input }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    return result;
  }
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPreview(null);
    setBusy(true);
    const data = new FormData(event.currentTarget),
      task = workspace.tasks.find((t) => t.plan.id === data.get("taskId"));
    if (!task) {
      setBusy(false);
      return;
    }
    try {
      setPreview(
        await send("preview", {
          projectId: workspace.project.id,
          projectVersion: workspace.project.version,
          taskId: task.plan.id,
          version: task.version,
          requestedStart: data.get("start"),
          duration: Number(data.get("duration")),
          prerequisites: data.getAll("prerequisites"),
          reason: data.get("reason"),
        }),
      );
      setRequestId(crypto.randomUUID());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview unavailable");
    } finally {
      setBusy(false);
    }
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview) return;
    setError("");
    setBusy(true);
    try {
      await send("commit", {
        projectId: workspace.project.id,
        previewId: preview.previewId,
        requestId,
        confirm: true,
      });
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Schedule unavailable");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="schedule-editor-heading">
      <h2 id="schedule-editor-heading">Plan a task schedule</h2>
      <p>
        Preview each change across dependent paths. Independent work stays
        parallel. Dates use the pinned calendar.
      </p>
      {workspace.tasks
        .filter((t) => t.status === "PENDING")
        .map((task) => (
          <details key={task.plan.id} className="schedule-card">
            <summary>Schedule {task.title}</summary>
            <form
              onSubmit={submit}
              onChange={() => setPreview(null)}
              className="schedule-form"
            >
              <input type="hidden" name="taskId" value={task.plan.id} />
              <label>
                Requested start
                <input
                  type="date"
                  name="start"
                  required
                  defaultValue={task.plan.requestedStart ?? ""}
                />
              </label>
              <label>
                Working-day duration
                <input
                  type="number"
                  name="duration"
                  min="1"
                  max="3660"
                  required
                  defaultValue={task.plan.duration ?? ""}
                />
              </label>
              <fieldset>
                <legend>Prerequisites</legend>
                {workspace.tasks
                  .filter((t) => t.plan.id !== task.plan.id)
                  .map((other) => (
                    <label key={other.plan.id}>
                      <input
                        type="checkbox"
                        name="prerequisites"
                        value={other.plan.id}
                        defaultChecked={task.plan.prerequisites.includes(
                          other.plan.id,
                        )}
                      />
                      {other.title}
                    </label>
                  ))}
              </fieldset>
              <label>
                Reason
                <textarea name="reason" maxLength={2000} required />
              </label>
              <button disabled={busy}>Preview schedule</button>
            </form>
          </details>
        ))}
      {error && <p role="alert">{error}</p>}
      {preview && (
        <section aria-label="Schedule impact preview" className="schedule-card">
          <h3>Review schedule impact</h3>
          <p>
            Calendar version {preview.calendarNumber} · {preview.timezone}.
            Preview expires {scheduleTime(preview.validUntil, preview.timezone)}
            .
          </p>
          <p>
            Forecast:{" "}
            {preview.after.forecastAt
              ? scheduleTime(preview.after.forecastAt, preview.timezone)
              : "Unassessed - some work has unknown scheduling inputs."}
          </p>
          {preview.exceedsDeadline && (
            <p role="status">
              Forecast exceeds the current approved deadline. Saving does not
              approve a deadline revision.
            </p>
          )}
          <p>
            Employee capacity is not guaranteed. {preview.after.overlaps.length}{" "}
            overlapping assignment pairs shown in this project (up to 100).
          </p>
          <ul>
            {preview.after.tasks.map((row) => (
              <li key={row.id}>
                {labels.get(row.id) ?? "Project task"}:{" "}
                {row.effectiveStart ?? "Unscheduled"} to{" "}
                {row.dueAt
                  ? scheduleTime(row.dueAt, preview.timezone)
                  : "Unknown finish"}
                {row.adjusted
                  ? " - Start adjusted by calendar or prerequisites"
                  : ""}
              </li>
            ))}
          </ul>
          <form onSubmit={save}>
            <label>
              <input type="checkbox" required />I reviewed the affected task
              paths and confirm this schedule revision.
            </label>
            <button disabled={busy}>Save confirmed schedule</button>
          </form>
        </section>
      )}
    </section>
  );
}
