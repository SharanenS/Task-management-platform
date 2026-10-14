import { expect, test, type Page } from "@playwright/test";

const adminUsername = process.env.DEV_USER_USERNAME;
const adminPassword = process.env.DEV_USER_PASSWORD;
const employeeUsername = process.env.PHASE3_E2E_USERNAME;
const employeeEmail = process.env.PHASE3_E2E_EMAIL;
const employeeDisplayName = process.env.PHASE3_E2E_DISPLAY_NAME;
const temporaryPassword = process.env.PHASE3_E2E_TEMP_PASSWORD;
const employeePassword = process.env.PHASE3_E2E_PASSWORD;
const enabled =
  process.env.RUN_EMPLOYEE_ADMIN_E2E === "1" &&
  adminUsername &&
  adminPassword &&
  employeeUsername &&
  employeeEmail &&
  employeeDisplayName &&
  temporaryPassword &&
  employeePassword;

async function login(page: Page, username: string, password: string) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: /ADMIN|MANAGER|MEMBER/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signed-out$/);
}

test("ADMIN provisions, governs, and safely deactivates a disposable employee", async ({
  page,
}) => {
  test.skip(
    !enabled,
    "Set RUN_EMPLOYEE_ADMIN_E2E=1 and disposable credentials.",
  );
  test.setTimeout(180_000);

  await login(page, adminUsername!, adminPassword!);
  await expect(page).toHaveURL("http://localhost:3010/");
  await page.getByRole("link", { name: "Employees", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Employees" })).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Provision employee" }).click();
  await page.getByLabel(/^Username/).fill(employeeUsername!);
  await page.getByLabel("Email").fill(employeeEmail!);
  await page.getByLabel("Display name").fill(employeeDisplayName!);
  await page.getByLabel(/^Temporary password/).fill(temporaryPassword!);
  await page.getByRole("button", { name: "Provision employee" }).click();
  await expect(page.getByText("Employee provisioned")).toBeVisible();
  await page.getByRole("link", { name: "View employee" }).click();
  await expect(page).toHaveURL(/\/employees\/[0-9a-f-]+$/);
  const detailUrl = page.url();
  await expect(page.getByText(employeeEmail!)).toBeVisible();
  await logout(page);

  await login(page, employeeUsername!, temporaryPassword!);
  await expect(page.locator("#password-new")).toBeVisible();
  await page.locator("#password-new").fill(employeePassword!);
  await page.locator("#password-confirm").fill(employeePassword!);
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page).toHaveURL("http://localhost:3010/");
  await expect(
    page.getByRole("link", { name: "Employees", exact: true }),
  ).toHaveCount(0);
  const denied = await page.request.post("/graphql", {
    data: { query: "query { employees(first: 1) { nodes { id } } }" },
  });
  expect((await denied.json()).errors[0].extensions.code).toBe("FORBIDDEN");
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).concat(Object.keys(sessionStorage)),
    ),
  ).toEqual([]);
  await logout(page);

  await login(page, adminUsername!, adminPassword!);
  await page.goto(detailUrl);
  await page.getByRole("button", { name: "Deactivate employee" }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Inactive", { exact: true })).toBeVisible();
  await logout(page);

  await login(page, employeeUsername!, employeePassword!);
  await expect(page).not.toHaveURL("http://localhost:3010/");
  await page.context().clearCookies();

  await login(page, adminUsername!, adminPassword!);
  await page.goto(detailUrl);
  await page.getByRole("button", { name: "Activate employee" }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Active", { exact: true })).toBeVisible();
  await logout(page);

  await login(page, employeeUsername!, employeePassword!);
  await expect(page).toHaveURL("http://localhost:3010/");
  await logout(page);

  await login(page, adminUsername!, adminPassword!);
  await page.goto(detailUrl);
  await page.getByRole("button", { name: "Deactivate employee" }).click();
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("Inactive", { exact: true })).toBeVisible();
});
