"use client";

import { useState } from "react";
import { sendOwnerCommand } from "./owner-command";

export function ReviewFallbackEditor({
  projectId,
  projectVersion,
  leaderId,
  recordId,
}: {
  projectId: string;
  projectVersion: number;
  leaderId: string | null;
  recordId?: string;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
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
          const shared = {
            projectId,
            requestId: id,
            reason: String(data.get("reason")),
            confirm: confirmed,
          };
          await sendOwnerCommand(
            recordId ? "fallback-revoke" : "fallback-create",
            recordId
              ? {
                  ...shared,
                  recordId,
                }
              : {
                  ...shared,
                  projectVersion,
                  leaderId,
                  scope: String(data.get("scope")),
                  startsAt: new Date(String(data.get("starts"))).toISOString(),
                  endsAt: new Date(String(data.get("ends"))).toISOString(),
                },
          );
          window.location.reload();
        } catch (error) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Absence record unavailable.",
          );
        } finally {
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending}>
        <legend>
          {recordId ? "Revoke fallback record" : "Record scoped leader absence"}
        </legend>
        <label>
          {recordId ? "Revocation reason" : "Absence reason"}
          <textarea name="reason" required maxLength={2000} />
        </label>
        {!recordId && (
          <>
            <label>
              Fallback scope
              <select name="scope">
                <option value="REVIEWS">Reviews</option>
                <option value="EXTENSIONS">
                  Within-deadline extension assessment
                </option>
                <option value="BOTH">Both</option>
              </select>
            </label>
            <label>
              Starts at
              <input name="starts" type="datetime-local" required />
            </label>
            <label>
              Ends at
              <input name="ends" type="datetime-local" required />
            </label>
            <p>
              Times use your device timezone and are recorded as UTC. Only the
              current project owner or ADMIN receives fallback authority.
              Signing out never creates an absence.
            </p>
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
          I confirm this scoped absence change.
        </label>
        <button type="submit" disabled={!confirmed}>
          {pending
            ? "Recording…"
            : recordId
              ? "Revoke fallback"
              : "Record absence"}
        </button>
      </fieldset>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
