import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_JOB_RECOVERY_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("expired execution recovers after recovery-process outage", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in Phase 9 recovery journey",
  );
  test.setTimeout(180_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 60_000,
      windowsHide: true,
    });
  const container = (...args: string[]) =>
    execute("docker", args, { timeout: 60_000, windowsHide: true });
  const waitHealthy = async (service: string) =>
    expect
      .poll(
        async () => {
          const output = (
            await compose("ps", "--format", "json", service)
          ).stdout.trim();
          return output
            ? JSON.parse(output.split(/\r?\n/)[0]).Health
            : "missing";
        },
        { timeout: 60_000 },
      )
      .toBe("healthy");
  const gql = async (query: string, variables: object = {}) =>
    (
      await page.request.post("/graphql", { data: { query, variables } })
    ).json();

  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");

  const marker = Date.now().toString(36).toUpperCase();
  const projectKey = `J9-${marker}`;
  let projectId: string | undefined;
  let jobId: string | undefined;
  try {
    projectId = (
      await gql(
        "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        {
          input: { key: projectKey, name: `Recovery ${marker}` },
        },
      )
    ).data.createProject.id;
    const submitted = (
      await gql(
        "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id version } }",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: `phase9-recovery-${marker.toLowerCase()}`,
          },
        },
      )
    ).data.submitProjectTaskExport;
    jobId = submitted.id;
    await compose("stop", "job-worker", "job-recovery");
    await gql(
      "mutation D($id: ID!, $version: Int!) { dispatchJob(jobId: $id, expectedVersion: $version) { status } }",
      { id: jobId, version: submitted.version },
    );
    await expect
      .poll(
        async () =>
          (
            await gql(
              "query J($id: ID!) { job(id: $id) { publication { status } } }",
              {
                id: jobId,
              },
            )
          ).data.job.publication.status,
      )
      .toBe("PUBLISHED");
    await container("pause", "enterprise-task-platform-phase2-work-1");
    await container("start", "enterprise-task-platform-phase2-job-worker-1");
    await expect
      .poll(
        async () =>
          (
            await gql(
              "query J($id: ID!) { job(id: $id) { status attempts { status leaseExpiresAt } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 30_000 },
      )
      .toMatchObject({ status: "RUNNING", attempts: [{ status: "RUNNING" }] });
    await container("stop", "enterprise-task-platform-phase2-job-worker-1");
    await container("unpause", "enterprise-task-platform-phase2-work-1");
    const claimed = await gql(
      "query J($id: ID!) { job(id: $id) { status attempts { status leaseExpiresAt } } }",
      { id: jobId },
    );
    expect(claimed.data.job.status).toBe("RUNNING");
    expect(claimed.data.job.attempts).toHaveLength(1);
    await expect
      .poll(() => Date.now(), { timeout: 45_000 })
      .toBeGreaterThan(Date.parse(claimed.data.job.attempts[0].leaseExpiresAt));
    await compose("start", "job-recovery");
    await waitHealthy("job-recovery");
    await expect
      .poll(
        async () =>
          (
            await gql(
              "query J($id: ID!) { job(id: $id) { status executionGeneration attempts { status recoveredAt } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 60_000 },
      )
      .toMatchObject({
        status: "QUEUED",
        executionGeneration: 2,
        attempts: [{ status: "ABANDONED" }],
      });
    const persistedBeforeRestart = (
      await compose(
        "exec",
        "-T",
        "job-db",
        "psql",
        "-U",
        "job",
        "-d",
        "job",
        "-Atc",
        `SELECT (SELECT count(*) FROM job_attempts WHERE job_id='${jobId}' AND status='ABANDONED'),(SELECT count(*) FROM job_publication_outbox WHERE job_id='${jobId}'),(SELECT count(*) FROM jobs WHERE id='${jobId}' AND result_content IS NOT NULL);`,
      )
    ).stdout.trim();
    expect(persistedBeforeRestart).toBe("1|2|0");
    await compose("start", "job-worker");
    await waitHealthy("job-worker");
    await expect
      .poll(
        async () =>
          (
            await gql(
              "query J($id: ID!) { job(id: $id) { status attempts { status recoveredAt } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 60_000 },
      )
      .toMatchObject({
        status: "SUCCEEDED",
        attempts: [{ status: "ABANDONED" }, { status: "SUCCEEDED" }],
      });
    const persistedAfterRecovery = (
      await compose(
        "exec",
        "-T",
        "job-db",
        "psql",
        "-U",
        "job",
        "-d",
        "job",
        "-Atc",
        `SELECT (SELECT count(*) FROM job_attempts WHERE job_id='${jobId}'),(SELECT count(*) FROM job_publication_outbox WHERE job_id='${jobId}'),(SELECT count(*) FROM jobs WHERE id='${jobId}' AND result_content IS NOT NULL);`,
      )
    ).stdout.trim();
    expect(persistedAfterRecovery).toBe("2|2|1");
    await page.goto(`/jobs/${jobId}`);
    await expect(page.getByText("Export result")).toBeVisible();
    expect(await page.locator("text=/Attempt [12]/").count()).toBe(2);
    await page.reload();
    await expect(page.getByText("Export result")).toBeVisible();
    expect(await page.locator("text=/Attempt [12]/").count()).toBe(2);
  } finally {
    await container("unpause", "enterprise-task-platform-phase2-work-1").catch(
      () => undefined,
    );
    await compose("start", "job-recovery", "job-worker");
    await waitHealthy("job-recovery");
    await waitHealthy("job-worker");
    if (jobId)
      await compose(
        "exec",
        "-T",
        "job",
        "python",
        "-m",
        "app.development_cleanup",
        jobId,
      );
    if (projectId)
      await compose(
        "exec",
        "-T",
        "work",
        "python",
        "-m",
        "app.development_cleanup",
        "--project-id",
        projectId,
        "--expected-key",
        projectKey,
      );
  }
});
