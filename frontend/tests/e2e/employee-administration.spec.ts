import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const adminUsername = process.env.DEV_USER_USERNAME;
const adminPassword = process.env.DEV_USER_PASSWORD;
const employeeUsername = process.env.PHASE3_E2E_USERNAME;
const employeeEmail = process.env.PHASE3_E2E_EMAIL;
const employeeDisplayName = process.env.PHASE3_E2E_DISPLAY_NAME;
const temporaryPassword = process.env.PHASE3_E2E_TEMP_PASSWORD;
const employeePassword = process.env.PHASE3_E2E_PASSWORD;
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_EMPLOYEE_ADMIN_E2E === "1" &&
  adminUsername &&
  adminPassword &&
  employeeUsername &&
  employeeEmail &&
  employeeDisplayName &&
  temporaryPassword &&
  employeePassword &&
  process.env.KEYCLOAK_ADMIN_USERNAME &&
  process.env.KEYCLOAK_ADMIN_PASSWORD;

function docker(args: string[]) {
  const result = spawnSync("docker", ["compose", "-f", composeFile, ...args], {
    encoding: "utf8",
    windowsHide: true,
    env: process.env,
  });
  if (result.status !== 0)
    throw new Error("Disposable identity command failed.");
  return result.stdout;
}

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
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in disposable Employee lifecycle runs on desktop; responsive coverage is separate.",
  );
  test.setTimeout(180_000);
  const marker = Date.now().toString(36).toLowerCase();
  const username = `${employeeUsername}-${marker}`;
  const [emailLocal, emailDomain] = employeeEmail!.split("@", 2);
  const email = `${emailLocal}+${marker}@${emailDomain}`;
  let subject: string | undefined;
  let primarySubject: string | undefined;

  try {
    await login(page, adminUsername!, adminPassword!);
    await expect(page).toHaveURL("http://localhost:3010/");
    await page.getByRole("link", { name: "Employees", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Employees" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    await page.getByRole("link", { name: "Provision employee" }).click();
    await page.getByLabel(/^Username/).fill(username);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Display name").fill(employeeDisplayName!);
    await page.getByLabel(/^Temporary password/).fill(temporaryPassword!);
    await page.getByRole("button", { name: "Provision employee" }).click();
    await expect(page.getByText("Employee provisioned")).toBeVisible();
    await page.getByRole("link", { name: "View employee" }).click();
    await expect(page).toHaveURL(/\/employees\/[0-9a-f-]+$/);
    const detailUrl = page.url();
    await expect(page.getByText(email)).toBeVisible();

    docker([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "config",
      "credentials",
      "--server",
      "http://localhost:8080",
      "--realm",
      "master",
      "--user",
      process.env.KEYCLOAK_ADMIN_USERNAME!,
      "--password",
      process.env.KEYCLOAK_ADMIN_PASSWORD!,
    ]);
    const created = JSON.parse(
      docker([
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "get",
        "users",
        "-r",
        "taskspace",
        "-q",
        `username=${username}`,
      ]),
    );
    expect(created).toHaveLength(1);
    expect(created[0].username).toBe(username);
    subject = created[0].id;
    await logout(page);

    await login(page, username, temporaryPassword!);
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

    await login(page, username, employeePassword!);
    await expect(page).not.toHaveURL("http://localhost:3010/");
    await page.context().clearCookies();

    await login(page, adminUsername!, adminPassword!);
    await page.goto(detailUrl);
    await page.getByRole("button", { name: "Activate employee" }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("Active", { exact: true })).toBeVisible();
    await logout(page);

    await login(page, username, employeePassword!);
    await expect(page).toHaveURL("http://localhost:3010/");
    await logout(page);

    await login(page, adminUsername!, adminPassword!);
    await page.goto(detailUrl);
    await page.getByRole("button", { name: "Deactivate employee" }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("Inactive", { exact: true })).toBeVisible();
  } finally {
    docker([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "config",
      "credentials",
      "--server",
      "http://localhost:8080",
      "--realm",
      "master",
      "--user",
      process.env.KEYCLOAK_ADMIN_USERNAME!,
      "--password",
      process.env.KEYCLOAK_ADMIN_PASSWORD!,
    ]);
    const primary = JSON.parse(
      docker([
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "get",
        "users",
        "-r",
        "taskspace",
        "-q",
        `username=${adminUsername}`,
      ]),
    );
    if (primary.length !== 1)
      throw new Error("Primary identity lookup failed.");
    primarySubject = primary[0].id;
    if (!subject) {
      const created = JSON.parse(
        docker([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "get",
          "users",
          "-r",
          "taskspace",
          "-q",
          `username=${username}`,
        ]),
      );
      if (created.length === 1 && created[0].username === username) {
        subject = created[0].id;
      }
    }
    if (subject) {
      docker([
        "exec",
        "-T",
        "employee",
        "python",
        "-m",
        "app.development_access",
        "remove",
        "--subject",
        subject,
        "--protected-subject",
        primarySubject!,
      ]);
      docker([
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "delete",
        `users/${subject}`,
        "-r",
        "taskspace",
      ]);
    }
  }
});
