import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const authenticated = process.env.RUN_AUTH_E2E === "1" && username && password;

function startKeycloakAndWait() {
  execFileSync(
    "docker",
    ["compose", "up", "-d", "--wait", "--wait-timeout", "90", "keycloak"],
    { cwd: "..", stdio: "ignore", timeout: 100_000 },
  );
}

async function signIn(page: Page) {
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in\?returnTo=%2F$/);
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");
  await expect(
    page.getByRole("heading", { name: "Make room for great work." }),
  ).toBeVisible();
}

test("an unauthenticated protected route redirects to sign in", async ({
  page,
}) => {
  await page.goto("/system?source=acceptance");
  await expect(page).toHaveURL(
    /\/sign-in\?returnTo=%2Fsystem%3Fsource%3Dacceptance$/,
  );
  await expect(
    page.getByRole("heading", { name: "Sign in to your workspace" }),
  ).toBeVisible();
});

test.describe("Docker-backed authentication", () => {
  test.skip(!authenticated, "Set RUN_AUTH_E2E=1 and development credentials.");

  test("login, employee identity, GraphQL, storage, and logout", async ({
    page,
  }) => {
    await signIn(page);

    await page.getByRole("button", { name: /Local User|ADMIN/ }).click();
    await expect(page.getByRole("menu")).toContainText("ADMIN");
    await expect(page.getByRole("menu")).toContainText(
      "local.user@example.test",
    );
    await expect(
      page.getByText("Gateway connected", { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => ({
        local: Object.keys(localStorage),
        session: Object.keys(sessionStorage),
      })),
    ).toEqual({ local: [], session: [] });

    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/signed-out$/);
    await expect(
      page.getByRole("heading", { name: "You are signed out" }),
    ).toBeVisible();
    await page.goto("/");
    await expect(page).toHaveURL(/\/sign-in/);
  });

  test("an expired access token refreshes without exposing a new browser token", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    test.skip(
      process.env.RUN_AUTH_REFRESH_E2E !== "1",
      "Slow refresh check is opt-in.",
    );
    await signIn(page);
    await page.waitForTimeout(65_000);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Make room for great work." }),
    ).toBeVisible();
    expect(
      await page.evaluate(() =>
        Object.keys(localStorage).concat(Object.keys(sessionStorage)),
      ),
    ).toEqual([]);
  });
});

test("an authenticated identity without an active employee is denied", async ({
  page,
}) => {
  test.skip(
    process.env.RUN_ACCESS_DENIED_E2E !== "1" || !username || !password,
    "The profile-state integration check is opt-in.",
  );
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/access-denied");
  await expect(
    page.getByRole("heading", { name: "Workspace access unavailable" }),
  ).toBeVisible();
});

test("refresh failure expires the session and recovers after Keycloak returns", async ({
  page,
}) => {
  test.setTimeout(120_000);
  test.skip(
    process.env.RUN_AUTH_FAILURE_E2E !== "1" || !username || !password,
    "The real identity-service outage check is opt-in.",
  );
  await signIn(page);
  await page.route("**/graphql", (route) => route.abort("blockedbyclient"));
  await page.waitForTimeout(65_000);
  try {
    execFileSync("docker", ["compose", "stop", "keycloak"], {
      cwd: "..",
      stdio: "ignore",
    });
    await page.goto(`/system?refreshFailure=${Date.now()}`);
    await expect(page).toHaveURL("http://localhost:3010/session-expired");
    await expect(
      page.getByRole("heading", { name: "Your session has expired" }),
    ).toBeVisible();
  } finally {
    startKeycloakAndWait();
  }
  await expect
    .poll(
      async () => {
        try {
          const response = await fetch(
            "http://localhost:8080/realms/taskspace/.well-known/openid-configuration",
          );
          return response.ok;
        } catch {
          return false;
        }
      },
      { timeout: 30_000 },
    )
    .toBe(true);
});

test("login reports a Keycloak outage and recovers after restart", async ({
  page,
}) => {
  test.setTimeout(120_000);
  test.skip(
    process.env.RUN_LOGIN_OUTAGE_E2E !== "1",
    "The login-time identity-service outage check is opt-in.",
  );
  await page.goto("/sign-in");
  try {
    execFileSync("docker", ["compose", "stop", "keycloak"], {
      cwd: "..",
      stdio: "ignore",
    });
    await page.getByRole("link", { name: "Sign in" }).click();
    await expect(
      page.getByRole("heading", {
        name: "Authentication service unavailable",
      }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("main")).not.toContainText("ECONNREFUSED");
  } finally {
    startKeycloakAndWait();
  }
  await expect
    .poll(
      async () => {
        try {
          return (
            await fetch(
              "http://localhost:8080/realms/taskspace/.well-known/openid-configuration",
            )
          ).ok;
        } catch {
          return false;
        }
      },
      { timeout: 30_000 },
    )
    .toBe(true);
  await expect
    .poll(
      async () => {
        await page.goto("/auth/login?returnTo=%2F");
        return page.locator("#username").isVisible();
      },
      { timeout: 20_000 },
    )
    .toBe(true);
});
