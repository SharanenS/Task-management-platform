"use client";

import { useState } from "react";
import type {
  OwnerOversightQuery,
  PreviewOwnerDeadlineMutation,
} from "@/shared/api/generated";
import { sendOwnerCommand } from "./owner-command";

type Oversight = OwnerOversightQuery["ownerOversight"];
type Preview = PreviewOwnerDeadlineMutation["previewOwnerDeadline"];

export function OwnerDecisionEditor({
  workspace,
  escalation,
}: {
  workspace: Oversight;
  escalation: Oversight["escalations"][number];
}) {
  const [outcome, setOutcome] = useState("REQUEST_REPLAN");
  const [deadline, setDeadline] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [requestId, setRequestId] = useState("");
  const assessed =
    escalation.assessmentState === "ASSESSED" &&
    escalation.forecastAt !== null &&
    Date.parse(escalation.forecastAt) > Date.parse(workspace.currentDeadline);
  function changed() {
    setConfirmed(false);
    setRequestId("");
    setMessage("");
  }
  return (
    <form
      className="coordination-form"
      onChange={(event) => {
        if (
          !(event.target instanceof HTMLInputElement) ||
          event.target.name !== "confirm"
        )
          changed();
      }}
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const id = requestId || crypto.randomUUID();
        setRequestId(id);
        setPending(true);
        setMessage("");
        try {
          await sendOwnerCommand("decide", {
            projectId: workspace.project.id,
            escalationId: escalation.id,
            requestId: id,
            version: escalation.version,
            projectVersion: workspace.project.version,
            outcome,
            reason: String(data.get("reason")),
            affectedTeam: String(data.get("team")),
            previewId:
              outcome === "REVISE_DEADLINE" ? (preview?.id ?? null) : null,
            confirm: confirmed,
          });
          window.location.reload();
        } catch (error) {
          setMessage(
            error instanceof Error ? error.message : "Decision unavailable.",
          );
        } finally {
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending}>
        <legend>Record owner decision</legend>
        <label>
          Decision
          <select
            value={outcome}
            onChange={(event) => {
              setOutcome(event.target.value);
              setPreview(null);
              changed();
            }}
          >
            <option value="REQUEST_REPLAN">Request a revised plan</option>
            <option value="ACCEPT_FORECAST_LATE" disabled={!assessed}>
              Keep deadline and accept forecast late completion
            </option>
            <option value="REVISE_DEADLINE" disabled={!assessed}>
              Approve a revised project deadline
            </option>
          </select>
        </label>
        {!assessed && (
          <p>
            A fresh assessment beyond the approved deadline is required before
            accepting a late forecast or revising the deadline.
          </p>
        )}
        <label>
          Decision reason
          <textarea name="reason" required maxLength={2000} />
        </label>
        <label>
          Affected team and context
          <input
            name="team"
            required
            maxLength={300}
            defaultValue={escalation.affectedTeam}
          />
        </label>
        {outcome === "REVISE_DEADLINE" && (
          <>
            <label>
              Proposed deadline date
              <input
                type="date"
                required
                value={deadline}
                onChange={(event) => {
                  setDeadline(event.target.value);
                  setPreview(null);
                  changed();
                }}
              />
            </label>
            <button
              type="button"
              disabled={!deadline}
              onClick={async () => {
                setPending(true);
                setPreview(null);
                changed();
                try {
                  const result = await sendOwnerCommand<{ preview: Preview }>(
                    "preview",
                    {
                      projectId: workspace.project.id,
                      escalationId: escalation.id,
                      version: escalation.version,
                      deadlineDate: deadline,
                    },
                  );
                  setPreview(result.preview);
                } catch (error) {
                  setMessage(
                    error instanceof Error
                      ? error.message
                      : "Preview unavailable.",
                  );
                } finally {
                  setPending(false);
                }
              }}
            >
              Preview deadline revision
            </button>
            {preview && (
              <section aria-label="Deadline revision preview">
                <h4>Review deadline revision</h4>
                <p>Original commitment: {preview.originalDeadline}</p>
                <p>Current approval: {preview.currentDeadline}</p>
                <p>Assessed forecast: {preview.forecastAt}</p>
                <p>Proposed approval: {preview.deadlineLocal}</p>
                <p>
                  Preview valid until {preview.expiresAt}. Changes to the
                  project or assessment require a new preview.
                </p>
                <p>
                  Calendar version {preview.calendarNumber}. This changes the
                  project commitment; task schedules are not silently rewritten.
                </p>
              </section>
            )}
          </>
        )}
        <label>
          <input
            type="checkbox"
            name="confirm"
            required
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I confirm this decision and its recorded context.
        </label>
        <button
          type="submit"
          disabled={!confirmed || (outcome === "REVISE_DEADLINE" && !preview)}
        >
          {pending ? "Recording…" : "Record decision"}
        </button>
      </fieldset>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
