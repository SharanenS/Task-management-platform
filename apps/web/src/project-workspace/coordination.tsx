import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  ProjectCoordinationDocument,
  ProjectMembershipDocument,
} from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import { CoordinationEditor } from "./coordination-editor";

export async function ProjectCoordination({
  id,
  page = "0",
}: {
  id: string;
  page?: string;
}) {
  const { session, actor, root } = await requireProjectViewer();
  if (!["ADMIN", "MANAGER"].includes(actor.companyRoles[0]))
    redirect("/access-denied");
  const pageNumber =
    /^\d{1,5}$/.test(page) && Number(page) <= 10000 ? Number(page) : 0;
  let workspace;
  let membership;
  try {
    membership = (
      await administrationRequest(session, ProjectMembershipDocument, { id })
    ).projectMembership;
    workspace = (
      await administrationRequest(session, ProjectCoordinationDocument, {
        id,
        page: pageNumber,
      })
    ).projectCoordination;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Project coordination</h1>
        <p role="alert">
          Coordination services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">PROJECT COORDINATION</p>
      <h1>{membership.project.name}</h1>
      <Link href={`${root}/${id}`}>Back to project</Link>
      <p>
        Manage update requests, internal meetings and check-ins for this
        project. These records do not send email, create external calendar
        events or place calls.
      </p>
      <p>
        Employee responses and acknowledgements will become available in a later
        stage. Pending states below reflect that no response has been recorded.
        Follow-ups are manual; automatic reminders are not enabled.
      </p>
      <section className="project-panel">
        <CoordinationEditor projectId={id} recipients={membership.members} />
      </section>
      {!workspace.records.length && <p>No coordination requests recorded.</p>}
      {workspace.records.map((record) => (
        <section className="project-panel" key={record.id}>
          <h2>{record.topic}</h2>
          <p>
            {record.kind.replaceAll("_", " ")} ·{" "}
            {record.overdue ? "Outstanding past scheduled time" : "Pending"}
          </p>
          <p className="project-objectives">{record.details}</p>
          <p>
            {record.kind === "UPDATE" ? "Response due" : "Scheduled time"}:{" "}
            <time dateTime={record.dueAt}>{record.dueAt}</time> (UTC)
          </p>
          {record.location && <p>Location: {record.location}</p>}
          <h3>Recipients</h3>
          <ul>
            {record.recipients.map((r) => (
              <li key={r.accountId}>
                {r.displayName} — Acknowledgement:{" "}
                {r.acknowledgement.replaceAll("_", " ")} · Response:{" "}
                {r.responseState}
              </li>
            ))}
          </ul>
          <h3>Follow-up history</h3>
          {record.followUps.length ? (
            <ol>
              {record.followUps.map((f) => (
                <li key={f.id}>
                  <p>{f.note}</p>
                  <p>
                    Recorded {f.createdAt} · Next follow-up {f.nextFollowUpAt}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p>No follow-ups recorded.</p>
          )}
          <CoordinationEditor projectId={id} recipients={[]} record={record} />
        </section>
      ))}
      <nav aria-label="Coordination pages">
        {pageNumber > 0 && (
          <Link href={`?page=${pageNumber - 1}`}>Previous requests</Link>
        )}
        {workspace.hasMore && (
          <Link href={`?page=${pageNumber + 1}`}>More requests</Link>
        )}
      </nav>
    </>
  );
}
