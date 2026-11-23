import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import type { CreateCoordinationMutationVariables } from "@/shared/api/generated";
import { ProjectAcceptance } from "./project-acceptance-support";

test.describe.configure({ mode: "serial" });
const run = new ProjectAcceptance();
let context: BrowserContext;
let page: Page;
let secondary: BrowserContext | undefined;
let employee: string;
let project: { id: string; version: number };
let appointedVersion: number;
let meeting: CreateCoordinationMutationVariables["input"];
let records: unknown;
const change =
  "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}";
const mutation =
  "mutation($input:CreateCoordinationInput!){createCoordination(input:$input){id topic version recipients{responseState}}}";
const query =
  "query($id:ID!){projectCoordination(id:$id){records{id dueAt followUps{note} recipients{responseState}}}}";
async function check(stage: string, work: () => Promise<void>) {
  run.boundary = stage;
  run.checkpoint(test.info().project.name);
  try {
    await work();
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S9 boundary failed: ${run.boundary}`);
  }
}

test.beforeAll(async ({ browser }) => {
  run.diagnosticScope = "s9";
  await check("owned fixture setup", async () => {
    await run.setup();
    context = await browser.newContext({
      baseURL: "http://127.0.0.1:3020",
      viewport: test.info().project.use.viewport,
    });
    page = await context.newPage();
    await run.login(page);
    const deadline = await run.calendar(context);
    run.people("role", "MANAGER");
    run.people("project_other_role", "EMPLOYEE");
    employee = run.people("project_other_inspect").accountId;
    await page.goto("/auth/ready");
    const preview = await run.graphql(
      context,
      "mutation($input:ProjectPreviewInput!){previewProject(input:$input){previewId}}",
      {
        input: {
          name: `Coordination ${run.runId}`,
          objectives: "S9 scoped acceptance",
          deadlineDate: deadline,
        },
      },
    );
    expect(preview.errors).toBeUndefined();
    const created = await run.graphql(
      context,
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
    const appointed = await run.graphql(context, change, {
      input: {
        projectId: project.id,
        requestId: crypto.randomUUID(),
        version: project.version,
        accountId: employee,
        action: "appoint",
        responsibility: "LEADER",
        duties: "Coordinate acceptance",
        confirm: true,
      },
    });
    expect(appointed.errors).toBeUndefined();
    appointedVersion = appointed.data.changeProjectMembership.version;
  });
});
test.beforeEach(async () => {
  await page.goto("/auth/ready");
});
test.afterAll(async () => {
  const failures: unknown[] = [];
  for (const [browserContext, identity] of [
    [secondary, run.secondary],
    [context, run.primary],
  ] as const) {
    if (!browserContext) continue;
    try {
      await run.sessions(browserContext, identity);
    } catch (error) {
      failures.push(error);
      run.diagnostic(error, test.info().project.name);
    }
    try {
      await browserContext.close();
    } catch (error) {
      failures.push(error);
    }
  }
  try {
    await run.cleanup();
  } catch (error) {
    failures.push(error);
    run.diagnostic(error, test.info().project.name);
  }
  if (failures.length) throw new Error("S9 scoped cleanup failed");
});

test("S9 confirmed update request and retained follow-up history", async () => {
  await check(
    "confirmed update request UI and honest pending state",
    async () => {
      run.boundary = "confirmed update request UI and honest pending state";
      run.checkpoint(test.info().project.name);
      await page.goto(`/manager/projects/${project.id}/coordination`);
      const form = page.getByRole("group", {
        name: "New coordination request",
        exact: true,
      });
      await form.getByLabel("Topic", { exact: true }).fill("Delivery update");
      await form
        .getByLabel("Request details")
        .fill("Progress, blockers and next steps");
      await form
        .locator(`input[name="recipient"][value="${employee}"]`)
        .check();
      await form.getByLabel("Response required by").fill("2030-01-10T10:00");
      await form.getByLabel("I have reviewed this request.").check();
      await form
        .getByRole("button", { name: "Create request", exact: true })
        .click();
      await expect(
        page.getByRole("heading", { name: "Delivery update", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText(/Acknowledgement: PENDING.*Response: PENDING/),
      ).toBeVisible();
      const follow = page.getByRole("group", {
        name: "Record a follow-up",
        exact: true,
      });
      await follow
        .getByLabel("Follow-up note")
        .fill("Review outstanding response");
      await follow
        .getByLabel("Next follow-up", { exact: true })
        .fill("2030-01-11T10:00");
      await follow.getByLabel("I have reviewed this request.").check();
      await follow
        .getByRole("button", { name: "Save follow-up", exact: true })
        .click();
      await expect(
        page.getByText("Review outstanding response", { exact: true }),
      ).toBeVisible();
    },
  );
});

test("S9 internal meeting creation and duplicate prevention", async () => {
  await check("meeting creation and duplicate prevention", async () => {
    meeting = {
      projectId: project.id,
      requestId: crypto.randomUUID(),
      kind: "MEETING",
      topic: "Internal review",
      details: "Review delivery",
      dueAt: "2030-01-12T10:00:00Z",
      location: "Cabin 2",
      acknowledgementRequired: true,
      recipients: [employee],
      confirm: true,
    };
    const result = await run.graphql(context, mutation, { input: meeting });
    expect(result.errors).toBeUndefined();
    expect(await run.graphql(context, mutation, { input: meeting })).toEqual(
      result,
    );
    const resultRecords = await run.graphql(context, query, { id: project.id });
    records = resultRecords.data.projectCoordination.records;
    expect(records).toHaveLength(2);
  });
});

test("S9 current recipient eligibility and project authorization", async ({
  browser,
}) => {
  await check(
    "current recipient eligibility and project authorization",
    async () => {
      secondary = await browser.newContext({
        baseURL: "http://127.0.0.1:3020",
      });
      await run.login(await secondary.newPage(), run.secondary);
      const denied = await run.graphql(
        secondary,
        query,
        { id: project.id },
        run.secondary,
      );
      expect(denied.errors[0].extensions.code).toBe("FORBIDDEN");
      run.people("project_other_role", "MANAGER");
      const unrelated = await run.graphql(
        secondary,
        query,
        { id: project.id },
        run.secondary,
      );
      expect(unrelated.errors[0].extensions.reason).toBe("project_not_found");
      run.people("project_other_role", "EMPLOYEE");
      const removed = await run.graphql(context, change, {
        input: {
          projectId: project.id,
          requestId: crypto.randomUUID(),
          version: appointedVersion,
          accountId: employee,
          action: "remove",
          responsibility: "LEADER",
          duties: "",
          confirm: true,
        },
      });
      expect(removed.errors).toBeUndefined();
      const rejected = await run.graphql(context, mutation, {
        input: { ...meeting, requestId: crypto.randomUUID() },
      });
      expect(rejected.errors[0].extensions.reason).toBe(
        "coordination_recipient_ineligible",
      );
      expect(
        (await run.graphql(context, query, { id: project.id })).data
          .projectCoordination.records,
      ).toEqual(records);
      expect(
        (
          await context.request.post("/projects/coordination-command", {
            headers: { Origin: "http://untrusted.invalid" },
            data: {},
          })
        ).status(),
      ).toBe(403);
    },
  );
});

test("S9 responsive coordination layout", async () => {
  await check("responsive coordination layout", async () => {
    run.boundary = "responsive coordination layout";
    run.checkpoint(test.info().project.name);
    await page.goto(`/manager/projects/${project.id}/coordination`);
    await expect(
      page.getByRole("heading", { name: "Internal review", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  });
});
