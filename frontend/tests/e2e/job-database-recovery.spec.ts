import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_JOB_DATABASE_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });
test("Job PostgreSQL failure does not poison an idempotency key", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in isolated Job PostgreSQL outage check",
  );
  test.setTimeout(180_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 60_000,
      windowsHide: true,
    });
  expect(
    JSON.parse((await compose("config", "--format", "json")).stdout).name,
  ).toBe("enterprise-task-platform-phase2");

  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");

  const marker = Date.now().toString(36).toUpperCase();
  const projectKey = `JD-${marker}`;
  const idempotencyKey = `phase6-db-recovery-${marker.toLowerCase()}`;
  let projectId: string | undefined;
  let jobId: string | undefined;
  const operation =
    "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id status } }";
  const request = async (input: object) =>
    (
      await page.request.post("/graphql", {
        data: { query: operation, variables: { input } },
      })
    ).json();
  const waitForJobs = async () => {
    await expect
      .poll(
        async () => {
          try {
            const response = await page.request.post("/graphql", {
              data: { query: "query { jobs(first: 1) { nodes { id } } }" },
            });
            return (await response.json()).data?.jobs?.nodes !== undefined;
          } catch {
            return false;
          }
        },
        { timeout: 60_000 },
      )
      .toBe(true);
  };

  try {
    const project = await page.request.post("/graphql", {
      data: {
        query:
          "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        variables: {
          input: { key: projectKey, name: `Job database recovery ${marker}` },
        },
      },
    });
    projectId = (await project.json()).data.createProject.id;
    const input = { projectId, includeCompleted: true, idempotencyKey };

    await compose("stop", "job-db");
    const unavailable = await request(input);
    expect(unavailable.errors[0]).toEqual({
      message: "Job management is temporarily unavailable.",
      extensions: { code: "SERVICE_UNAVAILABLE" },
    });
    expect(JSON.stringify(unavailable)).not.toMatch(
      /job-db|5432|Traceback|OperationalError|psycopg|password/i,
    );
    await expect(page).not.toHaveURL(/\/jobs\/[0-9a-f-]+$/);

    await compose("start", "job-db");
    await waitForJobs();
    const submitted = await request(input);
    expect(submitted.errors).toBeUndefined();
    jobId = submitted.data.submitProjectTaskExport.id;
    expect(submitted.data.submitProjectTaskExport.status).toBe("SUBMITTED");
    const replay = await request(input);
    expect(replay.data.submitProjectTaskExport.id).toBe(jobId);
    const conflict = await request({ ...input, includeCompleted: false });
    expect(conflict.errors[0]).toEqual({
      message: "The idempotency key is already in use.",
      extensions: { code: "IDEMPOTENCY_CONFLICT" },
    });
    const matches = await page.request.post("/graphql", {
      data: {
        query: "query { jobs(first: 50) { nodes { id } } }",
      },
    });
    expect(
      (await matches.json()).data.jobs.nodes.filter(
        (job: { id: string }) => job.id === jobId,
      ),
    ).toHaveLength(1);
  } finally {
    await compose("start", "job-db", "job");
    await waitForJobs();
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
