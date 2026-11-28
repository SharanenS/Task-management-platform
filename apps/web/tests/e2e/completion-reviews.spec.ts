import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import {
  ProjectAcceptance,
  appOrigin,
  registerProjectCleanup,
} from "./project-acceptance-support";

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
    throw new Error(`S13 boundary failed: ${run.boundary}`);
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
  run.diagnosticScope = "s13";
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
        timezoneId: "America/Los_Angeles",
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
            objectives: "Owned S13 acceptance",
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
            duties: `Owned S13 leader ${run.runId}`,
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
registerProjectCleanup(run, () => [
  [member, run.peer],
  [leader, run.primary],
  [owner, run.secondary],
]);

const reviewQuery =
  "query($id:ID!){projectReviews(id:$id,page:0){project{id version} isLeader canReview fallbackId tasks{id title status version own canAct canReview progress blocker instructions submissions{id pending summary version decision{outcome selfApproval feedback fallbackId}}}}}";
const executeMutation =
  "mutation($input:ExecuteTaskInput!){executeTask(input:$input){taskId version projectVersion}}";
const decideMutation =
  "mutation($input:ReviewCompletionInput!){reviewCompletion(input:$input){taskId version projectVersion}}";
const ownTitle = `Leader own work ${run.runId}`;
const memberTitle = `Contributor work ${run.runId}`;
let ownTask: string;
let memberTask: string;
async function reviews(context = leader, identity = run.primary) {
  const result = await run.graphql(
    context,
    reviewQuery,
    { id: project.id },
    identity,
  );
  expect(result.errors).toBeUndefined();
  return result.data.projectReviews;
}
async function createScheduled(
  title: string,
  assigneeId: string,
  prerequisites: string[] = [],
) {
  const current = await state();
  const changed = await run.graphql(
    leader,
    mutation,
    {
      input: {
        projectId: project.id,
        projectVersion: current.project.version,
        taskId: null,
        version: 0,
        requestId: crypto.randomUUID(),
        action: "CREATE",
        title,
        instructions: `Private review instructions ${title}`,
        acceptanceCriteria: `Private review criteria ${title}`,
        assigneeId,
        reason: `Owned S13 task ${run.runId}`,
        confirm: true,
      },
    },
    run.primary,
  );
  expect(changed.errors).toBeUndefined();
  const task = changed.data.changeTask;
  const preview = await run.graphql(
    leader,
    "mutation($input:PreviewTaskScheduleInput!){previewTaskSchedule(input:$input){previewId}}",
    {
      input: {
        projectId: project.id,
        taskId: task.taskId,
        projectVersion: task.projectVersion,
        version: task.version,
        requestedStart: "2020-01-01",
        duration: 1,
        prerequisites,
        reason: `Owned S13 past working-day window ${run.runId}`,
      },
    },
    run.primary,
  );
  expect(preview.errors).toBeUndefined();
  const saved = await run.graphql(
    leader,
    "mutation($input:CommitTaskScheduleInput!){commitTaskSchedule(input:$input){projectVersion}}",
    {
      input: {
        projectId: project.id,
        previewId: preview.data.previewTaskSchedule.previewId,
        requestId: crypto.randomUUID(),
        confirm: true,
      },
    },
    run.primary,
  );
  expect(saved.errors).toBeUndefined();
  return task.taskId as string;
}
async function executionInput(
  id: string,
  action: string,
  context = leader,
  identity = run.primary,
) {
  const workspace = await reviews(context, identity);
  const row = workspace.tasks.find((t: { id: string }) => t.id === id);
  expect(row).toBeTruthy();
  return {
    projectId: project.id,
    taskId: id,
    projectVersion: workspace.project.version,
    version: row.version,
    requestId: crypto.randomUUID(),
    action,
    note: `Owned S13 completion ${run.runId}`,
    progress: row.progress,
    blocker: row.blocker,
    confirm: true,
  };
}
async function execute(
  id: string,
  action: string,
  context = leader,
  identity = run.primary,
) {
  const result = await run.graphql(
    context,
    executeMutation,
    { input: await executionInput(id, action, context, identity) },
    identity,
  );
  expect(result.errors).toBeUndefined();
  return result.data.executeTask;
}
async function reviewInput(
  id: string,
  context = leader,
  identity = run.primary,
) {
  const workspace = await reviews(context, identity);
  const row = workspace.tasks.find((t: { id: string }) => t.id === id);
  return {
    projectId: project.id,
    taskId: id,
    submissionId: row.submissions.find((s: { pending: boolean }) => s.pending)
      .id,
    projectVersion: workspace.project.version,
    version: row.version,
    requestId: crypto.randomUUID(),
    outcome: "APPROVE",
    feedback: `Owned S13 review ${run.runId}`,
    selfConfirm: false,
    confirm: true,
  };
}
async function uiAction(
  target: Page,
  title: string,
  legend: string,
  note: string,
  options: {
    owner?: boolean;
    progress?: string;
    outcome?: string;
    self?: boolean;
  } = {},
) {
  await target.goto(
    `${options.owner ? "/manager/projects" : "/projects"}/${project.id}/reviews`,
  );
  const article = target
    .locator("article")
    .filter({ has: target.getByRole("heading", { name: title, exact: true }) });
  const form = article.getByRole("group", { name: legend, exact: true });
  await form
    .getByRole("textbox", {
      name: /Work note|Completion summary|Review feedback/,
    })
    .fill(note);
  if (options.progress)
    await form
      .getByLabel("Progress percent", { exact: true })
      .fill(options.progress);
  if (options.outcome)
    await form
      .getByRole("combobox", { name: "Decision", exact: true })
      .selectOption(options.outcome);
  await form.getByRole("checkbox", { name: /I confirm this/ }).check();
  if (options.self)
    await form
      .getByRole("checkbox", { name: /I explicitly approve my own submission/ })
      .check();
  const response = target.waitForResponse(
    (r) =>
      new URL(r.url()).origin === appOrigin &&
      new URL(r.url()).pathname === "/projects/review-command" &&
      r.request().method() === "POST",
  );
  const loaded = target.waitForEvent("load");
  await form.getByRole("button", { name: legend, exact: true }).click();
  expect((await response).status()).toBe(200);
  await loaded;
}

