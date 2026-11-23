"use client";

import { useState } from "react";

type Recipient = {
  accountId: string | null;
  displayName: string;
  active: boolean;
};

export function CoordinationEditor({
  projectId,
  recipients,
  record,
}: {
  projectId: string;
  recipients: Recipient[];
  record?: { id: string; version: number };
}) {
  const [kind, setKind] = useState("UPDATE");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [requestId, setRequestId] = useState("");
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
          const localTime = String(data.get("time"));
          const time = new Date(localTime).toISOString();
          const input = record
            ? {
                projectId,
                recordId: record.id,
                version: record.version,
                requestId: id,
                note: String(data.get("note")),
                nextFollowUpAt: time,
                confirm: data.get("confirm") === "on",
              }
            : {
                projectId,
                requestId: id,
                kind,
                topic: String(data.get("topic")),
                details: String(data.get("details")),
                dueAt: time,
                location: kind === "UPDATE" ? "" : String(data.get("location")),
                acknowledgementRequired: data.get("acknowledgement") === "on",
                recipients: data.getAll("recipient").map(String),
                confirm: data.get("confirm") === "on",
              };
          const response = await fetch("/projects/coordination-command", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              command: record ? "follow-up" : "create",
              input,
            }),
          });
          const value = await response.json();
          if (!response.ok)
            throw new Error(value.error ?? "Coordination request unavailable.");
          window.location.reload();
        } catch (error) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Coordination request unavailable.",
          );
        } finally {
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending}>
        <legend>
          {record ? "Record a follow-up" : "New coordination request"}
        </legend>
        {record ? (
          <label>
            Follow-up note
            <textarea name="note" required maxLength={2000} />
          </label>
        ) : (
          <>
            <label>
              Type
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                <option value="UPDATE">Update request</option>
                <option value="MEETING">Internal meeting</option>
                <option value="CHECK_IN">Check-in</option>
              </select>
            </label>
            <label>
              Topic
              <input name="topic" required maxLength={150} />
            </label>
            <label>
              Request details
              <textarea name="details" required maxLength={2000} />
            </label>
            {kind !== "UPDATE" && (
              <label>
                Location or cabin
                <input name="location" required maxLength={300} />
              </label>
            )}
            <fieldset>
              <legend>Project recipients (up to 25)</legend>
              {recipients
                .filter((r) => r.active && r.accountId)
                .map((r) => (
                  <label key={r.accountId}>
                    <input
                      type="checkbox"
                      name="recipient"
                      value={r.accountId!}
                    />
                    {r.displayName}
                  </label>
                ))}
            </fieldset>
            <label>
              <input type="checkbox" name="acknowledgement" defaultChecked />
              Acknowledgement required
            </label>
          </>
        )}
        <label>
          {record
            ? "Next follow-up"
            : kind === "UPDATE"
              ? "Response required by"
              : "Meeting time"}
          <input type="datetime-local" name="time" required />
        </label>
        <p>
          Times use your device’s local timezone. Review the recorded UTC time
          after saving.
        </p>
        <label>
          <input
            type="checkbox"
            name="confirm"
            required
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
          />
          I have reviewed this request.
        </label>
        <button type="submit">
          {pending ? "Saving…" : record ? "Save follow-up" : "Create request"}
        </button>
      </fieldset>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
