import { execFileSync } from "node:child_process";

import { expect, test, type Page } from "@playwright/test";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled = process.env.RUN_TASK_E2E === "1" && username && password;

async function signIn(page: Page) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
}

test.describe("Docker-backed task management", () => {
  test.skip(!enabled, "Set RUN_TASK_E2E=1 and development credentials.");
  test.describe.configure({ mode: "serial" });

  test("administrator completes a disposable task lifecycle", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    const marker = Date.now().toString(36).toUpperCase();
    const key = `T5-${marker}`;
    let projectId: string | undefined;

    try {
      await signIn(page);
      const created = await page.request.post("/graphql", {
        data: {
          query:
            "mutation Create($input: CreateProjectInput!) { createProject(input: $input) { id } }",
          variables: { input: { key, name: `Tasks ${marker}` } },
        },
      });
      const body = await created.json();
      expect(body.errors).toBeUndefined();
      projectId = body.data.createProject.id;

      await page.goto(`/projects/${projectId}`);
      await page.getByRole("link", { name: "View tasks" }).click();
      await expect(page).toHaveURL(`/projects/${projectId}/tasks`);
      await expect(
        page.getByRole("heading", { name: "Tasks", exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      ).toBe(true);
      await page.getByRole("link", { name: "Create task" }).click();
      await page.getByLabel("Title").fill(`Review ${marker}`);
      await page.getByLabel("Description").fill("Disposable task");
      await page.getByLabel("Priority").selectOption("HIGH");
      await page.getByRole("button", { name: "Create task" }).click();
      await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]+$/);
      await expect(page.getByText(`${key}-1`, { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "IN_PROGRESS" }).click();
      await expect(
        page.getByText("IN_PROGRESS", { exact: true }).first(),
      ).toBeVisible();
      await expect(page.getByText(/Version 2\./)).toBeVisible();
      await page.getByLabel("Add comment").fill("Lifecycle comment");
      await page.getByRole("button", { name: "Add comment" }).click();
      await expect(page.getByText("Lifecycle comment")).toBeVisible();
      await expect(page.getByText("COMMENT_ADDED")).toBeVisible();
      await page.getByRole("link", { name: "← Tasks", exact: true }).click();
      await page.getByRole("button", { name: "Board view" }).click();
      await expect(page.getByText(`Review ${marker}`)).toBeVisible();
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).concat(Object.keys(sessionStorage)),
        ),
      ).toEqual([]);
    } finally {
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
            key,
          ],
          { cwd: "..", stdio: "pipe" },
        );
      }
    }
  });
});