test("S13 leader own execution submits separately and requires explicit self approval", async () => {
  await check(
    "leader own start progress submission and self confirmation",
    async () => {
      ownTask = await createScheduled(ownTitle, leaderId);
      await uiAction(page, ownTitle, "Start my task", "Owned start");
      await uiAction(page, ownTitle, "Record my progress", "Work reported", {
        progress: "100",
      });
      expect(
        (await reviews()).tasks.find((t: { id: string }) => t.id === ownTask)
          .status,
      ).toBe("IN_PROGRESS");
      await uiAction(
        page,
        ownTitle,
        "Submit for review",
        "Owned completion evidence",
      );
      const input = await reviewInput(ownTask);
      const denied = await run.graphql(
        leader,
        decideMutation,
        { input },
        run.primary,
      );
      expect(denied.errors[0].extensions.reason).toBe(
        "explicit_self_approval_required",
      );
      expect(
        (await reviews()).tasks.find((t: { id: string }) => t.id === ownTask)
          .status,
      ).toBe("AWAITING_REVIEW");
      await uiAction(
        page,
        ownTitle,
        "Record review decision",
        "Explicitly reviewed my own work",
        { self: true },
      );
      const row = (await reviews()).tasks.find(
        (t: { id: string }) => t.id === ownTask,
      );
      expect(row.status).toBe("COMPLETED");
      expect(row.submissions[0].decision.selfApproval).toBe(true);
      await expect(
        page.getByText("Explicit self-approval", { exact: true }),
      ).toBeVisible();
    },
  );
});

test("S13 leader returns contributor submission and retains resubmission feedback", async () => {
  await check("return for changes and retained resubmission", async () => {
    memberTask = await createScheduled(memberTitle, contributorId);
    await execute(memberTask, "START", member, run.peer);
    await execute(memberTask, "SUBMIT", member, run.peer);
    await uiAction(
      page,
      memberTitle,
      "Record review decision",
      "Provide the missing acceptance evidence",
      { outcome: "RETURN" },
    );
    expect(
      (await reviews(member, run.peer)).tasks.find(
        (t: { id: string }) => t.id === memberTask,
      ).status,
    ).toBe("IN_PROGRESS");
    await execute(memberTask, "SUBMIT", member, run.peer);
    await uiAction(
      page,
      memberTitle,
      "Record review decision",
      "Acceptance evidence verified",
    );
    const row = (await reviews()).tasks.find(
      (t: { id: string }) => t.id === memberTask,
    );
    expect(row.status).toBe("COMPLETED");
    expect(row.submissions).toHaveLength(2);
    expect(row.submissions[1].decision.feedback).toBe(
      "Provide the missing acceptance evidence",
    );
    expect(row.submissions[0].decision.selfApproval).toBe(false);
  });
});

