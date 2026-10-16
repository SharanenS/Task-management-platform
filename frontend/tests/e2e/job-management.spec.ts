import { execFileSync } from "node:child_process";

import { expect, test, type Page } from "@playwright/test";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled = process.env.RUN_JOB_E2E === "1" && username && password;

async function signIn(page: Page) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
}

async function gql(page: Page, query: string, variables: object = {}) {
  const response = await page.request.post("/graphql", {
    data: { query, variables },
  });
  return response.json();
}

test.describe("Docker-backed job management", () => {
  test.skip(!enabled, "Set RUN_JOB_E2E=1 and development credentials.");
  test.describe.configure({ mode: "serial" });

  test("administrator submits and inspects durable jobs without execution", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    const marker = Date.now().toString(36).toUpperCase();
    const projectKey = `J6-${marker}`;
    let projectId: string | undefined;
    const jobIds: string[] = [];
    try {
      await signIn(page);
      const project = await gql(
        page,
        "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        { input: { key: projectKey, name: `Job project ${marker}` } },
      );
      expect(project.errors).toBeUndefined();
      projectId = project.data.createProject.id;

      await page.goto("/jobs/new");
      await page.getByLabel("Project UUID").fill(projectId!);
      await page.getByRole("button", { name: "Submit job" }).click();
      await expect(page).toHaveURL(/\/jobs\/[0-9a-f-]+$/);
      jobIds.push(page.url().split("/").at(-1)!);
      await expect(page.getByText("SUBMITTED", { exact: true })).toBeVisible();
      await expect(page.getByText("Format").locator("..")).toContainText("CSV");
      await expect(
        page.getByText(
          "No execution attempts yet. Worker execution is introduced in Phase 7.",
        ),
      ).toBeVisible();
      await expect(
        page.getByText(/Dispatch, retry, cancellation/),
      ).toBeVisible();
      await page.reload();
      await expect(page.getByText("SUBMITTED", { exact: true })).toBeVisible();
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).concat(Object.keys(sessionStorage)),
        ),
      ).toEqual([]);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      ).toBe(true);

      const idempotencyKey = `phase6-e2e-${marker.toLowerCase()}`;
      const operation =
        "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id status } }";
      const input = { projectId, includeCompleted: true, idempotencyKey };
      const first = await gql(page, operation, { input });
      const replay = await gql(page, operation, { input });
      expect(first.errors).toBeUndefined();
      expect(replay.data.submitProjectTaskExport.id).toBe(
        first.data.submitProjectTaskExport.id,
      );
      jobIds.push(first.data.submitProjectTaskExport.id);
      const conflict = await gql(page, operation, {
        input: { ...input, includeCompleted: false },
      });
      expect(conflict.errors[0]).toEqual({
        message: "The idempotency key is already in use.",
        extensions: { code: "IDEMPOTENCY_CONFLICT" },
      });
      await page.goto("/jobs");
      await expect(page.getByText("Project task export").first()).toBeVisible();
    } finally {
      for (const jobId of jobIds) {
        execFileSync(
          "docker",
          [
            "compose",
            "exec",
            "-T",
            "job",
            "python",
            "-m",
            "app.development_cleanup",
            jobId,
          ],
          { cwd: "..", stdio: "pipe" },
        );
      }
      if (projectId) {
        execFileSync(
          "docker",
          [
            "compose",
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
          ],
          { cwd: "..", stdio: "pipe" },
        );
      }
    }
  });
});
