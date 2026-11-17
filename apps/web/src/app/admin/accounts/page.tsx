import Link from "next/link";
import { randomUUID } from "node:crypto";
import { requireAdministrator } from "@/portals/admin/server";
import { administrationRequest } from "@/shared/api/account-administration";
import { AccountAdministrationDocument } from "@/shared/api/generated";
import { AccountDenied } from "@/shared/api/account-entry";
import { redirect } from "next/navigation";
const roles = ["EMPLOYEE", "MANAGER", "ADMIN", "HR"];
const notices: Record<string, string> = {
  complete:
    "The request completed. Email requests were accepted by the mail server; check the recipient inbox.",
  incomplete:
    "The request did not finish. Review provisioning or change history below before retrying.",
  rejected:
    "The change was rejected. Refresh the account, check its current status and retain at least one active administrator. You cannot deactivate or demote your own account.",
  confirmation: "Confirm the change before submitting.",
  unavailable:
    "Account services are unavailable. Refresh to check the recorded outcome before submitting again.",
};
function Hidden({ name, value }: { name: string; value: string | number }) {
  return <input type="hidden" name={name} value={value} />;
}
function Confirmation() {
  return (
    <label className="accounts-confirm">
      <input type="checkbox" name="confirm" value="yes" required /> I confirm
      this change
    </label>
  );
}
export default async function Accounts({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; notice?: string }>;
}) {
  const { actor, session } = await requireAdministrator();
  const params = await searchParams;
  const number = Number(params.page ?? 0);
  const page =
    Number.isInteger(number) && number >= 0 && number <= 10000 ? number : 0;
  let data;
  try {
    data = (
      await administrationRequest(session, AccountAdministrationDocument, {
        page,
      })
    ).accountAdministration;
  } catch (error) {
    if (error instanceof AccountDenied) redirect("/access-denied");
    return (
      <>
        <h1>User accounts</h1>
        <p role="alert">
          Account services are unavailable. Your existing accounts have not been
          changed.
        </p>
      </>
    );
  }
  return (
    <>
      <p className="admin-eyebrow">PEOPLE & ACCESS</p>
      <h1>User accounts</h1>
      <p className="admin-intro">
        Create accounts and manage company access. Project membership and team
        leadership are assigned separately.
      </p>
      {params.notice && notices[params.notice] && (
        <p role="status" className="accounts-notice">
          {notices[params.notice]}
        </p>
      )}
      <section className="accounts-panel" aria-labelledby="create-account">
        <h2 id="create-account">Create an account</h2>
        <p>
          The recipient receives a secure email link to verify their address and
          choose a password. No password is shown here.
        </p>
        <form
          method="post"
          action="/admin/accounts/command"
          className="accounts-create"
        >
          <Hidden name="intent" value="create" />
          <Hidden name="requestId" value={randomUUID()} />
          <label>
            Full name
            <input
              name="displayName"
              required
              maxLength={150}
              autoComplete="off"
            />
          </label>
          <label>
            Username
            <input
              name="username"
              required
              minLength={3}
              maxLength={100}
              pattern="[a-zA-Z0-9][a-zA-Z0-9._-]{2,99}"
              autoComplete="off"
            />
          </label>
          <label>
            Email address
            <input
              type="email"
              name="email"
              required
              maxLength={254}
              autoComplete="off"
            />
          </label>
          <label>
            Company role
            <select name="role" defaultValue="EMPLOYEE">
              {roles.map((role) => (
                <option key={role}>{role}</option>
              ))}
            </select>
          </label>
          <button className="admin-primary-button">
            Create account & send setup email
          </button>
        </form>
      </section>
      <section aria-labelledby="accounts-title">
        <h2 id="accounts-title">Company accounts</h2>
        <div className="accounts-list">
          {data.accounts.map((account) => (
            <article className="accounts-panel" key={account.id}>
              <h3>{account.displayName}</h3>
              <p>
                {account.username || "Existing account"}
                {account.email && ` · ${account.email}`}
              </p>
              <p>
                {account.active ? "Active" : "Inactive"} · {account.role}
                {account.id === actor.accountId ? " · Your account" : ""}
              </p>
              <div className="accounts-controls">
                <form method="post" action="/admin/accounts/command">
                  <Hidden name="intent" value="change" />
                  <Hidden name="requestId" value={randomUUID()} />
                  <Hidden name="accountId" value={account.id} />
                  <Hidden name="version" value={account.version} />
                  <Hidden name="action" value="ROLE" />
                  <label>
                    Company role for {account.displayName}
                    <select name="role" defaultValue={account.role}>
                      {roles.map((role) => (
                        <option key={role}>{role}</option>
                      ))}
                    </select>
                  </label>
                  <Confirmation />
                  <button>Save role</button>
                </form>
                <form method="post" action="/admin/accounts/command">
                  <Hidden name="intent" value="change" />
                  <Hidden name="requestId" value={randomUUID()} />
                  <Hidden name="accountId" value={account.id} />
                  <Hidden name="version" value={account.version} />
                  <Hidden
                    name="action"
                    value={account.active ? "DEACTIVATE" : "ACTIVATE"}
                  />
                  <Confirmation />
                  <button
                    disabled={account.id === actor.accountId && account.active}
                  >
                    {account.active ? "Deactivate account" : "Activate account"}
                  </button>
                </form>
                <form method="post" action="/admin/accounts/command">
                  <Hidden name="intent" value="change" />
                  <Hidden name="requestId" value={randomUUID()} />
                  <Hidden name="accountId" value={account.id} />
                  <Hidden name="version" value={account.version} />
                  <Hidden name="action" value="RESET_EMAIL" />
                  <Confirmation />
                  <button disabled={!account.active}>
                    Send password reset email
                  </button>
                </form>
              </div>
            </article>
          ))}
        </div>
        <nav aria-label="Account pages">
          {page > 0 && (
            <Link href={`/admin/accounts?page=${page - 1}`}>Previous page</Link>
          )}{" "}
          {data.hasMore && (
            <Link href={`/admin/accounts?page=${page + 1}`}>Next page</Link>
          )}
        </nav>
      </section>
      <section className="accounts-panel" aria-labelledby="provisioning-title">
        <h2 id="provisioning-title">Recent provisioning</h2>
        <p>
          Recovery checks the exact owned identity and does not retrieve or
          reset a password. A setup email may be sent again.
        </p>
        {data.operations.length === 0 && (
          <p>No accounts have been provisioned through these controls yet.</p>
        )}
        {data.operations.map((operation) => (
          <div className="accounts-operation" key={operation.id}>
            <strong>{operation.username}</strong>
            <span>{operation.state.replaceAll("_", " ")}</span>
            {operation.failureCode && (
              <p>
                Needs attention: {operation.failureCode.replaceAll("_", " ")}
              </p>
            )}
            {operation.state !== "COMPLETE" && (
              <form method="post" action="/admin/accounts/command">
                <Hidden name="intent" value="recover" />
                <Hidden name="requestId" value={randomUUID()} />
                <Hidden name="operationId" value={operation.id} />
                <Confirmation />
                <button>Retry provisioning for {operation.username}</button>
              </form>
            )}
          </div>
        ))}
      </section>
      <section className="accounts-panel" aria-labelledby="history-title">
        <h2 id="history-title">Recent account changes</h2>
        <p>
          Latest 25 requests. Failed or pending requests remain visible; refresh
          to check their outcome.
        </p>
        {data.history.length === 0 && <p>No account changes recorded yet.</p>}
        {data.history.map((entry) => (
          <details key={entry.id}>
            <summary>
              {entry.action.replaceAll("_", " ")} · {entry.state} ·{" "}
              <time>{entry.createdAt}</time>
            </summary>
            <p>
              Actor: {entry.actorId} · Account:{" "}
              {entry.targetId ?? "Provisioning"}
            </p>
            <p>Before: {entry.before}</p>
            <p>After: {entry.after}</p>
          </details>
        ))}
      </section>
    </>
  );
}
