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
  let primarySubject: string | undefined;
  const contexts: Array<{ close(): Promise<void> }> = [];

  try {
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
    );
    expect(users).toHaveLength(1);
    subject = users[0].id;
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
        `username=${env.DEV_USER_USERNAME}`,
      ]),
    );
    expect(primary).toHaveLength(1);
    primarySubject = primary[0].id;
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
    for (const context of contexts.reverse()) await context.close();
    if (subject && primarySubject) {
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
