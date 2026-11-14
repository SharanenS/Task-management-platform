import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_JOB_PUBLICATION_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("publisher outage preserves intent and recovers automatically", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in publisher recovery check",
  );
  test.setTimeout(180_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 60_000,
      windowsHide: true,
    });
  const gql = async (query: string, variables: object = {}) =>
    (
      await page.request.post("/graphql", { data: { query, variables } })
    ).json();
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
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
  const marker = Date.now().toString(36).toUpperCase();
  const projectKey = `J8-${marker}`;
  let projectId: string | undefined;
  let jobId: string | undefined;
  try {
    projectId = (
      await gql(
        "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        { input: { key: projectKey, name: `Publisher recovery ${marker}` } },
      )
    ).data.createProject.id;
    const submitted = (
      await gql(
        "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id version } }",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: `phase8-publisher-${marker.toLowerCase()}`,
          },
        },
      )
    ).data.submitProjectTaskExport;
    jobId = submitted.id;
    await compose("stop", "job-publisher");
    const dispatched = await gql(
      "mutation D($id: ID!, $version: Int!) { dispatchJob(jobId: $id, expectedVersion: $version) { status publication { status } } }",
      { id: jobId, version: submitted.version },
    );
    expect(dispatched.data.dispatchJob).toEqual({
      status: "QUEUED",
      publication: { status: "PENDING" },
    });
    await compose("stop", "job-db");
    await compose("start", "job-publisher");
    await expect
      .poll(
        async () => {
          const output = (
            await compose("ps", "--format", "json", "job-publisher")
          ).stdout.trim();
          return output
            ? JSON.parse(output.split(/\r?\n/)[0]).Health
            : "missing";
        },
        { timeout: 30_000 },
      )
      .not.toBe("healthy");
    await compose("start", "job-db");
    await waitHealthy("job-db");
    await compose("start", "job", "job-publisher");
    await waitHealthy("job");
    await waitHealthy("job-publisher");
    await expect
      .poll(
        async () =>
          (
            await gql(
              "query J($id: ID!) { job(id: $id) { status publication { status } attempts { status } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 60_000 },
      )
      .toMatchObject({
        status: "SUCCEEDED",
        publication: { status: "PUBLISHED" },
        attempts: [{ status: "SUCCEEDED" }],
      });
  } finally {
    await compose("start", "job-db");
    await waitHealthy("job-db");
    await compose("start", "job", "job-publisher");
    await waitHealthy("job");
    await waitHealthy("job-publisher");
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
