import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";

import {
  Cleanup,
  compose,
  deleteJob,
  discoverOwnedExecutionJobs,
  sql,
  sqlLiteral,
  uuid,
} from "./workflow-acceptance-support";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled =
  process.env.RUN_WORKFLOW_DUPLICATE_E2E === "1" && username && password;
async function signIn(page: Page) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
}
async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}
test.describe("Workflow duplicate RabbitMQ delivery", () => {
  test.skip(
    !enabled,
    "Set RUN_WORKFLOW_DUPLICATE_E2E=1 and development credentials.",
  );
  test.describe.configure({ mode: "serial" });
  test("duplicate RabbitMQ delivery creates one execution and one logical job", async ({
    page,
  }, info) => {
    test.skip(
      info.project.name !== "desktop",
      "Destructive duplicate-delivery acceptance runs once on desktop.",
    );
    test.setTimeout(180_000);
    const marker = Date.now().toString(36).toUpperCase();
    const projectKey = `W10-${marker}`;
    const ruleName = `Workflow ${marker}`;
    const taskTitle = `Workflow task ${marker}`;
    let projectId: string | undefined;
    let taskId: string | undefined;
    let ruleId: string | undefined;
    let jobId: string | undefined;
    try {
      await signIn(page);
      const project = await gql(
        page,
        "mutation C($input:CreateProjectInput!){createProject(input:$input){id}}",
        { input: { key: projectKey, name: `Workflow project ${marker}` } },
      );
      expect(project.errors).toBeUndefined();
      projectId = project.data.createProject.id;
      uuid(projectId!, "project ID");
      const task = await gql(
        page,
        "mutation T($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id version}}",
        {
          projectId,
          input: { title: taskTitle, priority: "MEDIUM" },
        },
      );
      expect(task.errors).toBeUndefined();
      taskId = task.data.createTask.id;
      uuid(taskId!, "task ID");
      const started = await gql(
        page,
        "mutation S($projectId:ID!,$taskId:ID!){changeTaskStatus(projectId:$projectId,taskId:$taskId,status:IN_PROGRESS,expectedVersion:1){id version}}",
        { projectId, taskId },
      );
      expect(started.errors).toBeUndefined();
      await page.goto("/workflows/new");
      await page.getByLabel("Rule name").fill(ruleName);
      await page.getByLabel("Project UUID").fill(projectId!);
      await page.getByRole("button", { name: "Create rule" }).click();
      await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]+$/);
      ruleId = page.url().split("/").at(-1)!;
      uuid(ruleId, "workflow rule ID");
      await page.goto(`/projects/${projectId}/tasks/${taskId}`);
      await page.getByRole("button", { name: "DONE" }).click();
      await expect(
        page.getByText("DONE", { exact: true }).first(),
      ).toBeVisible();
      const eventPayload = execFileSync(
        "docker",
        [
          "compose",
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select json_build_object('eventId',id,'schemaVersion',schema_version,'eventType',event_type,'projectId',project_id,'taskId',task_id,'actorEmployeeId',actor_employee_id,'taskVersion',task_version,'occurredAt',created_at) from work_outbox_events where task_id='${taskId}'::uuid;`,
        ],
        { cwd: "..", encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
      ).trim();
      expect(eventPayload).toBeTruthy();
      const committedEvent = JSON.parse(eventPayload) as {
        eventId: string;
        actorEmployeeId: string;
      };
      uuid(committedEvent.eventId, "Work event ID");
      uuid(committedEvent.actorEmployeeId, "event actor ID");
      const encoded = Buffer.from(eventPayload, "utf8").toString("base64");
      execFileSync(
        "docker",
        [
          "compose",
          "exec",
          "-T",
          "-e",
          `WORKFLOW_DUPLICATE_PAYLOAD=${encoded}`,
          "workflow",
          "python",
          "-c",
          "import base64,json,os;from kombu import Connection,Exchange,Producer;p=json.loads(base64.b64decode(os.environ['WORKFLOW_DUPLICATE_PAYLOAD']));c=Connection(os.environ['RABBITMQ_URL']);x=Exchange('work.domain',type='direct',durable=True);q=Producer(c);q.publish(p,exchange=x,routing_key='work.task.completed.v1',serializer='json',declare=[x],delivery_mode=2);q.publish(p,exchange=x,routing_key='work.task.completed.v1',serializer='json',declare=[x],delivery_mode=2);c.release()",
        ],
        {
          cwd: "..",
          stdio: "pipe",
          env: process.env,
        },
      );
      await expect
        .poll(
          async () => {
            const result = await gql(
              page,
              "query E($id:ID!){workflowRule(id:$id){id}workflowExecutions(first:10,ruleId:$id){nodes{id status resultingJobId}}}",
              { id: ruleId },
            );
            const nodes = result.data?.workflowExecutions?.nodes ?? [];
            if (nodes.length === 1 && nodes[0].resultingJobId) {
              jobId = nodes[0].resultingJobId;
              uuid(jobId!, "resulting job ID");
            }
            return nodes.length === 1 ? nodes[0].status : "NONE";
          },
          { timeout: 60_000 },
        )
        .toBe("SUCCEEDED");
      expect(jobId).toBeTruthy();
      await expect
        .poll(
          async () => {
            const result = await gql(
              page,
              "query J($id:ID!){job(id:$id){status}}",
              { id: jobId },
            );
            return result.data?.job?.status;
          },
          { timeout: 60_000 },
        )
        .toBe("SUCCEEDED");
      expect(
        sql(
          "workflow-db",
          "workflow",
          "workflow",
          `select count(*) from workflow_source_events where id='${committedEvent.eventId}'::uuid;`,
        ),
      ).toBe("1");
      const executionRow = sql(
        "workflow-db",
        "workflow",
        "workflow",
        `select id::text || '|' || resulting_job_id::text from workflow_executions where rule_id=${sqlLiteral(uuid(ruleId!, "rule ID"))}::uuid and task_id=${sqlLiteral(uuid(taskId!, "task ID"))}::uuid;`,
      );
      const [executionId, linkedJobId] = executionRow.split("|");
      uuid(executionId, "execution ID");
      expect(uuid(linkedJobId, "linked job ID")).toBe(
        uuid(jobId!, "observed job ID"),
      );
      const idempotencyKey = `workflow:${executionId}`;
      const deterministicJobs = sql(
        "job-db",
        "job",
        "job",
        `select id::text || '|' || coalesce(related_project_id::text,'') || '|' || coalesce((payload->>'projectId'),'') from jobs where idempotency_key=${sqlLiteral(idempotencyKey)} and submitter_employee_id=${sqlLiteral(uuid(committedEvent.actorEmployeeId, "actor employee ID"))}::uuid order by id;`,
      )
        .split(/\r?\n/)
        .filter(Boolean);
      expect(deterministicJobs).toHaveLength(1);
      const [deterministicJobId, relatedProjectId, payloadProjectId] =
        deterministicJobs[0].split("|");
      expect(uuid(deterministicJobId, "deterministic job ID")).toBe(
        linkedJobId,
      );
      expect(uuid(relatedProjectId, "related project ID")).toBe(projectId);
      expect(uuid(payloadProjectId, "payload project ID")).toBe(projectId);
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from jobs where idempotency_key=${sqlLiteral(idempotencyKey)};`,
        ),
      ).toBe("1");
      expect(
        sql(
          "workflow-db",
          "workflow",
          "workflow",
          `select count(*) from workflow_executions where rule_id='${ruleId}'::uuid and task_id='${taskId}'::uuid;`,
        ),
      ).toBe("1");
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from job_attempts where job_id=${sqlLiteral(jobId!)}::uuid and status='SUCCEEDED';`,
        ),
      ).toBe("1");
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from jobs where id=${sqlLiteral(jobId!)}::uuid and result_content is not null and result_checksum is not null and result_content_type='text/csv; charset=utf-8';`,
        ),
      ).toBe("1");
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from job_publication_outbox where job_id=${sqlLiteral(jobId!)}::uuid and execution_generation=1 and event_type='EXECUTE_JOB' and status='PUBLISHED';`,
        ),
      ).toBe("1");
      await page.goto(`/workflows/${ruleId}`);
      await expect(
        page.getByRole("link", { name: "Open resulting job" }),
      ).toHaveAttribute("href", `/jobs/${jobId}`);
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).concat(Object.keys(sessionStorage)),
        ),
      ).toEqual([]);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth + 1,
        ),
      ).toBe(true);
    } finally {
      const cleanup = new Cleanup();
      const discoveredJobIds = new Set<string>();
      const discoveredJobKeys = new Set<string>();
      await cleanup.stage("discover execution and job links", () => {
        for (const link of discoverOwnedExecutionJobs({
          ruleId,
          projectId,
          taskId,
          projectKey,
          ruleName,
          taskTitle,
        })) {
          discoveredJobKeys.add(link.idempotencyKey);
          for (const id of link.jobIds) discoveredJobIds.add(id);
        }
      });
      await cleanup.stage("delete exact workflow jobs", () => {
        for (const id of discoveredJobIds) deleteJob(id);
      });
      await cleanup.stage("delete exact workflow rule", () => {
        const ownedRuleId =
          ruleId ??
          sql(
            "workflow-db",
            "workflow",
            "workflow",
            `select id::text from workflow_rules where name=${sqlLiteral(ruleName)};`,
          );
        const ownedProjectId =
          projectId ??
          sql(
            "work-db",
            "work",
            "work",
            `select id::text from projects where key=${sqlLiteral(projectKey)};`,
          );
        if (!ownedRuleId && !ownedProjectId) return;
        if (!ownedRuleId || !ownedProjectId)
          throw new Error("Rule cleanup ownership is incomplete.");
        compose([
          "exec",
          "-T",
          "workflow",
          "python",
          "-m",
          "app.development_cleanup",
          "--rule-id",
          uuid(ownedRuleId, "rule ID"),
          "--expected-project-id",
          uuid(ownedProjectId, "project ID"),
          "--expected-name",
          ruleName,
        ]);
      });
      await cleanup.stage("delete exact Work project", () => {
        const ownedProjectId =
          projectId ??
          sql(
            "work-db",
            "work",
            "work",
            `select id::text from projects where key=${sqlLiteral(projectKey)};`,
          );
        if (ownedProjectId)
          compose([
            "exec",
            "-T",
            "work",
            "python",
            "-m",
            "app.development_cleanup",
            "--project-id",
            uuid(ownedProjectId, "project ID"),
            "--expected-key",
            projectKey,
          ]);
      });
      await cleanup.stage("independent marker zero counts", () => {
        const counts = [
          sql(
            "workflow-db",
            "workflow",
            "workflow",
            `select count(*) from workflow_rules where name=${sqlLiteral(ruleName)};`,
          ),
          sql(
            "workflow-db",
            "workflow",
            "workflow",
            `select count(*) from workflow_executions where task_id=${taskId ? `${sqlLiteral(uuid(taskId, "task ID"))}::uuid` : "null"};`,
          ),
          sql(
            "workflow-db",
            "workflow",
            "workflow",
            `select count(*) from workflow_source_events where task_id=${taskId ? `${sqlLiteral(uuid(taskId, "task ID"))}::uuid` : "null"};`,
          ),
          sql(
            "work-db",
            "work",
            "work",
            `select count(*) from work_outbox_events where task_id in (select t.id from tasks t join projects p on p.id=t.project_id where p.key=${sqlLiteral(projectKey)} and t.title=${sqlLiteral(taskTitle)});`,
          ),
          sql(
            "work-db",
            "work",
            "work",
            `select count(*) from tasks t join projects p on p.id=t.project_id where p.key=${sqlLiteral(projectKey)} and t.title=${sqlLiteral(taskTitle)};`,
          ),
          sql(
            "work-db",
            "work",
            "work",
            `select count(*) from projects where key=${sqlLiteral(projectKey)};`,
          ),
          sql(
            "job-db",
            "job",
            "job",
            `select count(*) from jobs where idempotency_key in (${[...discoveredJobKeys].map(sqlLiteral).join(",") || "null"});`,
          ),
          sql(
            "job-db",
            "job",
            "job",
            `select count(*) from job_attempts where job_id in (${[...discoveredJobIds].map((id) => `${sqlLiteral(uuid(id, "job ID"))}::uuid`).join(",") || "null"});`,
          ),
          sql(
            "job-db",
            "job",
            "job",
            `select count(*) from jobs where id in (${[...discoveredJobIds].map((id) => `${sqlLiteral(uuid(id, "job ID"))}::uuid`).join(",") || "null"}) and result_content is not null;`,
          ),
          sql(
            "job-db",
            "job",
            "job",
            `select count(*) from job_publication_outbox where job_id in (${[...discoveredJobIds].map((id) => `${sqlLiteral(uuid(id, "job ID"))}::uuid`).join(",") || "null"});`,
          ),
        ];
        if (counts.some((count) => count !== "0"))
          throw new Error("Current-run marker rows remain.");
      });
      await cleanup.stage("one-off container zero count", () => {
        if (
          compose(["ps", "-a", "--services"])
            .split(/\r?\n/)
            .filter((name) => name.startsWith(`w10-${marker.toLowerCase()}`))
            .length
        )
          throw new Error("Current-run one-off containers remain.");
      });
      cleanup.finish();
    }
  });
});
