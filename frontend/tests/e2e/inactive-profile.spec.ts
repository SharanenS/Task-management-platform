import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Browser, type Page } from "@playwright/test";

const env = process.env;
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  env.RUN_INACTIVE_PROFILE_E2E === "1" &&
  env.DEV_USER_USERNAME &&
  env.DEV_USER_PASSWORD &&
  env.PHASE4_E2E_TEMP_PASSWORD &&
  env.PHASE4_E2E_PASSWORD &&
  env.KEYCLOAK_ADMIN_USERNAME &&
  env.KEYCLOAK_ADMIN_PASSWORD;

function docker(args: string[]) {
  const result = spawnSync("docker", ["compose", "-f", composeFile, ...args], {
    encoding: "utf8",
    windowsHide: true,
    env,
  });
  if (result.status !== 0)
    throw new Error("Disposable identity command failed.");
  return result.stdout;
}

function configureKeycloakAdmin() {
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
    env.KEYCLOAK_ADMIN_USERNAME!,
    "--password",
    env.KEYCLOAK_ADMIN_PASSWORD!,
  ]);
}

function exactKeycloakUsers(username: string) {
  const users = JSON.parse(
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
  ) as Array<{ id: string; username: string; enabled?: boolean }>;
  return users.filter((user) => user.username === username);
}

function checkedUuid(value: string | undefined, label: string) {
  if (
    !value ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  )
    throw new Error(`${label} was not a UUID.`);
  return value;
}

function sqlLiteral(value: string) {
  return `'${value.replaceAll("'", "''")}'`;
}

function employeeSql(sql: string) {
  return docker([
    "exec",
    "-T",
    "employee-db",
    "psql",
    "-U",
    "employee",
    "-d",
    "employee",
    "-At",
    "-c",
    sql,
  ]).trim();
}

async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}

