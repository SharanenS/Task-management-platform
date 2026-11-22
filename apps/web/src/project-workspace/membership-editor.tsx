"use client";
import { useState } from "react";
import type {
  ProjectMembershipQuery,
  ProjectCandidatesQuery,
} from "@/shared/api/generated";
type Workspace = ProjectMembershipQuery["projectMembership"];

export function MembershipEditor({
  workspace,
  candidates,
}: {
  workspace: Workspace;
  candidates: ProjectCandidatesQuery["projectCandidates"]["candidates"];
}) {
  const [accountId, setAccountId] = useState("");
  const [responsibility, setResponsibility] = useState("CONTRIBUTOR");
  const [duties, setDuties] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [requestId, setRequestId] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  function changed() {
    setConfirmed(false);
    setRequestId("");
    setMessage("");
  }
  function select(value: string) {
    const member = workspace.members.find((m) => m.accountId === value);
    setAccountId(value);
    setResponsibility(member?.responsibility ?? "CONTRIBUTOR");
    setDuties(member?.duties ?? "");
    changed();
  }
  async function submit(action: "appoint" | "remove") {
    const id = requestId || crypto.randomUUID();
    setRequestId(id);
    setPending(true);
    setMessage("");
    try {
      const response = await fetch("/projects/membership-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          projectId: workspace.project.id,
          requestId: id,
          version: workspace.project.version,
          accountId,
          action,
          responsibility,
          duties,
          confirm: confirmed,
        }),
      });
      const value = await response.json();
      if (!response.ok)
        throw new Error(value.error ?? "Membership change unavailable.");
      window.location.reload();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Membership change unavailable.",
      );
    } finally {
      setPending(false);
    }
  }
  const existing = workspace.members.find((m) => m.accountId === accountId);
  return (
    <section className="project-panel">
      <h2>Manage project membership</h2>
      <p>
        Only active EMPLOYEE accounts can be appointed. Appointments apply to
        this project only. One active team leader is supported; demote or remove
        the current leader before appointing another.
      </p>
      {message && (
        <p role="alert" className="project-notice">
          {message}
        </p>
      )}
      <form
        className="project-create"
        onSubmit={(event) => {
          event.preventDefault();
          void submit("appoint");
        }}
      >
        <fieldset disabled={pending}>
          <label>
            Employee
            <select
              aria-label="Employee"
              required
              value={accountId}
              onChange={(event) => select(event.target.value)}
            >
              <option value="">Choose an employee</option>
              <optgroup label="Existing appointments">
                {workspace.members.map((member) => (
                  <option key={member.id} value={member.accountId!}>
                    {member.displayName} ·{" "}
                    {member.active ? member.responsibility : "Removed"}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Eligible employees">
                {candidates
                  .filter(
                    (candidate) =>
                      !workspace.members.some(
                        (member) => member.accountId === candidate.accountId,
                      ),
                  )
                  .map((candidate) => (
                    <option
                      key={candidate.accountId}
                      value={candidate.accountId}
                    >
                      {candidate.displayName} ·{" "}
                      {candidate.accountId.slice(0, 8)}
                    </option>
                  ))}
              </optgroup>
            </select>
          </label>
          <label>
            Project responsibility
            <select
              aria-label="Project responsibility"
              value={responsibility}
              onChange={(event) => {
                setResponsibility(event.target.value);
                changed();
              }}
            >
              <option value="CONTRIBUTOR">Contributor</option>
              <option value="LEADER">Team leader</option>
            </select>
          </label>
          <label>
            Responsibilities
            <textarea
              maxLength={1000}
              value={duties}
              onChange={(event) => {
                setDuties(event.target.value);
                changed();
              }}
            />
          </label>
          <p>
            Detailed responsibilities are visible to this employee and project
            management. Peers see only the appointment title.
          </p>
          <label className="project-confirm">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            I confirm this project membership change
          </label>
          <button disabled={!accountId || !confirmed}>Save appointment</button>
          {existing?.active && (
            <button
              type="button"
              disabled={!confirmed}
              onClick={() => void submit("remove")}
            >
              Remove appointment
            </button>
          )}
        </fieldset>
      </form>
    </section>
  );
}
