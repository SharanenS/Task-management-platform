import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const env = process.env;
const enabled =
  env.RUN_PROJECT_MULTI_ROLE_E2E === "1" &&
  env.DEV_USER_USERNAME &&
  env.DEV_USER_PASSWORD &&
  env.PHASE4_E2E_TEMP_PASSWORD &&
  env.PHASE4_E2E_PASSWORD &&
  env.KEYCLOAK_ADMIN_USERNAME &&
  env.KEYCLOAK_ADMIN_PASSWORD;
type Identity = { username: string; email: string; employeeId?: string };

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
async function login(
  page: Page,
  username: string,
  password: string,
  replacement?: string,
) {
  await page.goto("/sign-in");
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
}
async function logout(page: Page) {
  await page.getByRole("button", { name: /ADMIN|MANAGER|MEMBER/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/signed-out$/);
}

test.describe.configure({ mode: "serial" });
test("manager, contributor, non-member, and final-manager boundaries", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in multi-role journey requires ignored Phase 4 credentials.",
  );
  test.setTimeout(240_000);
  const marker = Date.now().toString(36).toLowerCase();
  const identities: Identity[] = ["manager", "member", "outsider"].map(
    (role) => ({
      username: `p4-${role}-${marker}`,
      email: `p4-${role}-${marker}@example.test`,
    }),
  );
  const [manager, contributor, outsider] = identities;
  const projectKey = `MR-${marker.toUpperCase()}`;
  let projectId: string | undefined;
  const provision = async (identity: Identity, role: "MANAGER" | "MEMBER") => {
    const result = await gql(
      page,
      "mutation P($input: ProvisionEmployeeInput!) { provisionEmployee(input: $input) { id } }",
      {
        input: {
          idempotencyKey: `phase4-${identity.username}`,
          username: identity.username,
          email: identity.email,
          displayName: identity.username.replaceAll("-", " "),
          role,
          active: true,
          temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD,
        },
      },
    );
    expect(result.errors).toBeUndefined();
    identity.employeeId = result.data.provisionEmployee.id;
  };
  try {
    await login(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
    await provision(manager, "MANAGER");
    await provision(contributor, "MEMBER");
    await provision(outsider, "MEMBER");
    await logout(page);
    for (const identity of identities) {
      await login(
        page,
        identity.username,
        env.PHASE4_E2E_TEMP_PASSWORD!,
        env.PHASE4_E2E_PASSWORD!,
      );
      await logout(page);
    }

    await login(page, manager.username, env.PHASE4_E2E_PASSWORD!);
    const created = await gql(
      page,
      "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id memberships { employeeId role } } }",
      {
        input: {
          key: projectKey,
          name: "Multi-role project",
          description: "Test-owned",
        },
      },
    );
    projectId = created.data.createProject.id;
    expect(created.data.createProject.memberships).toEqual([
      { employeeId: manager.employeeId, role: "PROJECT_MANAGER" },
    ]);
    const updated = await gql(
      page,
      "mutation U($id: ID!, $input: UpdateProjectInput!) { updateProject(projectId: $id, input: $input) { version } }",
      {
        id: projectId,
        input: {
          name: "Multi-role project updated",
          description: "Updated",
          expectedVersion: 1,
        },
      },
    );
    expect(updated.data.updateProject.version).toBe(2);
    await gql(
      page,
      "mutation S($id: ID!) { setProjectStatus(projectId: $id, status: ACTIVE, expectedVersion: 2) { id } }",
      { id: projectId },
    );
    await gql(
      page,
      "mutation A($id: ID!, $employee: ID!) { addProjectMember(projectId: $id, employeeId: $employee, role: CONTRIBUTOR) { id } }",
      { id: projectId, employee: contributor.employeeId },
    );
    const protectedManager = await gql(
      page,
      "mutation R($id: ID!, $employee: ID!) { removeProjectMember(projectId: $id, employeeId: $employee) { id } }",
      { id: projectId, employee: manager.employeeId },
    );
    expect(protectedManager.errors[0].extensions.code).toBe(
      "FINAL_PROJECT_MANAGER",
    );
    await logout(page);

    await login(page, contributor.username, env.PHASE4_E2E_PASSWORD!);
    await page.goto("/projects");
    await expect(page.getByText("Multi-role project updated")).toBeVisible();
    await page.goto(`/projects/${projectId}`);
    await expect(
      page.getByRole("heading", { name: "Multi-role project updated" }),
    ).toBeVisible();
    expect(
      (
        await gql(
          page,
          'mutation { createProject(input: {key: "FORGED", name: "Forged"}) { id } }',
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    expect(
      (
        await gql(
          page,
          'mutation U($id: ID!) { updateProject(projectId: $id, input: {name: "Forged", description: null, expectedVersion: 3}) { id } }',
          { id: projectId },
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    await logout(page);

    await login(page, outsider.username, env.PHASE4_E2E_PASSWORD!);
    await page.goto("/projects");
    await expect(page.getByText("Multi-role project updated")).toHaveCount(0);
    expect(
      (
        await gql(page, "query P($id: ID!) { project(id: $id) { id } }", {
          id: projectId,
        })
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    await logout(page);

    await login(page, manager.username, env.PHASE4_E2E_PASSWORD!);
    await gql(
      page,
      "mutation S($id: ID!) { setProjectStatus(projectId: $id, status: ARCHIVED, expectedVersion: 3) { id } }",
      { id: projectId },
    );
    await gql(
      page,
      "mutation S($id: ID!) { setProjectStatus(projectId: $id, status: ACTIVE, expectedVersion: 4) { id } }",
      { id: projectId },
    );
    await gql(
      page,
      "mutation M($id: ID!, $employee: ID!) { updateProjectMemberRole(projectId: $id, employeeId: $employee, role: PROJECT_MANAGER) { id } }",
      { id: projectId, employee: contributor.employeeId },
    );
    const transfer = await gql(
      page,
      "mutation R($id: ID!, $employee: ID!) { removeProjectMember(projectId: $id, employeeId: $employee) { memberships { employeeId role } } }",
      { id: projectId, employee: manager.employeeId },
    );
    expect(transfer.data.removeProjectMember.memberships).toEqual([
      { employeeId: contributor.employeeId, role: "PROJECT_MANAGER" },
    ]);
  } finally {
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
        docker([
          "exec",
          "-T",
          "employee",
          "python",
          "-m",
          "app.development_access",
          "remove",
          "--subject",
          users[0].id,
          "--protected-subject",
          primary[0].id,
        ]);
        docker([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "delete",
          `users/${users[0].id}`,
          "-r",
          "taskspace",
        ]);
      }
    }
  }
});
