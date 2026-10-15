import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled = process.env.RUN_PROJECT_E2E === "1" && username && password;

async function signIn(page: Page) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
}

test.describe("Docker-backed project management", () => {
  test.skip(!enabled, "Set RUN_PROJECT_E2E=1 and development credentials.");
  test.describe.configure({ mode: "serial" });

  test("administrator completes a disposable project lifecycle", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const marker = Date.now().toString(36).toUpperCase();
    const key = `E2E-${marker}`;
    let projectId: string | undefined;

    try {
      await signIn(page);
      const navigationButton = page.getByRole("button", {
        name: "Open navigation",
      });
      if (await navigationButton.isVisible()) {
        await navigationButton.click();
        await expect(
          page.getByRole("dialog", { name: "Navigation" }),
        ).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(navigationButton).toBeFocused();
      }
      await page.goto("/projects");
      await expect(
        page.getByRole("heading", { name: "Projects" }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Create project" }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      ).toBe(true);

      await page.getByRole("link", { name: "Create project" }).click();
      await page.getByLabel("Project key").fill(key);
      await page.getByLabel("Name").fill(`Disposable ${marker}`);
      await page.getByLabel("Description").fill("Test-owned project");
      await page.getByRole("button", { name: "Create project" }).click();
      await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);
      projectId = page.url().split("/").at(-1);
      await expect(page.getByText(key, { exact: true })).toBeVisible();

      await page.getByRole("button", { name: "Activate project" }).click();
      await expect(page.getByText("ACTIVE", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Archive project" }).click();
      await expect(page.getByText("ARCHIVED", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Reactivate project" }).click();
      await expect(page.getByText("ACTIVE", { exact: true })).toBeVisible();

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
