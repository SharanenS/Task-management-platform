import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_EMPLOYEE_ADMIN_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("Employee Service outage is sanitized and recovers", async ({
  page,
}, testInfo) => {
  test.skip(
    !enabled || testInfo.project.name !== "desktop",
    "Opt-in isolated outage check",
  );
  test.setTimeout(120_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 45_000,
      windowsHide: true,
    });
  const configuration = await compose("config", "--format", "json");
  expect(JSON.parse(configuration.stdout).name).toBe(
    "enterprise-task-platform-phase2",
  );

  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL("http://localhost:3010/");

  try {
    await compose("stop", "employee");
    const unavailable = await page.request.post("/graphql", {
      data: { query: "query { employees(first: 1) { nodes { id } } }" },
    });
    const body = await unavailable.json();
    expect(body.errors[0].extensions.code).toBe("SERVICE_UNAVAILABLE");
    expect(JSON.stringify(body)).not.toMatch(
      /employee:8020|Traceback|ECONNREFUSED/,
    );
  } finally {
    await compose("start", "employee");
  }

  await expect
    .poll(
      async () => {
        try {
          const recovered = await page.request.post("/graphql", {
            data: { query: "query { employees(first: 1) { nodes { id } } }" },
          });
          return (await recovered.json()).data?.employees?.nodes !== undefined;
        } catch {
          return false;
        }
      },
      { timeout: 60_000 },
    )
    .toBe(true);
});
