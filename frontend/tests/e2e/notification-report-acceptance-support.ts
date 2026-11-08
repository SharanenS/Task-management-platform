import { execFileSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import type { Page } from "@playwright/test";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SERVICE_PATTERN = /^[a-z][a-z0-9-]{0,63}$/;

export function checkedUuid(value: string, label: string): string {
  if (!UUID_PATTERN.test(value)) throw new Error(`${label} is not a UUID.`);
  return value;
}

export function sqlLiteral(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

export function runMarker(prefix = "P11"): string {
  return `${prefix}-${Date.now().toString(36).toUpperCase()}-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
}

export function compose(args: string[]): string {
  try {
    return execFileSync("docker", ["compose", ...args], {
      cwd: "..",
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      env: process.env,
    });
  } catch {
    throw new Error("The exact Compose operation failed.");
  }
}

export function composeService(operation: "start" | "stop", service: string) {
  if (!SERVICE_PATTERN.test(service))
    throw new Error("Invalid Compose service name.");
  compose([operation, service]);
}

export function sql(
  service: string,
  user: string,
  database: string,
  query: string,
) {
  for (const value of [service, user, database])
    if (!SERVICE_PATTERN.test(value))
      throw new Error("Invalid database target.");
  return compose([
    "exec",
    "-T",
    service,
    "psql",
    "-v",
    "ON_ERROR_STOP=1",
    "-U",
    user,
    "-d",
    database,
    "-Atc",
    query,
  ]).trim();
}

export async function waitForHealthy(service: string, timeoutMs = 60_000) {
  if (!SERVICE_PATTERN.test(service))
    throw new Error("Invalid Compose service name.");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const parsed = JSON.parse(
        compose(["ps", "--format", "json", service]),
      ) as
        | { State?: string; Health?: string }
        | Array<{ State?: string; Health?: string }>;
      const rows = Array.isArray(parsed) ? parsed : [parsed];
      if (
        rows.length === 1 &&
        rows[0].State === "running" &&
        rows[0].Health === "healthy"
      )
        return;
    } catch {
      // Report one fixed diagnostic only after the bounded deadline.
    }
    await delay(1_000);
  }
  throw new Error(`${service} did not become healthy within the bounded wait.`);
}

export const BROKER_DEPENDENTS = [
  "work-event-publisher",
  "notification-consumer",
  "job-publisher",
  "job-domain-publisher",
  "job-worker",
  "workflow-consumer",
] as const;

export async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}

export async function signIn(page: Page, username: string, password: string) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
}

export async function firstSignInDisposable(
  page: Page,
  identity: OwnedIdentity,
) {
  const temporary = process.env.PHASE4_E2E_TEMP_PASSWORD;
  const replacement = process.env.PHASE4_E2E_PASSWORD;
  if (!temporary || !replacement)
    throw new Error("Disposable identity login is not configured.");
  await signIn(page, identity.username, temporary);
  await page.locator("#password-new").fill(replacement);
  await page.locator("#password-confirm").fill(replacement);
  await page.getByRole("button", { name: /submit/i }).click();
}

export class Cleanup {
  private readonly failures: string[] = [];

  async stage(label: string, action: () => void | Promise<void>) {
    try {
      await action();
    } catch {
      this.failures.push(label);
    }
  }

  finish() {
    if (this.failures.length)
      throw new Error(`Cleanup failed at: ${this.failures.join(", ")}.`);
  }
}

export type OwnedIdentity = {
  username: string;
  email: string;
  subject?: string;
  employeeId?: string;
};

export function recordIdentity(
  identity: OwnedIdentity,
  protectedSubject: string,
) {
  const users = JSON.parse(
    compose([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "get",
      "users",
      "-r",
      "taskspace",
      "-q",
      `username=${identity.username}`,
    ]),
  ) as Array<{ id: string; username: string; email?: string }>;
  const exact = users.filter((user) => user.username === identity.username);
  const profile = sql(
    "employee-db",
    "employee",
    "employee",
    `select id::text || '|' || keycloak_subject || '|' || email from employees where username=${sqlLiteral(identity.username)};`,
  );
  if (exact.length !== 1 || exact[0].email !== identity.email || !profile)
    throw new Error("Disposable identity ownership is ambiguous.");
  const [employeeId, subject, email] = profile.split("|");
  const validatedEmployeeId = checkedUuid(employeeId, "Employee ID");
  const validatedSubject = checkedUuid(subject, "Keycloak subject");
  if (
    email !== identity.email ||
    subject !== exact[0].id ||
    (identity.employeeId && identity.employeeId !== validatedEmployeeId) ||
    (identity.subject && identity.subject !== validatedSubject) ||
    subject === protectedSubject
  )
    throw new Error("Disposable identity linkage is not owned by this run.");
  identity.employeeId = validatedEmployeeId;
  identity.subject = validatedSubject;
}

export async function provisionDisposableMember(
  page: Page,
  marker: string,
  protectedSubject: string,
): Promise<OwnedIdentity> {
  const temporaryPassword = process.env.PHASE4_E2E_TEMP_PASSWORD;
  if (!temporaryPassword)
    throw new Error("Disposable identity provisioning is not configured.");
  const safe = marker
    .toLowerCase()
    .replaceAll(/[^a-z0-9-]/g, "")
    .slice(-18);
  const identity: OwnedIdentity = {
    username: `p11-member-${safe}`,
    email: `p11-member-${safe}@example.invalid`,
  };
  const result = await gql(
    page,
    "mutation($input:ProvisionEmployeeInput!){provisionEmployee(input:$input){id}}",
    {
      input: {
        idempotencyKey: crypto.randomUUID(),
        username: identity.username,
        email: identity.email,
        displayName: identity.username,
        role: "MEMBER",
        active: true,
        temporaryPassword,
      },
    },
  );
  if (result.errors) throw new Error("Disposable member provisioning failed.");
  identity.employeeId = checkedUuid(
    result.data.provisionEmployee.id,
    "provisioned Employee ID",
  );
  recordIdentity(identity, protectedSubject);
  return identity;
}

export async function provisionDisposableManager(
  page: Page,
  marker: string,
  protectedSubject: string,
): Promise<OwnedIdentity> {
  const temporaryPassword = process.env.PHASE4_E2E_TEMP_PASSWORD;
  if (!temporaryPassword)
    throw new Error("Disposable identity provisioning is not configured.");
  const safe = marker
    .toLowerCase()
    .replaceAll(/[^a-z0-9-]/g, "")
    .slice(-18);
  const identity: OwnedIdentity = {
    username: `p13-mgr-${safe}`,
    email: `p13-mgr-${safe}@example.invalid`,
  };
  const result = await gql(
    page,
    "mutation($input:ProvisionEmployeeInput!){provisionEmployee(input:$input){id}}",
    {
      input: {
        idempotencyKey: crypto.randomUUID(),
        username: identity.username,
        email: identity.email,
        displayName: identity.username,
        role: "MANAGER",
        active: true,
        temporaryPassword,
      },
    },
  );
  if (result.errors) throw new Error("Disposable manager provisioning failed.");
  identity.employeeId = checkedUuid(
    result.data.provisionEmployee.id,
    "provisioned Employee ID",
  );
  recordIdentity(identity, protectedSubject);
  return identity;
}

export async function cleanupOwnedIdentity(
  cleanup: Cleanup,
  identity: OwnedIdentity,
  protectedSubject: string,
) {
  let ownershipVerified = false;
  await cleanup.stage(`verify identity ${identity.username}`, () => {
    recordIdentity(identity, protectedSubject);
    ownershipVerified = true;
  });
  await cleanup.stage(`delete profile ${identity.username}`, () => {
    if (!ownershipVerified) return;
    compose([
      "exec",
      "-T",
      "employee",
      "python",
      "-m",
      "app.development_access",
      "remove",
      "--subject",
      checkedUuid(identity.subject!, "disposable subject"),
      "--protected-subject",
      protectedSubject,
    ]);
  });
  await cleanup.stage(`delete identity ${identity.username}`, () => {
    if (!ownershipVerified) return;
    compose([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "delete",
      `users/${checkedUuid(identity.subject!, "disposable subject")}`,
      "-r",
      "taskspace",
    ]);
  });
  await cleanup.stage(`verify identity removal ${identity.username}`, () => {
    const profiles = sql(
      "employee-db",
      "employee",
      "employee",
      `select count(*) from employees where username=${sqlLiteral(identity.username)} or email=${sqlLiteral(identity.email)};`,
    );
    const users = JSON.parse(
      compose([
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "get",
        "users",
        "-r",
        "taskspace",
        "-q",
        `username=${identity.username}`,
      ]),
    ) as Array<{ username: string; email?: string }>;
    if (
      profiles !== "0" ||
      users.some(
        (user) =>
          user.username === identity.username || user.email === identity.email,
      )
    )
      throw new Error("Disposable identity rows remain.");
  });
}

export function verifyPrimaryAdministrator(username: string, subject: string) {
  checkedUuid(subject, "protected administrator subject");
  const count = sql(
    "employee-db",
    "employee",
    "employee",
    `select count(*) from employees where username=${sqlLiteral(username)} and keycloak_subject=${sqlLiteral(subject)} and active is true and role='ADMIN' and provisioning_status='COMPLETE';`,
  );
  if (count !== "1")
    throw new Error("Protected administrator profile integrity failed.");
}

export function protectedAdministrator(): {
  username: string;
  subject: string;
} {
  const username = process.env.DEV_USER_USERNAME;
  const adminUsername = process.env.KEYCLOAK_ADMIN_USERNAME;
  const adminPassword = process.env.KEYCLOAK_ADMIN_PASSWORD;
  if (!username || !adminUsername || !adminPassword)
    throw new Error("Protected administrator verification is not configured.");
  compose([
    "exec",
    "-T",
    "keycloak",
    "/opt/keycloak/bin/kcadm.sh",
    "config",
    "credentials",
    "--server",
    "http://localhost:8080",
    "--realm",
    "master",
    "--user",
    adminUsername,
    "--password",
    adminPassword,
  ]);
  const users = JSON.parse(
    compose([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "get",
      "users",
      "-r",
      "taskspace",
      "-q",
      `username=${username}`,
    ]),
  ) as Array<{ id: string; username: string; enabled: boolean }>;
  const exact = users.filter((user) => user.username === username);
  if (exact.length !== 1 || !exact[0].enabled)
    throw new Error("Protected administrator identity integrity failed.");
  const subject = checkedUuid(exact[0].id, "protected administrator subject");
  verifyPrimaryAdministrator(username, subject);
  return { username, subject };
}

export type OwnedNotification = {
  notificationId: string;
  sourceEventId: string;
  recipientEmployeeId: string;
};

export function discoverNotifications(options: {
  recipientEmployeeId: string;
  projectId?: string;
  taskId?: string;
  reportId?: string;
}): OwnedNotification[] {
  const recipient = checkedUuid(
    options.recipientEmployeeId,
    "notification recipient ID",
  );
  const predicates = [`recipient_employee_id=${sqlLiteral(recipient)}::uuid`];
  for (const [column, value] of [
    ["project_id", options.projectId],
    ["task_id", options.taskId],
    ["report_id", options.reportId],
  ] as const) {
    if (value)
      predicates.push(
        `${column}=${sqlLiteral(checkedUuid(value, column))}::uuid`,
      );
  }
  const rows = sql(
    "notification-db",
    "notification",
    "notification",
    `select id::text || '|' || source_event_id::text || '|' || recipient_employee_id::text from notifications where ${predicates.join(" and ")} order by id;`,
  );
  return rows
    ? rows.split(/\r?\n/).map((row) => {
        const [notificationId, sourceEventId, recipientEmployeeId] =
          row.split("|");
        return {
          notificationId: checkedUuid(notificationId, "notification ID"),
          sourceEventId: checkedUuid(
            sourceEventId,
            "notification source event ID",
          ),
          recipientEmployeeId: checkedUuid(
            recipientEmployeeId,
            "notification recipient ID",
          ),
        };
      })
    : [];
}

export function deleteNotification(item: OwnedNotification) {
  compose([
    "exec",
    "-T",
    "notification",
    "python",
    "-m",
    "app.development_cleanup",
    "--notification-id",
    checkedUuid(item.notificationId, "notification ID"),
    "--source-event-id",
    checkedUuid(item.sourceEventId, "source event ID"),
    "--recipient-employee-id",
    checkedUuid(item.recipientEmployeeId, "recipient ID"),
  ]);
}

export function discoverReportJobs(
  marker: string,
  projectId: string,
): string[] {
  const rows = sql(
    "job-db",
    "job",
    "job",
    `select id::text from jobs where related_project_id=${sqlLiteral(checkedUuid(projectId, "project ID"))}::uuid and idempotency_key=${sqlLiteral(marker)} order by id;`,
  );
  return rows
    ? rows.split(/\r?\n/).map((id) => checkedUuid(id, "report job ID"))
    : [];
}

export function discoverOwnedReportByWindow(options: {
  projectId: string;
  submitterEmployeeId: string;
  createdAfter: string;
  createdBefore: string;
}): string {
  const projectId = checkedUuid(options.projectId, "report project ID");
  const submitter = checkedUuid(
    options.submitterEmployeeId,
    "report submitter ID",
  );
  const after = new Date(options.createdAfter);
  const before = new Date(options.createdBefore);
  if (
    Number.isNaN(after.valueOf()) ||
    Number.isNaN(before.valueOf()) ||
    after >= before ||
    before.valueOf() - after.valueOf() > 300_000
  )
    throw new Error("Report discovery window is invalid.");
  const rows = sql(
    "job-db",
    "job",
    "job",
    `select id::text from jobs where related_project_id=${sqlLiteral(projectId)}::uuid and submitter_employee_id=${sqlLiteral(submitter)}::uuid and job_type='PROJECT_TASK_EXPORT' and created_at >= ${sqlLiteral(after.toISOString())}::timestamptz and created_at <= ${sqlLiteral(before.toISOString())}::timestamptz order by created_at,id;`,
  );
  const ids = rows
    ? rows.split(/\r?\n/).map((id) => checkedUuid(id, "owned report ID"))
    : [];
  if (ids.length !== 1)
    throw new Error("The bounded report ownership query was not unique.");
  return ids[0];
}

export function deleteJob(jobId: string) {
  compose([
    "exec",
    "-T",
    "job",
    "python",
    "-m",
    "app.development_cleanup",
    checkedUuid(jobId, "job ID"),
  ]);
}

export function assertNoOneOffContainers(marker: string) {
  const names = compose(["ps", "-a", "--format", "json"]);
  if (names.toLowerCase().includes(marker.toLowerCase()))
    throw new Error("A current-run one-off container remains.");
}

export function assertOwnedRowsRemoved(options: {
  projectKey: string;
  projectId?: string;
  taskIds?: string[];
  jobIds?: string[];
  notificationIds?: string[];
  sourceEventIds?: string[];
  jobDomainEventIds?: string[];
  workOutboxEventIds?: string[];
}) {
  const uuidList = (values: string[] | undefined, label: string) =>
    values?.length
      ? values
          .map((value) => `${sqlLiteral(checkedUuid(value, label))}::uuid`)
          .join(",")
      : "null";
  const taskIds = uuidList(options.taskIds, "task ID");
  const jobIds = uuidList(options.jobIds, "job ID");
  const notificationIds = uuidList(options.notificationIds, "notification ID");
  const sourceIds = uuidList(options.sourceEventIds, "source event ID");
  const jobDomainEventIds = uuidList(
    options.jobDomainEventIds,
    "Job domain event ID",
  );
  const workOutboxIds = uuidList(
    options.workOutboxEventIds,
    "Work outbox event ID",
  );
  const project = options.projectId
    ? `${sqlLiteral(checkedUuid(options.projectId, "project ID"))}::uuid`
    : "null";
  const counts = [
    sql(
      "notification-db",
      "notification",
      "notification",
      `select count(*) from notifications where id in (${notificationIds});`,
    ),
    sql(
      "notification-db",
      "notification",
      "notification",
      `select count(*) from notification_source_events where id in (${sourceIds});`,
    ),
    sql(
      "work-db",
      "work",
      "work",
      `select count(*) from work_outbox_events where id in (${workOutboxIds}) or task_id in (${taskIds}) or project_id=${project};`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from job_domain_outbox where job_id in (${jobIds});`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from job_domain_outbox where id in (${jobDomainEventIds});`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from job_attempts where job_id in (${jobIds});`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from jobs where id in (${jobIds}) and result_content is not null;`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from job_publication_outbox where job_id in (${jobIds});`,
    ),
    sql(
      "job-db",
      "job",
      "job",
      `select count(*) from jobs where id in (${jobIds});`,
    ),
    sql(
      "work-db",
      "work",
      "work",
      `select count(*) from tasks where id in (${taskIds});`,
    ),
    sql(
      "work-db",
      "work",
      "work",
      `select count(*) from projects where key=${sqlLiteral(options.projectKey)};`,
    ),
  ];
  if (counts.some((count) => count !== "0"))
    throw new Error("Current-run owned rows remain.");
  assertNoOneOffContainers(options.projectKey);
}
