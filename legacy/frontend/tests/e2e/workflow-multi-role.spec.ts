import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

import {
  Cleanup,
  deleteJob,
  discoverOwnedExecutionJobs,
  sqlLiteral,
  uuid,
} from "./workflow-acceptance-support";

const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const env = process.env;
const enabled =
  env.RUN_WORKFLOW_MULTI_ROLE_E2E === "1" &&
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
test("ADMIN, manager, member, and non-member workflow authorization", async ({
  page,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Opt-in workflow multi-role journey requires ignored credentials.",
  );
  test.setTimeout(240_000);
  const marker = Date.now().toString(36).toLowerCase();
  const identities: Identity[] = ["manager", "member", "outsider"].map(
    (role) => ({
      username: `w10-${role}-${marker}`,
      email: `w10-${role}-${marker}@example.test`,
    }),
  );
  const [manager, contributor, outsider] = identities;
  const projectKey = `WMR-${marker.toUpperCase()}`;
  const ruleName = `Workflow roles ${marker}`;
  const finalRuleName = `Updated workflow ${marker}`;
  let currentRuleName = ruleName;
  const taskTitle = `Workflow role task ${marker}`;
  let primarySubject: string | undefined;
  let ruleId: string | undefined;
  let projectId: string | undefined;
  let taskId: string | undefined;
  const provision = async (identity: Identity, role: "MANAGER" | "MEMBER") => {
    const result = await gql(
      page,
      "mutation P($input: ProvisionEmployeeInput!) { provisionEmployee(input: $input) { id } }",
      {
        input: {
          idempotencyKey: `phase10-${identity.username}`,
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
    uuid(identity.employeeId!, "Employee ID");
    const users = (
      JSON.parse(
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
      ) as Array<{ id: string; username: string; email?: string }>
    ).filter((user) => user.username === identity.username);
    if (users.length !== 1 || users[0].email !== identity.email)
      throw new Error("Provisioned Keycloak identity ownership is not unique.");
    identity.subject = uuid(users[0].id, "Keycloak subject");
    const linked = docker([
      "exec",
      "-T",
      "employee-db",
      "psql",
      "-U",
      "employee",
      "-d",
      "employee",
      "-Atc",
      `select count(*) from employees where id=${sqlLiteral(identity.employeeId!)}::uuid and keycloak_subject=${sqlLiteral(identity.subject!)} and username=${sqlLiteral(identity.username)} and email=${sqlLiteral(identity.email)};`,
    ]).trim();
    if (linked !== "1")
      throw new Error("Provisioned identity link was not verified.");
  };
  try {
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
    const primaryUsers = (
      JSON.parse(
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
      ) as Array<{ id: string; username: string; enabled: boolean }>
    ).filter((user) => user.username === env.DEV_USER_USERNAME);
    if (primaryUsers.length !== 1 || !primaryUsers[0].enabled)
      throw new Error("Protected primary identity preflight failed.");
    primarySubject = uuid(primaryUsers[0].id, "primary subject");
    const primaryProfile = docker([
      "exec",
      "-T",
      "employee-db",
      "psql",
      "-U",
      "employee",
      "-d",
      "employee",
      "-Atc",
      `select count(*) from employees where username=${sqlLiteral(env.DEV_USER_USERNAME!)} and keycloak_subject=${sqlLiteral(primarySubject)} and active is true and role='ADMIN' and provisioning_status='COMPLETE';`,
    ]).trim();
    if (primaryProfile !== "1")
      throw new Error("Protected primary profile preflight failed.");
    for (const identity of identities) {
      const existingUsers = (
        JSON.parse(
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
        ) as Array<{ username: string }>
      ).filter((user) => user.username === identity.username);
      const existingProfiles = docker([
        "exec",
        "-T",
        "employee-db",
        "psql",
        "-U",
        "employee",
        "-d",
        "employee",
        "-Atc",
        `select count(*) from employees where username=${sqlLiteral(identity.username)} or email=${sqlLiteral(identity.email)};`,
      ]).trim();
      if (existingUsers.length !== 0 || existingProfiles !== "0")
        throw new Error("Disposable identity marker already exists.");
    }
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
    uuid(projectId!, "project ID");
    const workflow = await gql(
      page,
      "mutation W($input:CreateWorkflowRuleInput!){createWorkflowRule(input:$input){id version enabled}}",
      {
        input: {
          projectId,
          name: ruleName,
          triggerType: "TASK_COMPLETED",
          actionType: "PROJECT_TASK_EXPORT",
        },
      },
    );
    expect(workflow.errors).toBeUndefined();
    ruleId = workflow.data.createWorkflowRule.id;
    uuid(ruleId!, "workflow rule ID");
    const renamed = await gql(
      page,
      "mutation U($id:ID!,$name:String!){updateWorkflowRule(ruleId:$id,input:{name:$name,expectedVersion:1}){version}}",
      { id: ruleId, name: finalRuleName },
    );
    expect(renamed.errors).toBeUndefined();
    currentRuleName = finalRuleName;
    await gql(
      page,
      "mutation D($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:false,expectedVersion:2){version}}",
      { id: ruleId },
    );
    await gql(
      page,
      "mutation E($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:true,expectedVersion:3){version}}",
      { id: ruleId },
    );
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
    const task = await gql(
      page,
      "mutation T($id: ID!, $input: CreateTaskInput!) { createTask(projectId: $id, input: $input) { id assigneeEmployeeId version } }",
      {
        id: projectId,
        input: {
          title: taskTitle,
          assigneeEmployeeId: contributor.employeeId,
          priority: "HIGH",
        },
      },
    );
    taskId = task.data.createTask.id;
    uuid(taskId!, "task ID");
    expect(task.data.createTask.assigneeEmployeeId).toBe(
      contributor.employeeId,
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
    const visibleRule = await gql(
      page,
      "query W($id:ID!){workflowRule(id:$id){id name}workflowExecutions(first:10,ruleId:$id){nodes{id status}}}",
      { id: ruleId },
    );
    expect(visibleRule.data.workflowRule.id).toBe(ruleId);
    expect(visibleRule.data.workflowExecutions.nodes).toEqual([]);
    const deniedWorkflow = await gql(
      page,
      "mutation D($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:false,expectedVersion:4){id}}",
      { id: ruleId },
    );
    expect(deniedWorkflow.errors[0].extensions.code).toMatch(
      /FORBIDDEN|NOT_FOUND/,
    );
    const forgedWorkflow = await gql(
      page,
      'mutation { createWorkflowRule(input:{projectId:"00000000-0000-4000-8000-000000000000",name:"Forged",triggerType:TASK_COMPLETED,actionType:PROJECT_TASK_EXPORT,ownerId:"00000000-0000-4000-8000-000000000000",enabled:true,status:"SUCCEEDED",sourceEventId:"00000000-0000-4000-8000-000000000000",executionId:"00000000-0000-4000-8000-000000000000",jobId:"00000000-0000-4000-8000-000000000000"){id}}',
    );
    expect(forgedWorkflow.errors).toBeTruthy();
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
    const transitioned = await gql(
      page,
      "mutation T($project: ID!, $task: ID!) { changeTaskStatus(projectId: $project, taskId: $task, status: IN_PROGRESS, expectedVersion: 1) { status version } }",
      { project: projectId, task: taskId },
    );
    expect(transitioned.data.changeTaskStatus.status).toBe("IN_PROGRESS");
    const comment = await gql(
      page,
      'mutation C($project: ID!, $task: ID!) { addTaskComment(projectId: $project, taskId: $task, body: "Contributor comment") { body } }',
      { project: projectId, task: taskId },
    );
    expect(comment.data.addTaskComment.body).toBe("Contributor comment");
    expect(
      (
        await gql(
          page,
          "mutation A($project: ID!, $task: ID!) { assignTask(projectId: $project, taskId: $task, assigneeEmployeeId: null, expectedVersion: 2) { id } }",
          { project: projectId, task: taskId },
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    expect(
      (
        await gql(
          page,
          'mutation U($project: ID!, $task: ID!) { updateTask(projectId: $project, taskId: $task, input: {title: "Forged", description: null, priority: LOW, dueDate: null, expectedVersion: 2}) { id } }',
          { project: projectId, task: taskId },
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    await logout(page);

    await login(page, outsider.username, env.PHASE4_E2E_PASSWORD!);
    await page.goto("/projects");
    await expect(page.getByText("Multi-role project updated")).toHaveCount(0);
    const concealedWorkflow = await gql(
      page,
      "query W($id:ID!){workflowRule(id:$id){id}workflowExecutions(first:10,ruleId:$id){nodes{id}}}",
      { id: ruleId },
    );
    expect(concealedWorkflow.errors[0].extensions.code).toMatch(
      /FORBIDDEN|NOT_FOUND/,
    );
    expect(
      (
        await gql(page, "query P($id: ID!) { project(id: $id) { id } }", {
          id: projectId,
        })
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    expect(
      (
        await gql(
          page,
          "query T($project: ID!, $task: ID!) { task(projectId: $project, taskId: $task) { id } }",
          { project: projectId, task: taskId },
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    expect(
      (
        await gql(
          page,
          'mutation C($project: ID!, $task: ID!) { addTaskComment(projectId: $project, taskId: $task, body: "Forged") { id } }',
          { project: projectId, task: taskId },
        )
      ).errors[0].extensions.code,
    ).toBe("FORBIDDEN");
    await logout(page);

    await login(page, manager.username, env.PHASE4_E2E_PASSWORD!);
    await gql(
      page,
      "mutation S($id: ID!) { setProjectStatus(projectId: $id, status: ARCHIVED, expectedVersion: 3) { id } }",
      { id: projectId },
    );
    const archivedTask = await gql(
      page,
      'mutation C($project: ID!, $task: ID!) { addTaskComment(projectId: $project, taskId: $task, body: "Archived") { id } }',
      { project: projectId, task: taskId },
    );
    expect(archivedTask.errors[0].extensions.code).toBe("PROJECT_ARCHIVED");
    await gql(
      page,
      "mutation S($id: ID!) { setProjectStatus(projectId: $id, status: ACTIVE, expectedVersion: 4) { id } }",
      { id: projectId },
    );
    const resumed = await gql(
      page,
      "mutation T($project: ID!, $task: ID!) { changeTaskStatus(projectId: $project, taskId: $task, status: DONE, expectedVersion: 2) { status } }",
      { project: projectId, task: taskId },
    );
    expect(resumed.data.changeTaskStatus.status).toBe("DONE");
    const assignedRemoval = await gql(
      page,
      "mutation R($id: ID!, $employee: ID!) { removeProjectMember(projectId: $id, employeeId: $employee) { memberships { employeeId role } } }",
      { id: projectId, employee: contributor.employeeId },
    );
    expect(assignedRemoval.errors).toEqual([
      expect.objectContaining({
        message:
          "Reassign the employee's tasks before removing project membership.",
        extensions: { code: "MEMBER_HAS_ASSIGNED_TASKS" },
      }),
    ]);
    const stillMember = await gql(
      page,
      "query P($id: ID!) { project(id: $id) { memberships { employeeId role } } }",
      { id: projectId },
    );
    expect(stillMember.data.project.memberships).toContainEqual({
      employeeId: contributor.employeeId,
      role: "CONTRIBUTOR",
    });
    await gql(
      page,
      "mutation A($project: ID!, $task: ID!) { assignTask(projectId: $project, taskId: $task, assigneeEmployeeId: null, expectedVersion: 3) { assigneeEmployeeId version } }",
      { project: projectId, task: taskId },
    );
    const safeRemoval = await gql(
      page,
      "mutation R($id: ID!, $employee: ID!) { removeProjectMember(projectId: $id, employeeId: $employee) { memberships { employeeId role } } }",
      { id: projectId, employee: contributor.employeeId },
    );
    expect(safeRemoval.data.removeProjectMember.memberships).toEqual([
      { employeeId: manager.employeeId, role: "PROJECT_MANAGER" },
    ]);
    await gql(
      page,
      "mutation A($id: ID!, $employee: ID!) { addProjectMember(projectId: $id, employeeId: $employee, role: CONTRIBUTOR) { id } }",
      { id: projectId, employee: contributor.employeeId },
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
    await logout(page);
    await login(page, manager.username, env.PHASE4_E2E_PASSWORD!);
    const removedManagerList = await gql(
      page,
      "query L($project:ID!){workflowRules(first:10,projectId:$project){nodes{id}}}",
      { project: projectId },
    );
    expect(removedManagerList.data?.workflowRules?.nodes ?? []).toEqual([]);
    const removedManagerDetail = await gql(
      page,
      "query W($id:ID!){workflowRule(id:$id){id}}",
      { id: ruleId },
    );
    expect(removedManagerDetail.errors[0].extensions.code).toMatch(
      /FORBIDDEN|NOT_FOUND/,
    );
    const removedManagerUpdate = await gql(
      page,
      'mutation U($id:ID!){updateWorkflowRule(ruleId:$id,input:{name:"Stale creator",expectedVersion:4}){id}}',
      { id: ruleId },
    );
    expect(removedManagerUpdate.errors[0].extensions.code).toMatch(
      /FORBIDDEN|NOT_FOUND/,
    );
    const removedManagerToggle = await gql(
      page,
      "mutation D($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:false,expectedVersion:4){id}}",
      { id: ruleId },
    );
    expect(removedManagerToggle.errors[0].extensions.code).toMatch(
      /FORBIDDEN|NOT_FOUND/,
    );
    await logout(page);
    await login(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
    const adminView = await gql(
      page,
      "query W($id:ID!){workflowRule(id:$id){id version}}",
      { id: ruleId },
    );
    expect(adminView.data.workflowRule.id).toBe(ruleId);
    await gql(
      page,
      "mutation D($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:false,expectedVersion:4){version}}",
      { id: ruleId },
    );
    await gql(
      page,
      "mutation E($id:ID!){setWorkflowRuleEnabled(ruleId:$id,enabled:true,expectedVersion:5){version}}",
      { id: ruleId },
    );
    expect(
      await page.evaluate(() =>
        Object.keys(localStorage).concat(Object.keys(sessionStorage)),
      ),
    ).toEqual([]);
  } finally {
    const cleanup = new Cleanup();
    const discoveredJobIds = new Set<string>();
    const discoveredJobKeys = new Set<string>();
    await cleanup.stage("re-establish Keycloak admin context", () => {
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
    });
    await cleanup.stage("revalidate protected primary subject", () => {
      if (!primarySubject)
        throw new Error("Primary subject was not recorded before setup.");
      const users = (
        JSON.parse(
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
        ) as Array<{ id: string; username: string; enabled: boolean }>
      ).filter((user) => user.username === env.DEV_USER_USERNAME);
      if (
        users.length !== 1 ||
        users[0].id !== primarySubject ||
        !users[0].enabled
      )
        throw new Error("Protected primary identity changed.");
    });
    await cleanup.stage("discover execution and job links", () => {
      for (const link of discoverOwnedExecutionJobs({
        ruleId,
        projectId,
        taskId,
        projectKey,
        ruleName: currentRuleName,
        taskTitle,
      })) {
        discoveredJobKeys.add(link.idempotencyKey);
        for (const id of link.jobIds) discoveredJobIds.add(id);
      }
    });
    await cleanup.stage("delete exact workflow jobs", () => {
      for (const id of discoveredJobIds) deleteJob(id);
    });
    await cleanup.stage("delete exact workflow rule", () => {
      const ownedRuleId =
        ruleId ??
        docker([
          "exec",
          "-T",
          "workflow-db",
          "psql",
          "-U",
          "workflow",
          "-d",
          "workflow",
          "-Atc",
          `select id::text from workflow_rules where name=${sqlLiteral(currentRuleName)};`,
        ]).trim();
      const ownedProjectId =
        projectId ??
        docker([
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select id::text from projects where key=${sqlLiteral(projectKey)};`,
        ]).trim();
      if (!ownedRuleId && !ownedProjectId) return;
      if (!ownedRuleId || !ownedProjectId)
        throw new Error("Rule cleanup ownership is incomplete.");
      docker([
        "exec",
        "-T",
        "workflow",
        "python",
        "-m",
        "app.development_cleanup",
        "--rule-id",
        uuid(ownedRuleId, "rule ID"),
        "--expected-project-id",
        uuid(ownedProjectId, "project ID"),
        "--expected-name",
        currentRuleName,
      ]);
    });
    await cleanup.stage("delete exact Work project and tasks", () => {
      const ownedProjectId =
        projectId ??
        docker([
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select id::text from projects where key=${sqlLiteral(projectKey)};`,
        ]).trim();
      if (ownedProjectId)
        docker([
          "exec",
          "-T",
          "work",
          "python",
          "-m",
          "app.development_cleanup",
          "--project-id",
          uuid(ownedProjectId, "project ID"),
          "--expected-key",
          projectKey,
        ]);
    });
    for (const identity of identities) {
      await cleanup.stage(`resolve ownership for ${identity.username}`, () => {
        const users = (
          JSON.parse(
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
          ) as Array<{ id: string; username: string; email?: string }>
        ).filter((user) => user.username === identity.username);
        const profile = docker([
          "exec",
          "-T",
          "employee-db",
          "psql",
          "-U",
          "employee",
          "-d",
          "employee",
          "-Atc",
          `select id::text || '|' || keycloak_subject || '|' || email from employees where username=${sqlLiteral(identity.username)};`,
        ]).trim();
        if (!users.length && !profile) return;
        if (
          users.length !== 1 ||
          users[0].email !== identity.email ||
          !profile ||
          !identity.username.startsWith(`w10-`)
        )
          throw new Error("Disposable ownership evidence is ambiguous.");
        const [employeeId, subject, email] = profile.split("|");
        uuid(employeeId, "Employee ID");
        uuid(subject, "Keycloak subject");
        if (
          email !== identity.email ||
          subject !== users[0].id ||
          (identity.employeeId && employeeId !== identity.employeeId) ||
          (identity.subject && subject !== identity.subject) ||
          subject === primarySubject
        )
          throw new Error("Disposable ownership evidence does not match.");
        identity.employeeId = employeeId;
        identity.subject = subject;
      });
      await cleanup.stage(
        `remove Employee profile ${identity.username}`,
        () => {
          if (!identity.subject) {
            const remaining = docker([
              "exec",
              "-T",
              "employee-db",
              "psql",
              "-U",
              "employee",
              "-d",
              "employee",
              "-Atc",
              `select count(*) from employees where username=${sqlLiteral(identity.username)} or email=${sqlLiteral(identity.email)};`,
            ]).trim();
            if (remaining !== "0")
              throw new Error(
                "Employee profile exists without proven ownership.",
              );
            return;
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
            identity.subject,
            "--protected-subject",
            primarySubject!,
          ]);
        },
      );
      await cleanup.stage(
        `delete Keycloak identity ${identity.username}`,
        () => {
          if (!identity.subject) {
            const users = (
              JSON.parse(
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
              ) as Array<{ username: string }>
            ).filter((user) => user.username === identity.username);
            if (users.length)
              throw new Error(
                "Keycloak identity exists without proven ownership.",
              );
            return;
          }
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
        },
      );
    }
    await cleanup.stage("independent current-run zero counts", () => {
      const names = identities
        .map((identity) => sqlLiteral(identity.username))
        .join(",");
      const jobIds =
        [...discoveredJobIds]
          .map((id) => `${sqlLiteral(uuid(id, "job ID"))}::uuid`)
          .join(",") || "null";
      const counts = [
        docker([
          "exec",
          "-T",
          "workflow-db",
          "psql",
          "-U",
          "workflow",
          "-d",
          "workflow",
          "-Atc",
          `select count(*) from workflow_rules where name in (${sqlLiteral(ruleName)},${sqlLiteral(finalRuleName)});`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "workflow-db",
          "psql",
          "-U",
          "workflow",
          "-d",
          "workflow",
          "-Atc",
          `select count(*) from workflow_executions where task_id=${taskId ? `${sqlLiteral(uuid(taskId, "task ID"))}::uuid` : "null"};`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "workflow-db",
          "psql",
          "-U",
          "workflow",
          "-d",
          "workflow",
          "-Atc",
          `select count(*) from workflow_source_events where task_id=${taskId ? `${sqlLiteral(uuid(taskId, "task ID"))}::uuid` : "null"};`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select count(*) from work_outbox_events where task_id=${taskId ? `${sqlLiteral(uuid(taskId, "task ID"))}::uuid` : "null"};`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select count(*) from projects where key=${sqlLiteral(projectKey)};`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "work-db",
          "psql",
          "-U",
          "work",
          "-d",
          "work",
          "-Atc",
          `select count(*) from tasks where title=${sqlLiteral(taskTitle)};`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "job-db",
          "psql",
          "-U",
          "job",
          "-d",
          "job",
          "-Atc",
          `select count(*) from jobs where id in (${jobIds});`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "job-db",
          "psql",
          "-U",
          "job",
          "-d",
          "job",
          "-Atc",
          `select count(*) from jobs where idempotency_key in (${[...discoveredJobKeys].map(sqlLiteral).join(",") || "null"});`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "job-db",
          "psql",
          "-U",
          "job",
          "-d",
          "job",
          "-Atc",
          `select count(*) from job_attempts where job_id in (${jobIds});`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "job-db",
          "psql",
          "-U",
          "job",
          "-d",
          "job",
          "-Atc",
          `select count(*) from jobs where id in (${jobIds}) and result_content is not null;`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "job-db",
          "psql",
          "-U",
          "job",
          "-d",
          "job",
          "-Atc",
          `select count(*) from job_publication_outbox where job_id in (${jobIds});`,
        ]).trim(),
        docker([
          "exec",
          "-T",
          "employee-db",
          "psql",
          "-U",
          "employee",
          "-d",
          "employee",
          "-Atc",
          `select count(*) from employees where username in (${names});`,
        ]).trim(),
      ];
      if (counts.some((count) => count !== "0"))
        throw new Error("Current-run marker rows remain.");
      for (const identity of identities) {
        const users = (
          JSON.parse(
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
          ) as Array<{ username: string }>
        ).filter((user) => user.username === identity.username);
        if (users.length)
          throw new Error("Current-run Keycloak identity remains.");
      }
      const oneOffs = docker(["ps", "-a", "--services"])
        .split(/\r?\n/)
        .filter((name) => name.startsWith(`w10-${marker}`));
      if (oneOffs.length)
        throw new Error("Current-run one-off containers remain.");
    });
    await cleanup.stage("verify primary administrator integrity", () => {
      if (!primarySubject) throw new Error("Primary subject was not recorded.");
      const users = (
        JSON.parse(
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
        ) as Array<{ id: string; username: string; enabled: boolean }>
      ).filter((user) => user.username === env.DEV_USER_USERNAME);
      if (
        users.length !== 1 ||
        users[0].id !== primarySubject ||
        !users[0].enabled
      )
        throw new Error("Protected primary identity integrity failed.");
      const profile = docker([
        "exec",
        "-T",
        "employee-db",
        "psql",
        "-U",
        "employee",
        "-d",
        "employee",
        "-Atc",
        `select count(*) from employees where username=${sqlLiteral(env.DEV_USER_USERNAME!)} and keycloak_subject=${sqlLiteral(primarySubject)} and active is true and role='ADMIN' and provisioning_status='COMPLETE';`,
      ]).trim();
      if (profile !== "1")
        throw new Error("Protected primary profile integrity failed.");
    });
    cleanup.finish();
  }
});
