import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { ProjectAcceptance } from "./project-acceptance-support";

test.describe.configure({ mode: "serial" });
const run = new ProjectAcceptance();
let owner: BrowserContext;
let member: BrowserContext;
let memberPage: Page;
let leader: BrowserContext;
let ownerPage: Page;
let page: Page;
let project: { id: string; version: number };
let leaderId: string;
let contributorId: string;
let taskId: string;
const query =
  "query($id:ID!){projectTasks(id:$id){canPlan project{id version} tasks{id title status assigneeName details{instructions acceptanceCriteria version assigneeId history{id action before after}}}}}";
const mutation =
  "mutation($input:ChangeTaskInput!){changeTask(input:$input){taskId version projectVersion}}";
async function check(stage: string, work: () => Promise<void>) {
  run.boundary = stage;
  run.checkpoint(test.info().project.name);
  try {
    await work();
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S11 boundary failed: ${run.boundary}`);
  }
}
async function state(context = leader, identity = run.primary) {
  const result = await run.graphql(
    context,
    query,
    { id: project.id },
    identity,
  );
  expect(result.errors).toBeUndefined();
  return result.data.projectTasks;
}
async function ownerGraphql(
  document: string,
  variables: Record<string, unknown>,
) {
  return run.graphql(owner, document, variables, run.secondary);
}
let identitiesReady = false;
let projectReady = false;
test.beforeAll(async () => {
  run.diagnosticScope = "s11";
  await check("owned disposable identities", async () => {
    await run.setup(true);
    identitiesReady = true;
  });
});
test.beforeAll(async ({ browser }) => {
  await check(
    "owned manager project and employee leader appointment",
    async () => {
      if (!identitiesReady)
        throw new Error("Identity preparation did not complete");
      owner = await browser.newContext({
        baseURL: "http://127.0.0.1:3020",
        viewport: test.info().project.use.viewport,
      });
      leader = await browser.newContext({
        baseURL: "http://127.0.0.1:3020",
        viewport: test.info().project.use.viewport,
      });
      member = await browser.newContext({
        baseURL: "http://127.0.0.1:3020",
        viewport: test.info().project.use.viewport,
      });
      memberPage = await member.newPage();
      ownerPage = await owner.newPage();
      page = await leader.newPage();
      run.boundary = "fixture administrator sign-in and calendar";
      run.checkpoint(test.info().project.name);
      await run.login(page);
      const deadline = await run.calendar(leader);
      run.boundary = "owned manager sign-in and project creation";
      run.checkpoint(test.info().project.name);
      await run.login(ownerPage, run.secondary);
      const preview = await ownerGraphql(
        "mutation($input:ProjectPreviewInput!){previewProject(input:$input){previewId}}",
        {
          input: {
            name: `Task breakdown ${run.runId}`,
            objectives: "Owned S11 acceptance",
            deadlineDate: deadline,
          },
        },
      );
      expect(preview.errors).toBeUndefined();
      const created = await ownerGraphql(
        "mutation($input:CreateProjectInput!){createProject(input:$input){id version}}",
        {
          input: {
            requestId: crypto.randomUUID(),
            previewId: preview.data.previewProject.previewId,
            confirm: true,
          },
        },
      );
      expect(created.errors).toBeUndefined();
      project = created.data.createProject;
      run.boundary = "owned employee leader appointment";
      run.checkpoint(test.info().project.name);
      run.people("role", "EMPLOYEE");
      leaderId = run.runId;
      contributorId = run.people("task_peer_inspect", run.peer.id).accountId;
      const appointed = await ownerGraphql(
        "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
        {
          input: {
            projectId: project.id,
            version: project.version,
            requestId: crypto.randomUUID(),
            accountId: leaderId,
            action: "appoint",
            responsibility: "LEADER",
            duties: `Owned S11 leader ${run.runId}`,
            confirm: true,
          },
        },
      );
      expect(appointed.errors).toBeUndefined();
      project.version = appointed.data.changeProjectMembership.version;
      projectReady = true;
    },
  );
});
test.beforeAll(async () => {
  await check("owned employee contributor appointment", async () => {
    if (!projectReady) throw new Error("Project preparation did not complete");
    const appointed = await ownerGraphql(
      "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
      {
        input: {
          projectId: project.id,
          version: project.version,
          requestId: crypto.randomUUID(),
          accountId: contributorId,
          action: "appoint",
          responsibility: "CONTRIBUTOR",
          duties: `Owned contributor ${run.runId}`,
          confirm: true,
        },
      },
    );
    expect(appointed.errors).toBeUndefined();
    project.version = appointed.data.changeProjectMembership.version;
    await run.login(memberPage, run.peer);
  });
});
test.afterAll(async () => {
  const failures: unknown[] = [];
  for (const [context, identity] of [
    [member, run.peer],
    [leader, run.primary],
    [owner, run.secondary],
  ] as const) {
    if (!context) continue;
    try {
      await run.sessions(context, identity);
    } catch (error) {
      run.diagnostic(error, test.info().project.name);
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
    run.diagnostic(error, test.info().project.name);
    failures.push(error);
  }
  expect(failures.length).toBe(0);
});
test("S11 leader creates one confirmed task and current assignee sees private instructions", async () => {
  await check(
    "confirmed task creation and contributor write denial",
    async () => {
      await page.goto(`/projects/${project.id}/tasks`);
      await expect(
        page.getByText("TEAM LEADER WORKSPACE", { exact: true }),
      ).toBeVisible();
      const form = page.getByRole("group", {
        name: "Create task",
        exact: true,
      });
      await form
        .getByLabel("Task title", { exact: true })
        .fill(`Owned task ${run.runId}`);
      await form
        .getByRole("textbox", { name: "Instructions", exact: true })
        .fill(`Private instructions ${run.runId}`);
      await form
        .getByRole("textbox", { name: "Acceptance criteria", exact: true })
        .fill(`Private criteria ${run.runId}`);
      await form
        .getByRole("combobox", { name: "Assign to", exact: true })
        .selectOption(contributorId);
      await form
        .getByLabel("Reason", { exact: true })
        .fill(`Owned creation ${run.runId}`);
      await form.getByLabel("I confirm this task planning change.").check();
      await form
        .getByRole("button", { name: "Create task", exact: true })
        .click();
      await expect(
        page.getByRole("heading", {
          name: `Owned task ${run.runId}`,
          exact: true,
        }),
      ).toBeVisible();
      const result = await state();
      expect(result.tasks).toHaveLength(1);
      taskId = result.tasks[0].id;
      expect(
        (await state(member, run.peer)).tasks[0].details.instructions,
      ).toBe(`Private instructions ${run.runId}`);
      const denied = await run.graphql(
        member,
        "query($id:ID!){taskCandidates(id:$id){candidates{accountId}}}",
        { id: project.id },
        run.peer,
      );
      expect(denied.errors[0].extensions.code).toBe("FORBIDDEN");
      const deniedWrite = await run.graphql(
        member,
        mutation,
        {
          input: {
            projectId: project.id,
            projectVersion: result.project.version,
            requestId: crypto.randomUUID(),
            taskId: null,
            version: 0,
            action: "CREATE",
            title: `Denied task ${run.runId}`,
            instructions: "Denied contributor planning",
            acceptanceCriteria: "Denied criteria",
            assigneeId: contributorId,
            reason: "Contributor cannot plan",
            confirm: true,
          },
        },
        run.peer,
      );
      expect(deniedWrite.errors[0].extensions.code).toBe("FORBIDDEN");
      expect((await state()).tasks).toHaveLength(1);

      expect(
        (
          await owner.request.post("/projects/task-command", {
            headers: { Origin: "http://untrusted.invalid" },
            data: {},
          })
        ).status(),
      ).toBe(403);
    },
  );
});
test("S11 instruction edits retain history and repeat safely", async () => {
  await check("instruction edit and idempotent replay", async () => {
    await page.goto(`/projects/${project.id}/tasks`);
    await page.getByText("Planning changes", { exact: true }).click();
    const form = page.getByRole("group", {
      name: "Edit task instructions",
      exact: true,
    });
    await form
      .getByRole("textbox", { name: "Instructions", exact: true })
      .fill(`Revised instructions ${run.runId}`);
    await form
      .getByLabel("Reason", { exact: true })
      .fill(`Owned edit ${run.runId}`);
    await form.getByLabel("I confirm this task planning change.").check();
    const submitted = page.waitForRequest(
      (r) =>
        new URL(r.url()).pathname === "/projects/task-command" &&
        r.method() === "POST",
    );
    await form
      .getByRole("button", { name: "Edit task instructions", exact: true })
      .click();
    const input = (await submitted).postDataJSON().input;
    await expect(
      page
        .getByRole("paragraph")
        .filter({ hasText: new RegExp(`^Revised instructions ${run.runId}$`) }),
    ).toBeVisible();
    expect(
      (await run.graphql(leader, mutation, { input }, run.primary)).errors,
    ).toBeUndefined();
    const result = await state();
    expect(result.tasks).toHaveLength(1);
    expect(result.tasks[0].details.history).toHaveLength(2);
  });
});
test("S11 reassignment transfers private access and retains the previous assignee", async () => {
  await check("single-assignee reassignment and peer privacy", async () => {
    await page.goto(`/projects/${project.id}/tasks`);
    await page.getByText("Planning changes", { exact: true }).click();
    const form = page.getByRole("group", {
      name: "Reassign task",
      exact: true,
    });
    await form
      .getByRole("combobox", { name: "Assign to", exact: true })
      .selectOption(leaderId);
    await form
      .getByLabel("Reason", { exact: true })
      .fill(`Owned handover ${run.runId}`);
    await form.getByLabel("I confirm this task planning change.").check();
    await Promise.all([
      page.waitForEvent("domcontentloaded"),
      form.getByRole("button", { name: "Reassign task", exact: true }).click(),
    ]);
    await expect(
      page.getByRole("heading", {
        name: `Owned task ${run.runId}`,
        exact: true,
      }),
    ).toBeVisible();
    const result = await state();
    expect(result.tasks).toHaveLength(1);
    expect(result.tasks[0].id).toBe(taskId);
    expect(result.tasks[0].details.assigneeId).toBe(leaderId);
    const history = result.tasks[0].details.history;
    expect(history).toHaveLength(3);
    expect(JSON.parse(history[0].before).assignee_id).toBe(contributorId);
    expect(JSON.parse(history[0].after).assignee_id).toBe(leaderId);
    const peer = await state(member, run.peer);
    expect(peer.tasks[0].details).toBeNull();
    await memberPage.goto(`/projects/${project.id}/tasks`);
    await expect(
      memberPage.getByText(`Revised instructions ${run.runId}`, {
        exact: true,
      }),
    ).toHaveCount(0);
    await page
      .getByText("Planning and reassignment history", { exact: true })
      .click();
    await expect(
      page.getByText(`Owned handover ${run.runId}`, { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
});
test("S11 owner oversight does not grant planning and revoked leaders lose access", async () => {
  await check(
    "owner read-only oversight and immediate leader revocation",
    async () => {
      const oversight = await state(owner, run.secondary);
      expect(oversight.canPlan).toBe(false);
      expect(oversight.tasks[0].details.history).toHaveLength(3);
      const candidates = await ownerGraphql(
        "query($id:ID!){taskCandidates(id:$id){candidates{accountId}}}",
        { id: project.id },
      );
      expect(candidates.errors[0].extensions.code).toBe("FORBIDDEN");
      const removed = await ownerGraphql(
        "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
        {
          input: {
            projectId: project.id,
            version: oversight.project.version,
            requestId: crypto.randomUUID(),
            accountId: leaderId,
            action: "remove",
            responsibility: "LEADER",
            duties: `Owned removal ${run.runId}`,
            confirm: true,
          },
        },
      );
      expect(removed.errors).toBeUndefined();
      expect(
        (await run.graphql(leader, query, { id: project.id }, run.primary))
          .errors[0].extensions.reason,
      ).toBe("project_not_found");
      const denied = await run.graphql(
        leader,
        mutation,
        {
          input: {
            projectId: project.id,
            projectVersion: oversight.project.version,
            taskId,
            version: 3,
            action: "EDIT",
            requestId: crypto.randomUUID(),
            title: `Owned task ${run.runId}`,
            instructions: "Denied edit",
            acceptanceCriteria: "Denied criteria",
            assigneeId: null,
            reason: "Denied revoked leader",
            confirm: true,
          },
        },
        run.primary,
      );
      expect(denied.errors[0].extensions.reason).toBe("project_not_found");
    },
  );
});