async function login(browser: Browser, username: string, password: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("http://localhost:3010/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  return { context, page };
}

test.describe.configure({ mode: "serial" });

test("a disposable inactive profile is denied without an application session", async ({
  browser,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in inactive-profile journey requires ignored disposable credentials.",
  );
  test.setTimeout(120_000);
  const marker = Date.now().toString(36).toLowerCase();
  const username = `inactive-${marker}`;
  const email = `inactive-${marker}@example.test`;
  let subject: string | undefined;
  let employeeId: string | undefined;
  let primarySubject: string | undefined;
  let ownershipVerified = false;
  const contexts: Array<{ close(): Promise<void> }> = [];

  try {
    configureKeycloakAdmin();
    const primaryUsers = exactKeycloakUsers(env.DEV_USER_USERNAME!);
    if (primaryUsers.length !== 1 || !primaryUsers[0].enabled)
      throw new Error("Protected primary identity verification failed.");
    primarySubject = checkedUuid(
      primaryUsers[0].id,
      "Protected primary subject",
    );
    if (exactKeycloakUsers(username).length !== 0)
      throw new Error("Generated inactive-profile username already exists.");

    const admin = await login(
      browser,
      env.DEV_USER_USERNAME!,
      env.DEV_USER_PASSWORD!,
    );
    contexts.push(admin.context);
    await expect(admin.page).toHaveURL("http://localhost:3010/");
    const provisioned = await gql(
      admin.page,
      "mutation P($input: ProvisionEmployeeInput!) { provisionEmployee(input: $input) { id } }",
      {
        input: {
          idempotencyKey: `inactive-${marker}`,
          username,
          email,
          displayName: `Inactive ${marker}`,
          role: "MEMBER",
          active: true,
          temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD,
        },
      },
    );
    expect(provisioned.errors).toBeUndefined();
    employeeId = checkedUuid(
      provisioned.data.provisionEmployee.id,
      "Disposable Employee ID",
    );
    const users = exactKeycloakUsers(username);
    if (users.length !== 1)
      throw new Error("Disposable inactive identity ownership is ambiguous.");
    subject = checkedUuid(users[0].id, "Disposable Keycloak subject");
    const employeeLink = employeeSql(
      `SELECT count(*) FROM employees WHERE id=${sqlLiteral(employeeId)} AND keycloak_subject=${sqlLiteral(subject)} AND username=${sqlLiteral(username)};`,
    );
    if (employeeLink !== "1")
      throw new Error("Disposable Employee subject link verification failed.");
    ownershipVerified = true;
    expect(subject).not.toBe(primarySubject);
    docker([
      "exec",
      "-T",
      "employee",
      "python",
      "-m",
      "app.development_access",
      "set-active",
      "--subject",
      subject!,
      "--active",
      "false",
      "--protected-subject",
      primarySubject!,
    ]);

    const denied = await login(
      browser,
      username,
      env.PHASE4_E2E_TEMP_PASSWORD!,
    );
    contexts.push(denied.context);
    await denied.page.locator("#password-new").fill(env.PHASE4_E2E_PASSWORD!);
    await denied.page
      .locator("#password-confirm")
      .fill(env.PHASE4_E2E_PASSWORD!);
    await denied.page.getByRole("button", { name: "Submit" }).click();
    await expect(denied.page).toHaveURL("http://localhost:3010/access-denied");
    await expect(
      denied.page.getByRole("heading", {
        name: "Workspace access unavailable",
      }),
    ).toBeVisible();
    await expect(
      denied.page.getByText(
        "Your identity is valid, but no active employee profile is linked to this account. Contact an administrator if you believe this is unexpected.",
      ),
    ).toBeVisible();
    expect(
      (await denied.context.cookies()).some(
        (cookie) => cookie.name === "taskspace.session",
      ),
    ).toBe(false);
  } finally {
    const cleanupFailures: string[] = [];
    const cleanup = async (
      label: string,
      action: () => unknown | Promise<unknown>,
    ) => {
      try {
        await action();
      } catch {
        cleanupFailures.push(label);
      }
    };

    for (const [index, context] of contexts.reverse().entries())
      await cleanup(`close browser context ${index + 1}`, () =>
        context.close(),
      );
    await cleanup("configure Keycloak administration", () =>
      configureKeycloakAdmin(),
    );
    await cleanup("remove exact inactive Employee profile", () => {
      if (!subject || !employeeId || !primarySubject || !ownershipVerified)
        return;
      if (subject === primarySubject)
        throw new Error("Refusing to remove the protected primary subject.");
      const link = employeeSql(
        `SELECT count(*) FROM employees WHERE id=${sqlLiteral(employeeId)} AND keycloak_subject=${sqlLiteral(subject)} AND username=${sqlLiteral(username)};`,
      );
      if (link !== "1") {
        ownershipVerified = false;
        throw new Error("Disposable Employee ownership is ambiguous.");
      }
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
        primarySubject,
      ]);
    });
    await cleanup("remove exact inactive Keycloak identity", () => {
      if (!subject || !primarySubject || !ownershipVerified) return;
      if (subject === primarySubject)
        throw new Error("Refusing to remove the protected primary subject.");
      const users = exactKeycloakUsers(username);
      if (users.length !== 1 || users[0].id !== subject)
        throw new Error("Disposable Keycloak ownership is ambiguous.");
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
    });
    await cleanup("verify current-run identity cleanup", () => {
      const profileCount = employeeSql(
        `SELECT count(*) FROM employees WHERE username=${sqlLiteral(username)};`,
      );
      if (profileCount !== "0" || exactKeycloakUsers(username).length !== 0)
        throw new Error("Current-run inactive identity remains after cleanup.");
    });
    await cleanup("verify protected primary administrator", () => {
      if (!primarySubject) throw new Error("Primary subject was not recorded.");
      const primaryUsers = exactKeycloakUsers(env.DEV_USER_USERNAME!);
      if (
        primaryUsers.length !== 1 ||
        primaryUsers[0].id !== primarySubject ||
        !primaryUsers[0].enabled
      )
        throw new Error("Protected primary Keycloak identity changed.");
      const profile = employeeSql(
        `SELECT count(*) FROM employees WHERE username=${sqlLiteral(env.DEV_USER_USERNAME!)} AND keycloak_subject=${sqlLiteral(primarySubject)} AND active IS TRUE AND role='ADMIN';`,
      );
      if (profile !== "1")
        throw new Error("Protected primary Employee profile changed.");
    });
    if (cleanupFailures.length)
      throw new Error(
        `Cleanup or integrity checks failed: ${cleanupFailures.join(", ")}`,
      );
  }
});
