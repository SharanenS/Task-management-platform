import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_JOB_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("Job Service persists, sanitizes outage, and recovers idempotently", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in isolated Job outage check",
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
  const projectKey = `JR-${marker}`;
  const idempotencyKey = `phase6-e2e-recovery-${marker.toLowerCase()}`;
  let projectId: string | undefined;
  let jobId: string | undefined;
  const operation =
    "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id status } }";
  const waitForJob = async () => {
    await expect
      .poll(
        async () => {
          const result = await page.request.post("/graphql", {
            data: { query: "query { jobs(first: 1) { nodes { id } } }" },
          });
          return (await result.json()).data?.jobs?.nodes !== undefined;
        },
        { timeout: 60_000 },
      )
      .toBe(true);
  };
  try {
    const projectResponse = await page.request.post("/graphql", {
      data: {
        query:
          "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        variables: {
          input: { key: projectKey, name: `Job recovery ${marker}` },
        },
      },
    });
    projectId = (await projectResponse.json()).data.createProject.id;
    const input = { projectId, includeCompleted: true, idempotencyKey };
    const submitted = await page.request.post("/graphql", {
      data: { query: operation, variables: { input } },
    });
    jobId = (await submitted.json()).data.submitProjectTaskExport.id;

    await compose("restart", "job");
    await waitForJob();
    const persisted = await page.request.post("/graphql", {
      data: {
        query: "query J($id: ID!) { job(id: $id) { id status } }",
        variables: { id: jobId },
      },
    });
    expect((await persisted.json()).data.job).toEqual({
      id: jobId,
      status: "SUBMITTED",
    });

    await compose("stop", "job");
    const unavailable = await page.request.post("/graphql", {
      data: { query: "query { jobs(first: 1) { nodes { id } } }" },
    });
    const unavailableBody = await unavailable.json();
    expect(unavailableBody.errors[0]).toEqual({
      message: "Job management is temporarily unavailable.",
      extensions: { code: "SERVICE_UNAVAILABLE" },
    });
    expect(JSON.stringify(unavailableBody)).not.toMatch(
      /job:8040|Traceback|ECONNREFUSED|database/i,
    );

    await compose("start", "job");
    await waitForJob();
    const replay = await page.request.post("/graphql", {
      data: { query: operation, variables: { input } },
    });
    expect((await replay.json()).data.submitProjectTaskExport.id).toBe(jobId);
  } finally {
    await compose("start", "job");
    await waitForJob();
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
    if (projectId) {
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
  }
});
