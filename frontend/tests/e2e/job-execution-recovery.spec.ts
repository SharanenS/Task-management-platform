import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_JOB_EXECUTION_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("worker and broker outages preserve durable execution and recover", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in isolated RabbitMQ and worker outage check",
  );
  test.setTimeout(240_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 60_000,
      windowsHide: true,
    });
  expect(
    JSON.parse((await compose("config", "--format", "json")).stdout).name,
  ).toBe("enterprise-task-platform-phase2");
  const gql = async (query: string, variables: object = {}) =>
    (
      await page.request.post("/graphql", {
        data: { query, variables },
      })
    ).json();
  const waitForHealthy = async (service: string) => {
    await expect
      .poll(
        async () => {
          const result = await compose("ps", "--format", "json", service);
          const rows = result.stdout
            .trim()
            .split(/\r?\n/)
            .filter(Boolean)
            .map((row) => JSON.parse(row));
          return rows[0]?.Health;
        },
        { timeout: 60_000 },
      )
      .toBe("healthy");
  };
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");

  const marker = Date.now().toString(36).toUpperCase();
  const projectKey = `J7-${marker}`;
  let projectId: string | undefined;
  const jobIds: string[] = [];
  const submit =
    "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id status version } }";
  const dispatch =
    "mutation D($id: ID!, $version: Int!) { dispatchJob(jobId: $id, expectedVersion: $version) { id status version } }";
  const status =
    "query J($id: ID!) { job(id: $id) { id status version attempts { status } } }";
  try {
    const project = await gql(
      "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
      { input: { key: projectKey, name: `Execution recovery ${marker}` } },
    );
    projectId = project.data.createProject.id;

    const workerJob = await gql(submit, {
      input: {
        projectId,
        includeCompleted: true,
        idempotencyKey: `phase7-worker-${marker.toLowerCase()}`,
      },
    });
    const workerId = workerJob.data.submitProjectTaskExport.id;
    jobIds.push(workerId);
    await compose("stop", "job-worker");
    const queued = await gql(dispatch, {
      id: workerId,
      version: workerJob.data.submitProjectTaskExport.version,
    });
    expect(queued.data.dispatchJob.status).toBe("QUEUED");
    expect((await gql(status, { id: workerId })).data.job.attempts).toEqual([]);
    await compose(
      "exec",
      "-T",
      "job",
      "python",
      "-c",
      "import sys; from uuid import UUID; from app.publisher import publisher; publisher().publish(UUID(sys.argv[1])); publisher().publish(UUID(sys.argv[1]))",
      workerId,
    );
    await compose("start", "job-worker");
    await waitForHealthy("job-worker");
    await expect
      .poll(async () => (await gql(status, { id: workerId })).data.job.status, {
        timeout: 60_000,
      })
      .toBe("SUCCEEDED");
    const duplicateResult = (await gql(status, { id: workerId })).data.job;
    expect(duplicateResult.attempts).toEqual([{ status: "SUCCEEDED" }]);

    const brokerJob = await gql(submit, {
      input: {
        projectId,
        includeCompleted: false,
        idempotencyKey: `phase7-broker-${marker.toLowerCase()}`,
      },
    });
    const brokerId = brokerJob.data.submitProjectTaskExport.id;
    jobIds.push(brokerId);
    await compose("stop", "rabbitmq");
    const unavailable = await gql(dispatch, {
      id: brokerId,
      version: brokerJob.data.submitProjectTaskExport.version,
    });
    expect(unavailable.errors[0]).toEqual({
      message: "Job dispatch is temporarily unavailable.",
      extensions: { code: "BROKER_UNAVAILABLE" },
    });
    expect(JSON.stringify(unavailable)).not.toMatch(
      /rabbitmq|amqp|password|Traceback|OperationalError/i,
    );
    const retained = (await gql(status, { id: brokerId })).data.job;
    expect(retained.status).toBe("SUBMITTED");
    await compose("start", "rabbitmq");
    await waitForHealthy("rabbitmq");
    await compose("restart", "job-worker");
    await waitForHealthy("job-worker");
    const recovered = await gql(dispatch, {
      id: brokerId,
      version: retained.version,
    });
    expect(recovered.errors).toBeUndefined();
    await expect
      .poll(async () => (await gql(status, { id: brokerId })).data.job.status, {
        timeout: 60_000,
      })
      .toBe("SUCCEEDED");
  } finally {
    await compose("start", "rabbitmq", "job-worker");
    await waitForHealthy("rabbitmq");
    await waitForHealthy("job-worker");
    for (const jobId of jobIds)
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
