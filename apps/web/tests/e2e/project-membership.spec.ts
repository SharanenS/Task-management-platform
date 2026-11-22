import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { ProjectAcceptance } from "./project-acceptance-support";

test.describe.configure({ mode: "serial" });
const run = new ProjectAcceptance();
let ownerContext: BrowserContext | undefined;
let employeeContext: BrowserContext | undefined;
let ownerPage: Page;
let employeePage: Page;
let employeeAccount: string;
const projects: { id: string; version: number; name: string }[] = [];
let contribution: Record<string, unknown>;
let contributionChange: string;
const membership =
  "query($id:ID!){projectMembership(id:$id){canManage responsibility project{id version creatorId ownerId} members{accountId duties responsibility active} history{id action}}}";
const change =
  "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){projectId version changeId}}";
function appointment(
  project: { id: string; version: number },
  fields: Record<string, unknown> = {},
) {
  return {
    projectId: project.id,
    version: project.version,
    requestId: crypto.randomUUID(),
    accountId: employeeAccount,
    action: "appoint",
    responsibility: "CONTRIBUTOR",
    duties: "Acceptance responsibilities",
    confirm: true,
    ...fields,
  };
}
async function check(work: () => Promise<void>) {
  try {
    await work();
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S8 boundary failed: ${run.boundary}`);
  }
}

test.beforeAll(async ({ browser }) => {
  run.diagnosticScope = "s8";
  run.boundary = "verified fixture identities and current employee association";
  try {
    await run.setup();
    run.people("project_other_role", "EMPLOYEE");
    employeeAccount = run.people("project_other_inspect").accountId;
    ownerContext = await browser.newContext({
      baseURL: "http://127.0.0.1:3020",
      viewport: test.info().project.use.viewport,
    });
    employeeContext = await browser.newContext({
      baseURL: "http://127.0.0.1:3020",
      viewport: test.info().project.use.viewport,
    });
    ownerPage = await ownerContext.newPage();
    employeePage = await employeeContext.newPage();
    await run.login(ownerPage);
    await expect(
      ownerPage.getByRole("heading", { name: "Administration", exact: true }),
    ).toBeVisible();
    const deadline = await run.calendar(ownerContext);
    run.people("role", "MANAGER");
    for (const prefix of [
      "Leader context",
      "Contributor context",
      "Unrelated context",
    ]) {
      const preview = await run.graphql(
        ownerContext,
        "mutation($input:ProjectPreviewInput!){previewProject(input:$input){previewId}}",
        {
          input: {
            name: `${prefix} ${run.runId}`,
            objectives: "S8 owned scope acceptance",
            deadlineDate: deadline,
          },
        },
      );
      expect(preview.errors).toBeUndefined();
      const created = await run.graphql(
        ownerContext,
        "mutation($input:CreateProjectInput!){createProject(input:$input){id version name}}",
        {
          input: {
            requestId: crypto.randomUUID(),
            previewId: preview.data.previewProject.previewId,
            confirm: true,
          },
        },
      );
      expect(created.errors).toBeUndefined();
      projects.push(created.data.createProject);
    }
    await run.login(employeePage, run.secondary);
    await expect(
      employeePage.getByRole("heading", {
        name: "You’re securely signed in.",
        exact: true,
      }),
    ).toBeVisible();
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S8 setup failed: ${run.boundary}`);
  }
});

test.beforeEach(async () => {
  await ownerPage.goto("/auth/ready");
  await employeePage.goto("/auth/ready");
});

test.afterAll(async () => {
  const failures: unknown[] = [];
  for (const [context, identity] of [
    [employeeContext, run.secondary],
    [ownerContext, run.primary],
  ] as const) {
    if (!context) continue;
    try {
      await run.sessions(context, identity);
    } catch (error) {
      failures.push(error);
    }
    try {
      await context.close();
    } catch (error) {
      failures.push(error);
    }
  }
  try {
    await run.cleanup();
  } catch (error) {
    failures.push(error);
  }
  if (failures.length)
    throw new Error("S8 scoped cleanup failed; private details omitted");
});

test("S8 owner appoints a project team leader through confirmed UI", async () => {
  await check(async () => {
    run.boundary = "owner UI appointment and explicit confirmation";
    await ownerPage.goto(
      `/manager/projects/${projects[0].id}/members?search=${encodeURIComponent("Project acceptance manager")}`,
    );
    await expect(
      ownerPage.getByRole("heading", { name: projects[0].name, exact: true }),
    ).toBeVisible();
    await ownerPage
      .getByLabel("Employee", { exact: true })
      .selectOption(employeeAccount);
    await ownerPage
      .getByLabel("Project responsibility", { exact: true })
      .selectOption("LEADER");
    await ownerPage
      .getByLabel("Responsibilities", { exact: true })
      .fill("Lead the first project only.");
    await expect(
      ownerPage.getByRole("button", { name: "Save appointment", exact: true }),
    ).toBeDisabled();
    await ownerPage
      .getByLabel("I confirm this project membership change")
      .check();
    await ownerPage
      .getByRole("button", { name: "Save appointment", exact: true })
      .click();
    await expect(
      ownerPage.getByText(/Appointment saved.*Project version 2/),
    ).toBeVisible();
    const state = await run.graphql(ownerContext!, membership, {
      id: projects[0].id,
    });
    expect(state.errors).toBeUndefined();
    expect(state.data.projectMembership.project.version).toBe(2);
    expect(state.data.projectMembership.members[0].responsibility).toBe(
      "LEADER",
    );
    expect(state.data.projectMembership.history).toHaveLength(1);
  });
});

