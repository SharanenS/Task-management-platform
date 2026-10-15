import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { expect, test } from "@playwright/test";

const execute = promisify(execFile);
const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const enabled =
  process.env.RUN_PROJECT_OUTAGE_E2E === "1" &&
  process.env.DEV_USER_USERNAME &&
  process.env.DEV_USER_PASSWORD;

test.describe.configure({ mode: "serial" });

test("Work Service persists through restart, sanitizes outage, and recovers", async ({
  page,
}, testInfo) => {
  test.skip(
    !enabled || testInfo.project.name !== "desktop",
    "Opt-in isolated Work outage check",
  );
  test.setTimeout(180_000);
  const compose = (...args: string[]) =>
    execute("docker", ["compose", "-f", composeFile, ...args], {
      timeout: 60_000,
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

  const marker = Date.now().toString(36).toUpperCase();
  const key = `REC-${marker}`;
  let projectId: string | undefined;
  const queryProject = async () => {
    const response = await page.request.post("/graphql", {
      data: {
        query:
          "query Project($id: ID!) { project(id: $id) { id key memberships { employeeId role } } }",
        variables: { id: projectId },
      },
    });
    return response.json();
  };
  const waitForWork = async () => {
    await expect
      .poll(
        async () => {
          try {
            await compose(
              "exec",
              "-T",
              "work",
              "python",
              "-c",
              "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8030/health/ready', timeout=2)",
            );
            return true;
          } catch {
            return false;
          }
        },
        { timeout: 60_000 },
      )
      .toBe(true);
  };

  try {
    const created = await page.request.post("/graphql", {
      data: {
        query:
          "mutation Create($input: CreateProjectInput!) { createProject(input: $input) { id key memberships { employeeId role } } }",
        variables: {
          input: { key, name: `Recovery ${marker}`, description: "Test-owned" },
        },
      },
    });
    const createdBody = await created.json();
    expect(createdBody.errors).toBeUndefined();
    projectId = createdBody.data.createProject.id;
    expect(createdBody.data.createProject.memberships).toHaveLength(1);

    await compose("restart", "work");
    await waitForWork();
    const persisted = await queryProject();
    expect(persisted.data.project.key).toBe(key);
    expect(persisted.data.project.memberships).toHaveLength(1);

    await compose("stop", "work");
    const unavailable = await page.request.post("/graphql", {
      data: { query: "query { projects(first: 1) { nodes { id } } }" },
    });
    const unavailableBody = await unavailable.json();
    expect(unavailableBody.errors[0]).toEqual({
      message: "Project management is temporarily unavailable.",
      extensions: { code: "SERVICE_UNAVAILABLE" },
    });
    expect(JSON.stringify(unavailableBody)).not.toMatch(
      /work:8030|Traceback|ECONNREFUSED|connection string/i,
    );
  } finally {
    await compose("start", "work");
    await waitForWork();
    if (projectId) {
      await compose(
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
      );
    }
  }

  const recovered = await page.request.post("/graphql", {
    data: { query: "query { projects(first: 1) { nodes { id } } }" },
  });
  expect((await recovered.json()).data.projects.nodes).toBeDefined();
});
