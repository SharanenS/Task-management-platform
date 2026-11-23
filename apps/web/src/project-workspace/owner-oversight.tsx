import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  administrationRequest,
  ProjectChangeRejected,
} from "@/shared/api/account-administration";
import { AccountDenied } from "@/shared/api/account-entry";
import {
  OwnerOversightDocument,
  ReviewFallbacksDocument,
} from "@/shared/api/generated";
import { requireProjectViewer } from "./server";
import { OwnerDecisionEditor } from "./owner-decision-editor";
import { ReviewFallbackEditor } from "./review-fallback-editor";

export async function OwnerOversight({
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
  let fallbacks;
  try {
    workspace = (
      await administrationRequest(session, OwnerOversightDocument, {
        id,
        page: pageNumber,
      })
    ).ownerOversight;
    fallbacks = (
      await administrationRequest(session, ReviewFallbacksDocument, {
        id,
        page: pageNumber,
      })
    ).reviewFallbacks;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    if (
      error instanceof ProjectChangeRejected &&
      error.reason === "project_not_found"
    )
      notFound();
    return (
      <>
        <h1>Delivery oversight</h1>
        <p role="alert">
          Owner decision services are unavailable. Please try again later.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="project-eyebrow">DELIVERY OVERSIGHT</p>
      <h1>{workspace.project.name}</h1>
      <Link href={`${root}/${id}`}>Back to project</Link>
      <dl className="oversight-metrics">
        <div>
          <dt>Original commitment</dt>
          <dd>{workspace.project.deadlineLocal}</dd>
          <dd>
            {workspace.originalOverdue
              ? "Original commitment is past due"
              : "Original commitment retained"}
          </dd>
        </div>
        <div>
          <dt>Current approved deadline</dt>
          <dd>{workspace.currentDeadline}</dd>
          <dd>
            {workspace.currentOverdue
              ? "Current commitment is past due"
              : "Current commitment retained"}
          </dd>
        </div>
        <div>
          <dt>Current forecast</dt>
          <dd>{workspace.forecastAt ?? "Not assessed"}</dd>
          <dd>
            {workspace.forecastState === "STALE"
              ? "Assessment needs refreshing"
              : workspace.forecastLate === null
                ? "Awaiting a delivery assessment"
                : workspace.forecastLate
                  ? "Forecast late"
                  : "Forecast within the approved deadline"}
          </dd>
        </div>
      </dl>
      <p>
        Commitments and forecasts are separate. A forecast is not an actual
        delivery result. Actual delivery:{" "}
        {workspace.actualDeliveryAt ?? "not recorded"}.
      </p>
      <section className="project-panel">
        <h2>Owner escalation inbox</h2>
        {!workspace.escalations.length && (
          <p>
            No pending owner escalations. Requests will appear when an
            authorized delivery assessment needs an owner decision.
          </p>
        )}
        {workspace.escalations.map((escalation) => (
          <article key={escalation.id} className="oversight-record">
            <h3>Pending deadline decision</h3>
            <p>{escalation.reason}</p>
            <p>Affected team: {escalation.affectedTeam}</p>
            <p>
              Assessment: {escalation.assessmentState}. Last assessed forecast:{" "}
              {escalation.forecastAt ?? "unavailable"}.
            </p>
            {escalation.assessmentSummary && (
              <p>{escalation.assessmentSummary}</p>
            )}
            <OwnerDecisionEditor
              workspace={workspace}
              escalation={escalation}
            />
          </article>
        ))}
      </section>
      <section className="project-panel">
        <h2>Decision history</h2>
        {!workspace.history.length && <p>No owner decisions recorded.</p>}
        {workspace.history.map((decision) => (
          <article key={decision.id} className="oversight-record">
            <h3>
              {decision.outcome === "REVISE_DEADLINE"
                ? "Project deadline revised"
                : decision.outcome === "ACCEPT_FORECAST_LATE"
                  ? "Forecast late completion accepted"
                  : "Revised plan requested"}
            </h3>
            <p>{decision.reason}</p>
            <p>
              {decision.actorName} ({decision.actorRole}) · {decision.createdAt}
            </p>
            <p>Affected team and context: {decision.affectedTeam}</p>
            <p>Prior approval: {decision.previousDeadline}</p>
            <p>
              Forecast snapshot ({decision.assessmentState}):{" "}
              {decision.forecastAt ?? "unavailable"}
            </p>
            {decision.revisedDeadline && (
              <p>Revised approval: {decision.revisedDeadline}</p>
            )}
            {decision.previousOverdue && (
              <p>
                The prior commitment was already overdue when this decision was
                recorded.
              </p>
            )}
          </article>
        ))}
      </section>
      <section className="project-panel">
        <h2>Leader absence and fallback</h2>
        <p>
          Current leader: {fallbacks.leaderName ?? "no leader appointed"}.
          Fallback requires an explicit scope and time window; signing out does
          not qualify.
        </p>
        {fallbacks.canRecord && (
          <ReviewFallbackEditor
            projectId={id}
            projectVersion={workspace.project.version}
            leaderId={fallbacks.leaderId}
          />
        )}
        {!fallbacks.records.length && <p>No scoped absence records.</p>}
        {fallbacks.records.map((record) => (
          <article key={record.id} className="oversight-record">
            <h3>{record.active ? "Active fallback" : "Inactive fallback"}</h3>
            <p>
              {record.leaderName ?? "Leadership vacancy"} · {record.scope}
            </p>
            <p>{record.reason}</p>
            <p>
              {record.startsAt} to {record.endsAt} (UTC) · Recorded by{" "}
              {record.actorName}
            </p>
            {record.revokedAt && (
              <p>
                Revoked {record.revokedAt}: {record.revocationReason}
              </p>
            )}
            {fallbacks.canRecord && !record.revokedAt && (
              <ReviewFallbackEditor
                projectId={id}
                projectVersion={workspace.project.version}
                leaderId={record.leaderId}
                recordId={record.id}
              />
            )}
          </article>
        ))}
      </section>
      <nav aria-label="Oversight pages">
        {pageNumber > 0 && (
          <Link href={`?page=${pageNumber - 1}`}>Previous records</Link>
        )}
        {(workspace.hasMore || fallbacks.hasMore) && (
          <Link href={`?page=${pageNumber + 1}`}>More records</Link>
        )}
      </nav>
    </>
  );
}
