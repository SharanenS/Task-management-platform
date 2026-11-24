"use client";

import { useState } from "react";
import type {
  ProjectTasksQuery,
  TaskCandidatesQuery,
} from "@/shared/api/generated";

type Workspace = ProjectTasksQuery["projectTasks"];
export function TaskEditor({
  workspace,
  candidates,
  task,
  action = "CREATE",
}: {
  workspace: Workspace;
  candidates: TaskCandidatesQuery["taskCandidates"]["candidates"];
  task?: Workspace["tasks"][number];
  action?: "CREATE" | "EDIT" | "ASSIGN";
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [message, setMessage] = useState("");
  const title =
    action === "CREATE"
      ? "Create task"
      : action === "EDIT"
        ? "Edit task instructions"
        : "Reassign task";
  return (
    <form
      className="coordination-form"
      onChange={(event) => {
        setRequestId("");
        setMessage("");
        if (
          !(event.target instanceof HTMLInputElement) ||
          event.target.name !== "confirm"
        )
          setConfirmed(false);
      }}
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const id = requestId || crypto.randomUUID();
        setRequestId(id);
        setPending(true);
        setMessage("");
        try {
          const response = await fetch("/projects/task-command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              input: {
                projectId: workspace.project.id,
                projectVersion: workspace.project.version,
                taskId: task?.id ?? null,
                version: task?.details?.version ?? 0,
                action,
                requestId: id,
                title: action === "ASSIGN" ? null : String(data.get("title")),
                instructions:
                  action === "ASSIGN" ? null : String(data.get("instructions")),
                acceptanceCriteria:
                  action === "ASSIGN" ? null : String(data.get("criteria")),
                assigneeId:
                  action === "EDIT" ? null : String(data.get("assignee")),
                reason: String(data.get("reason")),
                confirm: confirmed,
              },
            }),
          });
          if (!response.ok)
            throw new Error(
              (await response.json()).error || "Task change unavailable.",
            );
          window.location.reload();
        } catch (error) {
          setMessage(
            error instanceof Error ? error.message : "Task change unavailable.",
          );
        } finally {
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending}>
        <legend>{title}</legend>
        {action !== "ASSIGN" && (
          <>
            <label>
              Task title
              <input
                name="title"
                required
                maxLength={200}
                defaultValue={task?.title}
              />
            </label>
            <label>
              Instructions
              <textarea
                name="instructions"
                required
                maxLength={8000}
                defaultValue={task?.details?.instructions}
              />
            </label>
            <label>
              Acceptance criteria
              <textarea
                name="criteria"
                required
                maxLength={8000}
                defaultValue={task?.details?.acceptanceCriteria}
              />
            </label>
          </>
        )}
        {action !== "EDIT" && (
          <label>
            Assign to
            <select name="assignee" required defaultValue="">
              <option value="" disabled>
                Select an eligible project member
              </option>
              {candidates
                .filter(
                  (c) =>
                    action !== "ASSIGN" ||
                    c.accountId !== task?.details?.assigneeId,
                )
                .map((c) => (
                  <option key={c.accountId} value={c.accountId}>
                    {c.displayName}
                  </option>
                ))}
            </select>
          </label>
        )}
        <label>
          Reason
          <textarea name="reason" required maxLength={2000} />
        </label>
        <label>
          <input
            type="checkbox"
            name="confirm"
            checked={confirmed}
            required
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I confirm this task planning change.
        </label>
        <button type="submit" disabled={!confirmed}>
          {pending ? "Saving…" : title}
        </button>
      </fieldset>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
