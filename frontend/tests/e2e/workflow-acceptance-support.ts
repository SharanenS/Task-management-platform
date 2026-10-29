import { execFileSync } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function sqlLiteral(value: string): string {
  return `'${value.replaceAll("'", "''")}'`;
}

export function uuid(value: string, label: string): string {
  if (!UUID_PATTERN.test(value)) throw new Error(`${label} is not a UUID.`);
  return value;
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
    throw new Error("The scoped Compose operation failed.");
  }
}

export function sql(
  service: string,
  user: string,
  database: string,
  query: string,
): string {
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

export class Cleanup {
  private readonly failures: string[] = [];

  async stage(label: string, action: () => void | Promise<void>) {
    try {
      await action();
    } catch (error) {
      const diagnostic =
        error instanceof Error &&
        /^[A-Za-z0-9 .:_()-]{1,160}$/.test(error.message)
          ? error.message
          : "scoped operation failed";
      this.failures.push(`${label}: ${diagnostic}`);
    }
  }

  finish() {
    if (this.failures.length)
      throw new Error(`Cleanup failed: ${this.failures.join("; ")}`);
  }
}

export type ExecutionLink = {
  executionId: string;
  idempotencyKey: string;
  jobIds: string[];
};

export function discoverOwnedExecutionJobs(options: {
  ruleId?: string;
  projectId?: string;
  taskId?: string;
  projectKey: string;
  ruleName: string;
  taskTitle: string;
}): ExecutionLink[] {
  const projectRows = sql(
    "work-db",
    "work",
    "work",
    `select id::text from projects where key=${sqlLiteral(options.projectKey)};`,
  );
  if (!projectRows) return [];
  const markerProjectIds = projectRows
    .split(/\r?\n/)
    .map((value) => uuid(value, "marker project ID"));
  if (markerProjectIds.length !== 1)
    throw new Error("The project marker does not identify one owned project.");
  const markerProjectId = markerProjectIds[0];
  const taskRows = sql(
    "work-db",
    "work",
    "work",
    `select id::text from tasks where project_id=${sqlLiteral(markerProjectId)}::uuid and title=${sqlLiteral(options.taskTitle)};`,
  );
  const markerTaskIds = taskRows
    ? taskRows.split(/\r?\n/).map((value) => uuid(value, "marker task ID"))
    : [];
  if (markerTaskIds.length > 1)
    throw new Error("The task marker identifies ambiguous owned tasks.");
  const predicates = [
    `r.name=${sqlLiteral(options.ruleName)}`,
    `e.project_id=${sqlLiteral(markerProjectId)}::uuid`,
  ];
  if (markerTaskIds[0])
    predicates.push(`e.task_id=${sqlLiteral(markerTaskIds[0])}::uuid`);
  if (options.ruleId)
    predicates.push(
      `e.rule_id=${sqlLiteral(uuid(options.ruleId, "rule ID"))}::uuid`,
    );
  if (options.projectId)
    predicates.push(
      `e.project_id=${sqlLiteral(uuid(options.projectId, "project ID"))}::uuid`,
    );
  if (options.taskId)
    predicates.push(
      `e.task_id=${sqlLiteral(uuid(options.taskId, "task ID"))}::uuid`,
    );
  const rows = sql(
    "workflow-db",
    "workflow",
    "workflow",
    `select e.id::text || '|' || coalesce(e.resulting_job_id::text,'')
       from workflow_executions e
       join workflow_rules r on r.id=e.rule_id
      where ${predicates.join(" and ")};`,
  );
  if (!rows) return [];
  if (markerTaskIds.length !== 1)
    throw new Error("The execution task marker is missing or ambiguous.");
  const actorRows = sql(
    "work-db",
    "work",
    "work",
    `select distinct actor_employee_id::text from work_outbox_events where project_id=${sqlLiteral(markerProjectId)}::uuid and task_id=${sqlLiteral(markerTaskIds[0])}::uuid and event_type='TASK_COMPLETED';`,
  );
  const actors = actorRows
    ? actorRows.split(/\r?\n/).map((value) => uuid(value, "event actor ID"))
    : [];
  if (actors.length !== 1)
    throw new Error("The execution actor scope is missing or ambiguous.");
  const actorId = actors[0];
  return rows.split(/\r?\n/).map((row) => {
    const [rawExecutionId, rawLinkedJobId] = row.split("|");
    const executionId = uuid(rawExecutionId, "execution ID");
    const linkedJobId = rawLinkedJobId
      ? uuid(rawLinkedJobId, "resulting job ID")
      : undefined;
    const idempotencyKey = `workflow:${executionId}`;
    const jobRows = sql(
      "job-db",
      "job",
      "job",
      `select id::text || '|' || submitter_employee_id::text || '|' || coalesce(related_project_id::text,'') || '|' || coalesce((payload->>'projectId'),'') from jobs where idempotency_key=${sqlLiteral(idempotencyKey)} order by id;`,
    );
    const jobIds = jobRows
      ? jobRows.split(/\r?\n/).map((jobRow) => {
          const [rawJobId, submitterId, relatedProjectId, payloadProjectId] =
            jobRow.split("|");
          const jobId = uuid(rawJobId, "idempotency-key job ID");
          if (
            uuid(submitterId, "job submitter ID") !== actorId ||
            uuid(relatedProjectId, "related project ID") !== markerProjectId ||
            uuid(payloadProjectId, "payload project ID") !== markerProjectId
          )
            throw new Error("The deterministic job ownership scope disagrees.");
          return jobId;
        })
      : [];
    if (linkedJobId && !jobIds.includes(linkedJobId))
      throw new Error("The linked job and deterministic key disagree.");
    return { executionId, idempotencyKey, jobIds };
  });
}

export async function waitForHealthy(service: string, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const output = compose(["ps", "--format", "json", service]).trim();
      const parsed = JSON.parse(output) as
        | { Health?: string; State?: string }
        | Array<{ Health?: string; State?: string }>;
      const records = Array.isArray(parsed) ? parsed : [parsed];
      if (
        records.length === 1 &&
        records[0].State === "running" &&
        records[0].Health === "healthy"
      )
        return;
    } catch {
      // The bounded poll reports one fixed error only after the deadline.
    }
    await delay(1_000);
  }
  throw new Error(`${service} did not become healthy within the bounded wait.`);
}

export function deleteJob(jobId: string) {
  compose([
    "exec",
    "-T",
    "job",
    "python",
    "-m",
    "app.development_cleanup",
    uuid(jobId, "job ID"),
  ]);
}
