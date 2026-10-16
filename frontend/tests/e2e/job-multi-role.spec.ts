import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Browser, type Page } from "@playwright/test";

const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const env = process.env;
const enabled =
  env.RUN_JOB_MULTI_ROLE_E2E === "1" &&
  env.DEV_USER_USERNAME &&
  env.DEV_USER_PASSWORD &&
  env.PHASE4_E2E_TEMP_PASSWORD &&
  env.PHASE4_E2E_PASSWORD &&
  env.KEYCLOAK_ADMIN_USERNAME &&
  env.KEYCLOAK_ADMIN_PASSWORD;

type Identity = {
  username: string;
  email: string;
  employeeId?: string;
  subject?: string;
};

function docker(args: string[]) {
  const result = spawnSync("docker", ["compose", "-f", composeFile, ...args], {
    encoding: "utf8",
    windowsHide: true,
    env,
  });
  if (result.status !== 0)
    throw new Error("Disposable resource command failed.");
  return result.stdout;
}

async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}

async function authenticatedPage(
  browser: Browser,
  username: string,
  password: string,
  replacement?: string,
) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("http://localhost:3010/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  if (replacement) {
    await page.locator("#password-new").fill(replacement);
    await page.locator("#password-confirm").fill(replacement);
    await page.getByRole("button", { name: "Submit" }).click();
  }
  await expect(page).toHaveURL("http://localhost:3010/");
  return { context, page };
}

