import { expect, test } from "@playwright/test";
import { getIsolatedRecoveryHelper } from "./isolated-recovery-helper";

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

  const helper = getIsolatedRecoveryHelper();
  const baseURL = helper.getBaseUrl();

  const gql = async (query: string, variables: object = {}) =>
    (
      await page.request.post("/graphql", { data: { query, variables } })
    ).json();

  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL(new URL("/", baseURL).toString());

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

    helper.stopService("job-worker");
    helper.stopService("job-recovery");

    await gql(
      "mutation D($id: ID!, $version: Int!) { dispatchJob(jobId: $id, expectedVersion: $version) { status } }",
      { id: jobId, version: submitted.version },
    );

    let publicationStatus = "UNKNOWN";
    try {
      await expect
        .poll(
          async () => {
            const res = await gql(
              "query J($id: ID!) { job(id: $id) { publication { status } } }",
              { id: jobId },
            );
            publicationStatus =
              res?.data?.job?.publication?.status ?? "UNKNOWN";
            return publicationStatus;
          },
          { timeout: 30_000, message: "JOB_PUBLICATION_DID_NOT_SETTLE" },
        )
        .toBe("PUBLISHED");
    } catch {
      throw new Error(
        `PUBLICATION_FAILURE: Outbox event publication did not settle (status='${publicationStatus}').`,
      );
    }

    helper.pauseService("work");
    helper.startService("job-worker");

    let runningJobSnapshot:
      | {
          status?: string;
          publication?: { status?: string };
          attempts?: Array<{ status?: string; leaseExpiresAt?: string }>;
        }
      | undefined;

    try {
      await expect
        .poll(
          async () => {
            const res = await gql(
              "query J($id: ID!) { job(id: $id) { status publication { status } attempts { status leaseExpiresAt } } }",
              { id: jobId },
            );
            runningJobSnapshot = res?.data?.job;
            return runningJobSnapshot;
          },
          { timeout: 30_000, message: "WORKER_CLAIM_TIMEOUT" },
        )
        .toMatchObject({
          status: "RUNNING",
          attempts: [{ status: "RUNNING" }],
        });
    } catch {
      const pubStatus =
        runningJobSnapshot?.publication?.status ?? publicationStatus;
      const currentJobStatus = runningJobSnapshot?.status ?? "UNKNOWN";
      const attemptCount = runningJobSnapshot?.attempts?.length ?? 0;
      const firstAttemptStatus =
        runningJobSnapshot?.attempts?.[0]?.status ?? "NONE";

      if (pubStatus !== "PUBLISHED") {
        throw new Error(
          `PUBLICATION_FAILURE: Publication was not PUBLISHED when verifying worker claim (status='${pubStatus}').`,
        );
      }
      throw new Error(
        `WORKER_CLAIM_FAILURE: Worker failed to claim job into RUNNING state (jobStatus='${currentJobStatus}', attempts=${attemptCount}, firstAttemptStatus='${firstAttemptStatus}').`,
      );
    }

    // Confirm exact run-owned Job has a persisted RUNNING attempt before stopping the worker
    expect(runningJobSnapshot?.status).toBe("RUNNING");
    expect(runningJobSnapshot?.attempts).toHaveLength(1);
    expect(runningJobSnapshot?.attempts?.[0]?.status).toBe("RUNNING");
    expect(runningJobSnapshot?.attempts?.[0]?.leaseExpiresAt).toBeTruthy();

    helper.stopService("job-worker", 0);
    helper.unpauseService("work");

    let claimed:
      | {
          data?: {
            job?: {
              status: string;
              attempts: Array<{ status: string; leaseExpiresAt: string }>;
            };
          };
        }
      | undefined;

    await expect
      .poll(
        async () => {
          claimed = await gql(
            "query J($id: ID!) { job(id: $id) { status attempts { status leaseExpiresAt } } }",
            { id: jobId },
          );
          return claimed?.data?.job;
        },
        { timeout: 15_000, message: "PERSISTED_RUNNING_CLAIM_TIMEOUT" },
      )
      .toMatchObject({
        status: "RUNNING",
        attempts: [{ status: "RUNNING" }],
      });

    expect(claimed!.data!.job!.status).toBe("RUNNING");
    expect(claimed!.data!.job!.attempts).toHaveLength(1);
    expect(claimed!.data!.job!.attempts[0].status).toBe("RUNNING");
    const leaseExpiresAt = claimed!.data!.job!.attempts[0].leaseExpiresAt;
    expect(leaseExpiresAt).toBeTruthy();

    await expect
      .poll(() => Date.now(), { timeout: 45_000 })
      .toBeGreaterThan(Date.parse(leaseExpiresAt));

    helper.startService("job-recovery");
    await helper.waitForHealthy("job-recovery");

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

    const persistedBeforeRestart = helper.sql(
      "job-db",
      "job",
      "job",
      `SELECT (SELECT count(*) FROM job_attempts WHERE job_id='${jobId}' AND status='ABANDONED'),(SELECT count(*) FROM job_publication_outbox WHERE job_id='${jobId}'),(SELECT count(*) FROM jobs WHERE id='${jobId}' AND result_content IS NOT NULL);`,
    );
    expect(persistedBeforeRestart).toBe("1|2|0");

    helper.startService("job-worker");
    await helper.waitForHealthy("job-worker");

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

    const persistedAfterRecovery = helper.sql(
      "job-db",
      "job",
      "job",
      `SELECT (SELECT count(*) FROM job_attempts WHERE job_id='${jobId}'),(SELECT count(*) FROM job_publication_outbox WHERE job_id='${jobId}'),(SELECT count(*) FROM jobs WHERE id='${jobId}' AND result_content IS NOT NULL);`,
    );
    expect(persistedAfterRecovery).toBe("2|2|1");

    await page.goto(`/jobs/${jobId}`);
    await expect(page.getByText("Export result")).toBeVisible();
    expect(await page.locator("text=/Attempt [12]/").count()).toBe(2);
    await page.reload();
    await expect(page.getByText("Export result")).toBeVisible();
    expect(await page.locator("text=/Attempt [12]/").count()).toBe(2);
  } finally {
    try {
      helper.unpauseService("work");
    } catch {
      // ignore if already unpaused
    }
    try {
      helper.startService("job-recovery");
      helper.startService("job-worker");
      await helper.waitForHealthy("job-recovery").catch(() => undefined);
      await helper.waitForHealthy("job-worker").catch(() => undefined);
    } catch {
      // best-effort restart
    }
    if (jobId) {
      try {
        helper.composeExec("job", [
          "python",
          "-m",
          "app.development_cleanup",
          jobId,
        ]);
      } catch {
        // cleanup best effort
      }
    }
    if (projectId) {
      try {
        helper.composeExec("work", [
          "python",
          "-m",
          "app.development_cleanup",
          "--project-id",
          projectId,
          "--expected-key",
          projectKey,
        ]);
      } catch {
        // cleanup best effort
      }
    }
  }
});