test("S8 one employee leads one project and contributes elsewhere without unrelated authority", async () => {
  await check(async () => {
    run.boundary =
      "same identity contributor appointment and idempotent replay";
    contribution = appointment(projects[1]);
    const result = await run.graphql(ownerContext!, change, {
      input: contribution,
    });
    expect(result.errors).toBeUndefined();
    contributionChange = result.data.changeProjectMembership.changeId;
    const replay = await run.graphql(ownerContext!, change, {
      input: contribution,
    });
    expect(replay.data.changeProjectMembership.changeId).toBe(
      contributionChange,
    );
    run.boundary =
      "employee switches contextual responsibilities with the same session";
    await employeePage.goto("/projects");
    await expect(
      employeePage.getByRole("link", { name: projects[0].name, exact: true }),
    ).toBeVisible();
    await expect(
      employeePage.getByRole("link", { name: projects[1].name, exact: true }),
    ).toBeVisible();
    await expect(
      employeePage.getByRole("link", { name: projects[2].name, exact: true }),
    ).toHaveCount(0);
    await employeePage
      .getByRole("link", { name: projects[0].name, exact: true })
      .click();
    await expect(
      employeePage.getByRole("heading", {
        name: "Your role: Team leader",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      employeePage.getByRole("heading", {
        name: "Manage project membership",
        exact: true,
      }),
    ).toHaveCount(0);
    await employeePage.goto(`/projects/${projects[1].id}/members`);
    await expect(
      employeePage.getByRole("heading", {
        name: "Your role: Contributor",
        exact: true,
      }),
    ).toBeVisible();
    expect(
      await employeePage.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    run.boundary =
      "member cannot grant authority or enumerate unrelated candidates";
    const forbidden = await run.graphql(
      employeeContext!,
      change,
      { input: appointment(projects[2]) },
      run.secondary,
    );
    expect(forbidden.errors[0].extensions.code).toBe("FORBIDDEN");
    const candidates = await run.graphql(
      employeeContext!,
      "query($id:ID!){projectCandidates(id:$id){candidates{accountId}}}",
      { id: projects[0].id },
      run.secondary,
    );
    expect(candidates.errors[0].extensions.code).toBe("FORBIDDEN");
    const unrelated = await run.graphql(
      employeeContext!,
      membership,
      { id: projects[2].id },
      run.secondary,
    );
    expect(unrelated.errors[0].extensions.reason).toBe("project_not_found");
    await employeePage.goto(`/projects/${projects[2].id}/members`);
    await expect(
      employeePage.getByRole("heading", {
        name: "This page isn’t available.",
        exact: true,
      }),
    ).toBeVisible();
    const viewer = await run.graphql(
      employeeContext!,
      "{viewer{companyRoles}}",
      {},
      run.secondary,
    );
    expect(viewer.data.viewer.companyRoles).toEqual(["EMPLOYEE"]);
  });
});

test("S8 current eligibility, immediate revocation, administrator history and origin checks", async () => {
  await check(async () => {
    run.boundary = "inactive employee loses current API authority";
    const token = await run.token(employeeContext!, run.secondary);
    run.people("project_other_active", "false");
    const inactive = await employeeContext!.request.post(
      "http://127.0.0.1:8020/graphql",
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { query: membership, variables: { id: projects[0].id } },
      },
    );
    expect(inactive.status()).toBe(403);
    run.people("project_other_active", "true");
    run.people("role", "ADMIN");
    run.boundary = "HR is not an eligible appointment target";
    run.people("project_other_role", "HR");
    const ineligible = await run.graphql(ownerContext!, change, {
      input: appointment(projects[2]),
    });
    expect(ineligible.errors[0].extensions.reason).toBe("member_not_eligible");
    run.people("project_other_role", "EMPLOYEE");
    run.boundary =
      "administrator removal preserves history and immediately removes project access";
    const removed = await run.graphql(ownerContext!, change, {
      input: appointment(projects[0], {
        version: 2,
        action: "remove",
        responsibility: "LEADER",
      }),
    });
    expect(removed.errors).toBeUndefined();
    await employeePage.goto(`/projects/${projects[0].id}/members`);
    await expect(
      employeePage.getByRole("heading", {
        name: "This page isn’t available.",
        exact: true,
      }),
    ).toBeVisible();
    const revoked = await run.graphql(
      employeeContext!,
      membership,
      { id: projects[0].id },
      run.secondary,
    );
    expect(revoked.errors[0].extensions.reason).toBe("project_not_found");
    const state = await run.graphql(ownerContext!, membership, {
      id: projects[0].id,
    });
    expect(state.data.projectMembership.history).toHaveLength(2);
    expect(state.data.projectMembership.members[0].active).toBe(false);
    expect(state.data.projectMembership.project.creatorId).toBe(run.runId);
    expect(state.data.projectMembership.project.ownerId).toBe(run.runId);
    expect(
      (
        await ownerContext!.request.post(
          "http://127.0.0.1:3020/projects/membership-command",
          { headers: { Origin: "http://untrusted.invalid" }, data: {} },
        )
      ).status(),
    ).toBe(403);
    expect(
      (
        await employeeContext!.request.post(
          "http://127.0.0.1:3020/projects/membership-command",
          {
            headers: { Origin: "http://127.0.0.1:3020" },
            data: appointment(projects[2]),
          },
        )
      ).status(),
    ).toBe(403);
  });
});
