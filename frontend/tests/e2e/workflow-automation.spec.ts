import { execFileSync } from "node:child_process";
import { expect, test, type Page } from "@playwright/test";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled = process.env.RUN_WORKFLOW_E2E === "1" && username && password;
function docker(args: string[]) {
  const composeArgs = ["compose"];
  if (process.env.COMPOSE_PROJECT_NAME) {
    composeArgs.push("-p", process.env.COMPOSE_PROJECT_NAME);
  }
  if (process.env.COMPOSE_FILE) {
    composeArgs.push("-f", process.env.COMPOSE_FILE);
  }
  if (process.env.COMPOSE_ENV_FILES) {
    composeArgs.push("--env-file", process.env.COMPOSE_ENV_FILES);
  }
  return execFileSync("docker", [...composeArgs, ...args], {
    cwd: "..",
    stdio: "pipe",
    env: process.env,
  });
}

async function signIn(page: Page) {
  const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3010";
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username!);
  await page.locator("#password").fill(password!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL(new URL("/", baseURL).toString());
}
async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}

test.describe("Docker-backed workflow automation", () => {
  test.skip(!enabled, "Set RUN_WORKFLOW_E2E=1 and development credentials.");
  test.describe.configure({ mode: "serial" });
  test("task completion creates one execution and one completed job", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const marker = Date.now().toString(36).toUpperCase();
    const projectKey = `W10-${marker}`;
    const ruleName = `Workflow ${marker}`;
    let projectId: string | undefined;
    let taskId: string | undefined;
    let ruleId: string | undefined;
    let jobId: string | undefined;
    try {
      await signIn(page);
      const project = await gql(
        page,
        "mutation C($input:CreateProjectInput!){createProject(input:$input){id}}",
        { input: { key: projectKey, name: `Workflow project ${marker}` } },
      );
      expect(project.errors).toBeUndefined();
      projectId = project.data.createProject.id;
      const task = await gql(
        page,
        "mutation T($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id version}}",
        {
          projectId,
          input: { title: `Workflow task ${marker}`, priority: "MEDIUM" },
        },
      );
      expect(task.errors).toBeUndefined();
      taskId = task.data.createTask.id;
      const started = await gql(
        page,
        "mutation S($projectId:ID!,$taskId:ID!){changeTaskStatus(projectId:$projectId,taskId:$taskId,status:IN_PROGRESS,expectedVersion:1){id version}}",
        { projectId, taskId },
      );
      expect(started.errors).toBeUndefined();
      await page.goto("/workflows/new");
      await page.getByLabel("Rule name").fill(ruleName);
      await page.getByLabel("Project UUID").fill(projectId!);
      await page.getByRole("button", { name: "Create rule" }).click();
      await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]+$/);
      ruleId = page.url().split("/").at(-1)!;
      await page.goto(`/projects/${projectId}/tasks/${taskId}`);
      await page.getByRole("button", { name: "DONE" }).click();
      await expect(
        page.getByText("DONE", { exact: true }).first(),
      ).toBeVisible();
      await expect
        .poll(
          async () => {
            const result = await gql(
              page,
              "query E($id:ID!){workflowRule(id:$id){id}workflowExecutions(first:10,ruleId:$id){nodes{id status resultingJobId}}}",
              { id: ruleId },
            );
            const nodes = result.data?.workflowExecutions?.nodes ?? [];
            if (nodes.length === 1 && nodes[0].resultingJobId) {
              jobId = nodes[0].resultingJobId;
            }
            return nodes.length === 1 ? nodes[0].status : "NONE";
          },
          { timeout: 60_000 },
        )
        .toBe("SUCCEEDED");
      expect(jobId).toBeTruthy();
      await expect
        .poll(
          async () => {
            const result = await gql(
              page,
              "query J($id:ID!){job(id:$id){status}}",
              { id: jobId },
            );
            return result.data?.job?.status;
          },
          { timeout: 60_000 },
        )
        .toBe("SUCCEEDED");
      await page.goto(`/workflows/${ruleId}`);
      await expect(
        page.getByRole("link", { name: "Open resulting job" }),
      ).toHaveAttribute("href", `/jobs/${jobId}`);
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).concat(Object.keys(sessionStorage)),
        ),
      ).toEqual([]);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth + 1,
        ),
      ).toBe(true);
    } finally {
      if (ruleId && projectId) {
        docker([
          "exec",
          "-T",
          "workflow",
          "python",
          "-m",
          "app.development_cleanup",
          "--rule-id",
          ruleId,
          "--expected-project-id",
          projectId,
          "--expected-name",
          ruleName,
        ]);
      }
      if (jobId) {
        docker([
          "exec",
          "-T",
          "job",
          "python",
          "-m",
          "app.development_cleanup",
          jobId,
        ]);
      }
      if (projectId) {
        docker([
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
        ]);
      }
    }
  });
});
