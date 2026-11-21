"use client";
import { useState } from "react";
import type {
  ProjectWorkspaceQuery,
  PreviewProjectMutation,
} from "@/shared/api/generated";
export function ProjectCreate({
  calendar,
}: {
  calendar: NonNullable<ProjectWorkspaceQuery["projectWorkspace"]["calendar"]>;
}) {
  const [name, setName] = useState("");
  const [objectives, setObjectives] = useState("");
  const [date, setDate] = useState("");
  const [preview, setPreview] = useState<
    PreviewProjectMutation["previewProject"] | null
  >(null);
  const [confirmed, setConfirmed] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  function changed() {
    setPreview(null);
    setConfirmed(false);
    setError("");
  }
  async function command(action: string, input: unknown) {
    const response = await fetch("/projects/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, input }),
    });
    const value = await response.json();
    if (!response.ok)
      throw new Error(value.error ?? "Project request unavailable");
    return value;
  }
  async function perform(work: () => Promise<void>) {
    setPending(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Project request unavailable");
    } finally {
      setPending(false);
    }
  }
  return (
    <section className="project-panel">
      {error && (
        <p role="alert" className="project-notice">
          {error}
        </p>
      )}
      <p>
        Calendar loaded with this page: version {calendar.number},{" "}
        {calendar.timezone}. Choose an agreed working-date deadline; non-working
        dates will not be silently shifted.
      </p>
      <form
        className="project-create"
        onSubmit={(e) => {
          e.preventDefault();
          void perform(async () => {
            const value = await command("preview", {
              name,
              objectives,
              deadlineDate: date,
            });
            setPreview(value.result);
            setRequestId(crypto.randomUUID());
            setConfirmed(false);
          });
        }}
      >
        <fieldset disabled={pending}>
          <label>
            Project name
            <input
              name="name"
              required
              maxLength={150}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                changed();
              }}
            />
          </label>
          <label>
            Objectives
            <textarea
              name="objectives"
              required
              maxLength={5000}
              value={objectives}
              onChange={(e) => {
                setObjectives(e.target.value);
                changed();
              }}
            />
          </label>
          <label>
            Agreed deadline date
            <input
              name="deadlineDate"
              type="date"
              required
              min="1970-01-01"
              max="2199-12-31"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                changed();
              }}
            />
          </label>
          <button>Preview project</button>
        </fieldset>
      </form>
      {preview && (
        <div className="project-create">
          <h2>Review project commitment</h2>
          <p>
            <strong>{preview.name}</strong>
          </p>
          <p className="project-objectives">{preview.objectives}</p>
          <p>
            Agreed deadline: {preview.deadlineLocal} ({preview.timezone}). UTC:{" "}
            {preview.approvedDeadline}. Calendar version{" "}
            {preview.calendarNumber}.
          </p>
          {preview.pastDeadline && (
            <p className="project-notice">
              This deadline is already in the past. Confirm only if this is the
              intended commitment.
            </p>
          )}
          <p>
            The preview expires after ten minutes. Calendar changes require a
            fresh review.
          </p>
          <label className="project-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I confirm the objectives and initial agreed deadline
          </label>
          <button
            disabled={!confirmed || pending}
            onClick={() =>
              void perform(async () => {
                const value = await command("create", {
                  requestId,
                  previewId: preview.previewId,
                  confirm: true,
                });
                window.location.assign(value.href);
              })
            }
          >
            Create confirmed project
          </button>
        </div>
      )}
    </section>
  );
}
