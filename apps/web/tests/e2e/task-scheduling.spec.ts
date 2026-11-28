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
const taskIds: string[] = [];
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
    throw new Error(`S12 boundary failed: ${run.boundary}`);
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
  run.diagnosticScope = "s12";
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
            objectives: "Owned S12 acceptance",
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
            duties: `Owned S12 leader ${run.runId}`,
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

const scheduleQuery =
  "query($id:ID!){projectSchedule(id:$id){canPlan state forecastAt tasks{title plan{id requestedStart duration dueAt startsAt readiness} original{dueAt}} overlaps{taskId otherTaskId} history{id}}}";
const previewMutation =
  "mutation($input:PreviewTaskScheduleInput!){previewTaskSchedule(input:$input){previewId after{state forecastAt tasks{id effectiveStart dueAt}}}}";
const commitMutation =
  "mutation($input:CommitTaskScheduleInput!){commitTaskSchedule(input:$input){projectVersion scheduleVersion}}";
async function planTask(taskId: string, prerequisites: string[] = []) {
  const current = await state();
  const task = current.tasks.find((t: { id: string }) => t.id === taskId);
  const preview = await run.graphql(
    leader,
    previewMutation,
    {
      input: {
        projectId: project.id,
        taskId,
        projectVersion: current.project.version,
        version: task.details.version,
        requestedStart: "2030-01-02",
        duration: 2,
        prerequisites,
        reason: `Owned S12 plan ${run.runId}`,
      },
    },
    run.primary,
  );
  expect(preview.errors).toBeUndefined();
  const saved = await run.graphql(
    leader,
    commitMutation,
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
  return preview.data.previewTaskSchedule;
}
test("S12 leader previews and confirms a private working-day schedule through the UI", async () => {
  await check("owned task setup and confirmed schedule", async () => {
    for (let index = 0; index < 3; index++) {
      const current = await state();
      const result = await run.graphql(
        leader,
        mutation,
        {
          input: {
            projectId: project.id,
            projectVersion: current.project.version,
            taskId: null,
            version: 0,
            action: "CREATE",
            requestId: crypto.randomUUID(),
            title: `S12 task ${index} ${run.runId}`,
            instructions: `Owned instructions ${run.runId}`,
            acceptanceCriteria: `Owned criteria ${run.runId}`,
            assigneeId: index === 2 ? contributorId : leaderId,
            reason: `Owned S12 task ${run.runId}`,
            confirm: true,
          },
        },
        run.primary,
      );
      expect(result.errors).toBeUndefined();
      taskIds.push(result.data.changeTask.taskId);
    }
    await page.goto(`/projects/${project.id}/schedule`);
    await page
      .getByText(`Schedule S12 task 0 ${run.runId}`, { exact: true })
      .click();
    const form = page.locator("form").filter({
      has: page.locator(`input[name=taskId][value="${taskIds[0]}"]`),
    });
    await form
      .getByLabel("Requested start", { exact: true })
      .fill("2030-01-02");
    await form.getByLabel("Working-day duration", { exact: true }).fill("2");
    await form
      .getByLabel("Reason", { exact: true })
      .fill(`Owned S12 plan ${run.runId}`);
    const previewResponse = page.waitForResponse(
      (response) =>
        new URL(response.url()).origin === appOrigin &&
        new URL(response.url()).pathname === "/projects/schedule-command" &&
        response.request().method() === "POST" &&
        response.request().postDataJSON()?.action === "preview",
    );
    await form
      .getByRole("button", { name: "Preview schedule", exact: true })
      .click();
    const submittedPreview = await previewResponse;
    expect(submittedPreview.ok()).toBe(true);
    const previewData = await submittedPreview.json();
    const scheduledPoint = previewData.after.tasks.find(
      (row: { id: string }) => row.id === taskIds[0],
    );
    const projectTime = new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: previewData.timezone,
    }).format(new Date(scheduledPoint.dueAt));
    const impact = page.getByRole("region", {
      name: "Schedule impact preview",
    });
    await expect(impact).toContainText(projectTime);
    await expect(
      impact.getByRole("heading", { name: "Review schedule impact" }),
    ).toBeVisible();
    await impact
      .getByLabel(
        "I reviewed the affected task paths and confirm this schedule revision.",
      )
      .check();
    await impact
      .getByRole("button", { name: "Save confirmed schedule", exact: true })
      .click();
    await expect(page.getByText(/Original task commitment:/)).toBeVisible();
    const result = await run.graphql(
      leader,
      scheduleQuery,
      { id: project.id },
      run.primary,
    );
    expect(result.errors).toBeUndefined();
    expect(result.data.projectSchedule.state).toBe("UNASSESSED");
    expect(result.data.projectSchedule.forecastAt).toBeNull();
  });
});
test("S12 dependencies preserve handoffs and parallel work shows workload warnings", async () => {
  await check("dependency paths and explicit capacity warnings", async () => {
    await planTask(taskIds[1], [taskIds[0]]);
    await planTask(taskIds[2]);
    const result = await run.graphql(
      leader,
      scheduleQuery,
      { id: project.id },
      run.primary,
    );
    expect(result.errors).toBeUndefined();
    const work = result.data.projectSchedule;
    expect(work.state).toBe("ASSESSED");
    const first = work.tasks.find(
      (t: { plan: { id: string } }) => t.plan.id === taskIds[0],
    );
    const second = work.tasks.find(
      (t: { plan: { id: string } }) => t.plan.id === taskIds[1],
    );
    expect(new Date(second.plan.startsAt).valueOf()).toBeGreaterThan(
      new Date(first.plan.dueAt).valueOf(),
    );
    expect(second.plan.readiness).toBe("WAITING_FOR_PREREQUISITES");
    await planTask(taskIds[1]);
    await page.goto(`/projects/${project.id}/schedule`);
    await expect(
      page.getByRole("heading", { name: "Workload warnings", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(/not hourly effort or a capacity guarantee/),
    ).toBeVisible();
  });
});
test("S12 cycle rejection, owner oversight and colleague schedule privacy remain enforced", async () => {
  await check("cycle and privacy boundaries", async () => {
    await planTask(taskIds[1], [taskIds[0]]);
    const current = await state(),
      task = current.tasks.find((t: { id: string }) => t.id === taskIds[0]);
    const denied = await run.graphql(
      leader,
      previewMutation,
      {
        input: {
          projectId: project.id,
          taskId: taskIds[0],
          projectVersion: current.project.version,
          version: task.details.version,
          requestedStart: "2030-01-02",
          duration: 2,
          prerequisites: [taskIds[1]],
          reason: `Owned cycle ${run.runId}`,
        },
      },
      run.primary,
    );
    expect(denied.errors[0].extensions.reason).toBe("dependency_cycle");
    const peer = await run.graphql(
      member,
      scheduleQuery,
      { id: project.id },
      run.peer,
    );
    expect(peer.errors).toBeUndefined();
    expect(
      peer.data.projectSchedule.tasks.map(
        (t: { plan: { id: string } }) => t.plan.id,
      ),
    ).toEqual([taskIds[2]]);
    expect(peer.data.projectSchedule.history).toEqual([]);
    expect(peer.data.projectSchedule.forecastAt).toBeNull();
    await memberPage.goto(`/projects/${project.id}/schedule`);
    await expect(
      memberPage.getByRole("heading", {
        name: `S12 task 0 ${run.runId}`,
        exact: true,
      }),
    ).toHaveCount(0);
    await ownerPage.goto(`/manager/projects/${project.id}/schedule`);
    await expect(
      ownerPage.getByRole("heading", {
        name: "Plan a task schedule",
        exact: true,
      }),
    ).toHaveCount(0);
    const memberDenied = await run.graphql(
      member,
      previewMutation,
      {
        input: {
          projectId: project.id,
          taskId: taskIds[2],
          projectVersion: current.project.version,
          version: 1,
          requestedStart: "2030-01-02",
          duration: 2,
          prerequisites: [],
          reason: `Owned denied ${run.runId}`,
        },
      },
      run.peer,
    );
    expect(memberDenied.errors[0].extensions.code).toBe("FORBIDDEN");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    const cross = await leader.request.post("/projects/schedule-command", {
      headers: { Origin: "https://foreign.invalid" },
      data: { action: "preview", input: {} },
    });
    expect(cross.status()).toBe(403);
  });
});
test("S12 a removed leader immediately loses schedule read and planning access", async () => {
  await check("current leader revocation", async () => {
    const current = await ownerGraphql(
      "query($id:ID!){project(id:$id){id version}}",
      { id: project.id },
    );
    expect(current.errors).toBeUndefined();
    const removed = await ownerGraphql(
      "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
      {
        input: {
          projectId: project.id,
          version: current.data.project.version,
          requestId: crypto.randomUUID(),
          accountId: leaderId,
          action: "remove",
          responsibility: "LEADER",
          duties: `Owned S12 revocation ${run.runId}`,
          confirm: true,
        },
      },
    );
    expect(removed.errors).toBeUndefined();
    const denied = await run.graphql(
      leader,
      scheduleQuery,
      { id: project.id },
      run.primary,
    );
    expect(denied.errors[0].extensions.reason).toBe("project_not_found");
    const deniedWrite = await run.graphql(
      leader,
      previewMutation,
      {
        input: {
          projectId: project.id,
          taskId: taskIds[0],
          projectVersion: removed.data.changeProjectMembership.version,
          version: 1,
          requestedStart: "2030-01-02",
          duration: 2,
          prerequisites: [],
          reason: `Owned denied after removal ${run.runId}`,
        },
      },
      run.primary,
    );
    expect(deniedWrite.errors[0].extensions.reason).toBe("project_not_found");

    const response = await page.goto(`/projects/${project.id}/schedule`);
    expect(response?.status()).toBe(404);
    await expect(
      page.getByRole("heading", { name: "Plan a task schedule", exact: true }),
    ).toHaveCount(0);
  });
});