test.describe.configure({ mode: "serial" });
test("member ownership, non-owner concealment, and ADMIN override", async ({
  browser,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in Job multi-role journey requires ignored disposable credentials.",
  );
  test.setTimeout(240_000);
  const marker = Date.now().toString(36).toLowerCase();
  const identities: Identity[] = ["owner", "outsider"].map((kind) => ({
    username: `j6-${kind}-${marker}`,
    email: `j6-${kind}-${marker}@example.test`,
  }));
  const [owner, outsider] = identities;
  const projectKey = `JA-${marker.toUpperCase()}`;
  const idempotencyKey = `phase6-multi-role-${marker}`;
  let projectId: string | undefined;
  let jobId: string | undefined;
  let primarySubject: string | undefined;
  const contexts: Array<{ close(): Promise<void> }> = [];

  try {
    const admin = await authenticatedPage(
      browser,
      env.DEV_USER_USERNAME!,
      env.DEV_USER_PASSWORD!,
    );
    contexts.push(admin.context);
    for (const identity of identities) {
      const provisioned = await gql(
        admin.page,
        "mutation P($input: ProvisionEmployeeInput!) { provisionEmployee(input: $input) { id } }",
        {
          input: {
            idempotencyKey: `phase6-${identity.username}`,
            username: identity.username,
            email: identity.email,
            displayName: identity.username.replaceAll("-", " "),
            role: "MEMBER",
            active: true,
            temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD,
          },
        },
      );
      expect(provisioned.errors).toBeUndefined();
      identity.employeeId = provisioned.data.provisionEmployee.id;
    }
    const project = await gql(
      admin.page,
      "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id version } }",
      { input: { key: projectKey, name: `Job authorization ${marker}` } },
    );
    projectId = project.data.createProject.id;
    await gql(
      admin.page,
      "mutation S($id: ID!, $version: Int!) { setProjectStatus(projectId: $id, status: ACTIVE, expectedVersion: $version) { id } }",
      { id: projectId, version: project.data.createProject.version },
    );
    const membership = await gql(
      admin.page,
      "mutation A($id: ID!, $employee: ID!) { addProjectMember(projectId: $id, employeeId: $employee, role: CONTRIBUTOR) { id } }",
      { id: projectId, employee: owner.employeeId },
    );
    expect(membership.errors).toBeUndefined();

    for (const identity of identities) {
      const firstLogin = await authenticatedPage(
        browser,
        identity.username,
        env.PHASE4_E2E_TEMP_PASSWORD!,
        env.PHASE4_E2E_PASSWORD!,
      );
      await firstLogin.context.close();
    }

    const ownerSession = await authenticatedPage(
      browser,
      owner.username,
      env.PHASE4_E2E_PASSWORD!,
    );
    contexts.push(ownerSession.context);
    const operation =
      "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id status attempts { id } } }";
    const submitted = await gql(ownerSession.page, operation, {
      input: { projectId, includeCompleted: true, idempotencyKey },
    });
    expect(submitted.errors).toBeUndefined();
    jobId = submitted.data.submitProjectTaskExport.id;
    expect(submitted.data.submitProjectTaskExport).toMatchObject({
      status: "SUBMITTED",
      attempts: [],
    });
    const ownerList = await gql(
      ownerSession.page,
      "query { jobs(first: 50) { nodes { id } } }",
    );
    expect(ownerList.data.jobs.nodes).toContainEqual({ id: jobId });
    const ownerDetail = await gql(
      ownerSession.page,
      "query J($id: ID!) { job(id: $id) { id status attempts { id } } }",
      { id: jobId },
    );
    expect(ownerDetail.data.job.id).toBe(jobId);
    expect(
      await ownerSession.page.evaluate(() =>
        Object.keys(localStorage).concat(Object.keys(sessionStorage)),
      ),
    ).toEqual([]);
    const forged = await gql(
      ownerSession.page,
      'mutation { submitProjectTaskExport(input: {projectId: "00000000-0000-0000-0000-000000000000", includeCompleted: true, idempotencyKey: "forged", submitterEmployeeId: "00000000-0000-0000-0000-000000000000", role: ADMIN}) { id } }',
    );
    expect(forged.errors[0]).toEqual({ message: "Invalid GraphQL request." });

    const outsiderSession = await authenticatedPage(
      browser,
      outsider.username,
      env.PHASE4_E2E_PASSWORD!,
    );
    contexts.push(outsiderSession.context);
    const outsiderList = await gql(
      outsiderSession.page,
      "query { jobs(first: 50) { nodes { id } } }",
    );
    expect(outsiderList.data.jobs.nodes).not.toContainEqual({ id: jobId });
    const concealed = await gql(
      outsiderSession.page,
      "query J($id: ID!) { job(id: $id) { id } }",
      { id: jobId },
    );
    expect(concealed.errors[0]).toEqual({
      message: "The job was not found.",
      extensions: { code: "JOB_NOT_FOUND" },
    });
    expect(
      await outsiderSession.page.evaluate(() =>
        Object.keys(localStorage).concat(Object.keys(sessionStorage)),
      ),
    ).toEqual([]);

    const adminDetail = await gql(
      admin.page,
      "query J($id: ID!) { job(id: $id) { id status attempts { id } } }",
      { id: jobId },
    );
    expect(adminDetail.data.job).toEqual({
      id: jobId,
      status: "SUBMITTED",
      attempts: [],
    });
    await admin.page.goto(`/jobs/${jobId}`);
    await expect(
      admin.page.getByText(/Dispatch, retry, cancellation/),
    ).toBeVisible();
  } finally {
    for (const context of contexts.reverse()) await context.close();
    await docker([
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
    if (primary.length !== 1)
      throw new Error("Primary identity lookup failed.");
    primarySubject = primary[0].id;
    if (jobId)
      docker([
        "exec",
        "-T",
        "job",
        "python",
        "-m",
        "app.development_cleanup",
        jobId,
      ]);
    if (projectId)
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
    for (const identity of identities) {
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
          `username=${identity.username}`,
        ]),
      );
      if (users.length === 1 && users[0].username === identity.username) {
        identity.subject = users[0].id;
        docker([
          "exec",
          "-T",
          "employee",
          "python",
          "-m",
          "app.development_access",
          "remove",
          "--subject",
          identity.subject!,
          "--protected-subject",
          primarySubject!,
        ]);
        docker([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "delete",
          `users/${identity.subject}`,
          "-r",
          "taskspace",
        ]);
      }
    }
  }
});