test("S13 awaiting review does not unlock dependent work but approval does", async () => {
  await check("dependency gate through review completion", async () => {
    const parent = await createScheduled(
      `Review gate parent ${run.runId}`,
      leaderId,
    );
    const child = await createScheduled(
      `Review gate child ${run.runId}`,
      leaderId,
      [parent],
    );
    await execute(parent, "START");
    await execute(parent, "SUBMIT");
    const blocked = await run.graphql(
      leader,
      executeMutation,
      { input: await executionInput(child, "START") },
      run.primary,
    );
    expect(blocked.errors[0].extensions.reason).toBe(
      "task_prerequisites_not_ready",
    );
    const input = { ...(await reviewInput(parent)), selfConfirm: true };
    const accepted = await run.graphql(
      leader,
      decideMutation,
      { input },
      run.primary,
    );
    expect(accepted.errors).toBeUndefined();
    expect(
      await run.graphql(leader, decideMutation, { input }, run.primary),
    ).toEqual(accepted);
    await execute(child, "START");
    const row = (await reviews()).tasks.find(
      (t: { id: string }) => t.id === child,
    );
    expect(row.status).toBe("IN_PROGRESS");
  });
});

test("S13 owner review requires an explicit current review scoped absence", async () => {
  await check("owner fallback scope and immediate revocation", async () => {
    const title = `Fallback work ${run.runId}`;
    const id = await createScheduled(title, contributorId);
    await execute(id, "START", member, run.peer);
    await execute(id, "SUBMIT", member, run.peer);
    const input = await reviewInput(id, owner, run.secondary);
    const denied = await ownerGraphql(decideMutation, { input });
    expect(denied.errors[0].extensions.code).toBe("FORBIDDEN");
    const workspace = await reviews(owner, run.secondary);
    const absent = await ownerGraphql(
      "mutation($input:RecordReviewFallbackInput!){recordReviewFallback(input:$input){id active}}",
      {
        input: {
          projectId: project.id,
          projectVersion: workspace.project.version,
          requestId: crypto.randomUUID(),
          leaderId,
          scope: "REVIEWS",
          reason: `Owned S13 absence ${run.runId}`,
          startsAt: new Date(Date.now() - 3600000).toISOString(),
          endsAt: new Date(Date.now() + 3600000).toISOString(),
          confirm: true,
        },
      },
    );
    expect(absent.errors).toBeUndefined();
    expect(absent.data.recordReviewFallback.active).toBe(true);
    await uiAction(
      ownerPage,
      title,
      "Record review decision",
      "Reviewed under explicit absence",
      { owner: true },
    );
    const row = (await reviews(owner, run.secondary)).tasks.find(
      (t: { id: string }) => t.id === id,
    );
    expect(row.submissions[0].decision.fallbackId).toBe(
      absent.data.recordReviewFallback.id,
    );
    const revoked = await ownerGraphql(
      "mutation($input:RevokeReviewFallbackInput!){revokeReviewFallback(input:$input){id active}}",
      {
        input: {
          projectId: project.id,
          recordId: absent.data.recordReviewFallback.id,
          requestId: crypto.randomUUID(),
          reason: `Owned S13 revocation ${run.runId}`,
          confirm: true,
        },
      },
    );
    expect(revoked.errors).toBeUndefined();
    expect(revoked.data.revokeReviewFallback.active).toBe(false);
    const after = await ownerGraphql(decideMutation, { input });
    expect(after.errors[0].extensions.code).toBe("FORBIDDEN");
  });
});

test("S13 peer privacy cross origin and removed leader boundaries remain enforced", async () => {
  await check("review privacy origin and leader revocation", async () => {
    const peer = await reviews(member, run.peer);
    expect(peer.tasks.some((t: { id: string }) => t.id === ownTask)).toBe(
      false,
    );
    const wrong = await leader.request.post("/projects/review-command", {
      headers: { Origin: "https://foreign.invalid" },
      data: { action: "decide", input: {} },
    });
    expect(wrong.status()).toBe(403);
    await page.goto(`/projects/${project.id}/reviews`);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const current = await reviews(owner, run.secondary);
    const removed = await ownerGraphql(
      "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
      {
        input: {
          projectId: project.id,
          version: current.project.version,
          requestId: crypto.randomUUID(),
          accountId: leaderId,
          action: "remove",
          responsibility: "LEADER",
          duties: `Owned S13 removal ${run.runId}`,
          confirm: true,
        },
      },
    );
    expect(removed.errors).toBeUndefined();
    const denied = await run.graphql(
      leader,
      reviewQuery,
      { id: project.id },
      run.primary,
    );
    expect(denied.errors[0].extensions.reason).toBe("project_not_found");
    const write = await run.graphql(
      leader,
      executeMutation,
      {
        input: {
          projectId: project.id,
          taskId: ownTask,
          version: 1,
          projectVersion: removed.data.changeProjectMembership.version,
          requestId: crypto.randomUUID(),
          action: "SUBMIT",
          progress: 100,
          blocker: null,
          note: "Denied after removal",
          confirm: true,
        },
      },
      run.primary,
    );
    expect(write.errors[0].extensions.reason).toBe("project_not_found");
    expect((await page.goto(`/projects/${project.id}/reviews`))?.status()).toBe(
      404,
    );
  });
});
