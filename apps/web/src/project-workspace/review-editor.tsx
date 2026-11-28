"use client";

import { useState } from "react";
import type { ProjectReviewsQuery } from "@/shared/api/generated";

type Workspace = ProjectReviewsQuery["projectReviews"];
type Task = Workspace["tasks"][number];

export function ReviewEditor({
  workspace,
  task,
  action,
  submissionId,
}: {
  workspace: Workspace;
  task: Task;
  action: "START" | "PROGRESS" | "SUBMIT" | "DECIDE";
  submissionId?: string;
}) {
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [requestId, setRequestId] = useState("");
  const [outcome, setOutcome] = useState("APPROVE");
  const ownApproval = action === "DECIDE" && task.own && outcome === "APPROVE";
  const labels = {
    START: "Start my task",
    PROGRESS: "Record my progress",
    SUBMIT: "Submit for review",
    DECIDE: "Record review decision",
  };
  return (
    <form
      className="coordination-form"
      onChange={() => {
        setRequestId("");
        setMessage("");
      }}
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const id = requestId || crypto.randomUUID();
        setRequestId(id);
        setPending(true);
        setMessage("");
        try {
          const shared = {
            projectId: workspace.project.id,
            taskId: task.id,
            version: task.version,
            projectVersion: workspace.project.version,
            requestId: id,
            confirm: data.get("confirm") === "on",
          };
          const input =
            action === "DECIDE"
              ? {
                  ...shared,
                  submissionId,
                  outcome,
                  feedback: String(data.get("note")),
                  selfConfirm: ownApproval && data.get("selfConfirm") === "on",
                }
              : {
                  ...shared,
                  action,
                  note: String(data.get("note")),
                  progress:
                    action === "PROGRESS"
                      ? Number(data.get("progress"))
                      : task.progress,
                  blocker:
                    action === "PROGRESS"
                      ? String(data.get("blocker") || "").trim() || null
                      : task.blocker,
                };
          const response = await fetch("/projects/review-command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: action === "DECIDE" ? "decide" : "execute",
              input,
            }),
          });
          const result = await response.json();
          if (!response.ok)
            throw new Error(result.error || "Request unavailable");
          window.location.reload();
        } catch (error) {
          setMessage(
            error instanceof Error ? error.message : "Request unavailable",
          );
        } finally {
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending}>
        <legend>{labels[action]}</legend>
        {action === "DECIDE" && (
          <label>
            Decision
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
            >
              <option value="APPROVE">Approve completion</option>
              <option value="RETURN">Return for changes</option>
            </select>
          </label>
        )}
        {action === "PROGRESS" && (
          <>
            <label>
              Progress percent
              <input
                name="progress"
                type="number"
                min="0"
                max="100"
                step="1"
                defaultValue={task.progress}
                required
              />
            </label>
            <label>
              Current blocker
              <textarea
                name="blocker"
                maxLength={2000}
                defaultValue={task.blocker ?? ""}
              />
            </label>
            <p>
              Clear the blocker field to record its resolution. Progress at 100%
              does not approve completion.
            </p>
          </>
        )}
        <label>
          {action === "DECIDE"
            ? "Review feedback"
            : action === "SUBMIT"
              ? "Completion summary"
              : "Work note"}
          <textarea name="note" required maxLength={8000} />
        </label>
        <label className="calendar-confirm">
          <input type="checkbox" name="confirm" required />I confirm this{" "}
          {action === "DECIDE" ? "review decision" : "work update"}.
        </label>
        {ownApproval && (
          <label className="calendar-confirm">
            <input type="checkbox" name="selfConfirm" required />I explicitly
            approve my own submission. This will be recorded as self-approval.
          </label>
        )}
        <button type="submit" disabled={pending}>
          {pending ? "Recording…" : labels[action]}
        </button>
      </fieldset>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
