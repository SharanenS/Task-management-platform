import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import {
  appOrigin,
  ProjectAcceptance,
  registerProjectCleanup,
} from "./project-acceptance-support";

test.describe.configure({ mode: "serial" });
const run = new ProjectAcceptance();
let owner: BrowserContext;
let employee: BrowserContext;
let page: Page;
let employeePage: Page;
let employeeAccount: string;
let project: {
  id: string;
  version: number;
  name: string;
  approvedDeadline: string;
};
let inputs: {
  requests: Record<string, { id: string; version: number }>;
  revisedDate: string;
  projectVersion: number;
};
let revision: string;
const query =
  "query($id:ID!){ownerOversight(id:$id){project{id version approvedDeadline} currentDeadline forecastAt forecastState actualDeliveryAt escalations{id version reason} history{id outcome revisedDeadline previousDeadline}}}";
const mutation =
  "mutation($input:RecordOwnerDecisionInput!){recordOwnerDecision(input:$input){id outcome revisedDeadline}}";

async function check(stage: string, work: () => Promise<void>) {
  run.boundary = stage;
  run.checkpoint(test.info().project.name);
  try {
    await work();
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S10 boundary failed: ${run.boundary}`);
  }
}
async function workspace() {
  const result = await run.graphql(owner, query, { id: project.id });
  expect(result.errors).toBeUndefined();
  return result.data.ownerOversight;
}
function decision(label: string, projectVersion: number, outcome: string) {
  return {
    projectId: project.id,
    escalationId: inputs.requests[label].id,
    requestId: crypto.randomUUID(),
    version: inputs.requests[label].version,
    projectVersion,
    outcome,
    reason: `Owned S10 decision ${run.runId}`,
    affectedTeam: `Owned team ${run.runId}`,
    previewId: null,
    confirm: true,
  };
}

test.beforeAll(async () => {
  run.diagnosticScope = "s10";
  await check("owned identity preparation", async () => {
    await run.setup();
  });
});

test.beforeAll(async ({ browser }) => {
  await check("owned identity, project and leader fixtures", async () => {
    run.people("project_other_role", "EMPLOYEE");
    employeeAccount = run.people("project_other_inspect").accountId;
    owner = await browser.newContext({
      baseURL: "http://127.0.0.1:3020",
      viewport: test.info().project.use.viewport,
    });
    employee = await browser.newContext({
      baseURL: "http://127.0.0.1:3020",
      viewport: test.info().project.use.viewport,
    });
    page = await owner.newPage();
    employeePage = await employee.newPage();
    run.boundary = "owner sign-in and configured company calendar";
    run.checkpoint(test.info().project.name);
    await run.login(page);
    const deadline = await run.calendar(owner);
    run.people("role", "MANAGER");
    await page.goto("/auth/ready");
    run.boundary = "owned project preview and creation";
    run.checkpoint(test.info().project.name);
    const preview = await run.graphql(
      owner,
      "mutation($input:ProjectPreviewInput!){previewProject(input:$input){previewId}}",
      {
        input: {
          name: `Owner oversight ${run.runId}`,
          objectives: "S10 ownership and history acceptance",
          deadlineDate: deadline,
        },
      },
    );
    expect(preview.errors).toBeUndefined();
    const created = await run.graphql(
      owner,
      "mutation($input:CreateProjectInput!){createProject(input:$input){id version name approvedDeadline}}",
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
    run.boundary = "owned project leader appointment";
    run.checkpoint(test.info().project.name);
    const appointed = await run.graphql(
      owner,
      "mutation($input:ChangeProjectMembershipInput!){changeProjectMembership(input:$input){version}}",
      {
        input: {
          projectId: project.id,
          requestId: crypto.randomUUID(),
          version: project.version,
          accountId: employeeAccount,
          action: "appoint",
          responsibility: "LEADER",
          duties: "Owned S10 leader",
          confirm: true,
        },
      },
    );
    expect(appointed.errors).toBeUndefined();
    project.version = appointed.data.changeProjectMembership.version;
    run.boundary = "employee leader sign-in";
    run.checkpoint(test.info().project.name);
    await run.login(employeePage, run.secondary);
  });
});
test.beforeEach(async () => {
  await page.goto("/auth/ready");
});
registerProjectCleanup(run, () => [
  [employee, run.secondary],
  [owner, run.primary],
]);

test("S10 honest empty oversight and current project authority", async () => {
  await check(
    "unassessed empty inbox and unrelated authority rejection",
    async () => {
      await page.goto(`/manager/projects/${project.id}/oversight`);
      await expect(
        page.getByRole("heading", { name: project.name, exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Not assessed", { exact: true }),
      ).toBeVisible();
      const state = await workspace();
      expect(state.forecastAt).toBeNull();
      expect(state.actualDeliveryAt).toBeNull();
      expect(state.escalations).toHaveLength(0);
      expect(state.history).toHaveLength(0);
      const forbidden = await run.graphql(
        employee,
        query,
        { id: project.id },
        run.secondary,
      );
      expect(forbidden.errors[0].extensions.code).toBe("FORBIDDEN");
      run.people("project_other_role", "MANAGER");
      const unrelated = await run.graphql(
        employee,
        query,
        { id: project.id },
        run.secondary,
      );
      expect(unrelated.errors[0].extensions.reason).toBe("project_not_found");
      run.people("project_other_role", "EMPLOYEE");
      expect(
        (
          await owner.request.post("/projects/owner-command", {
            headers: { Origin: "http://untrusted.invalid" },
            data: {},
          })
        ).status(),
      ).toBe(403);
    },
  );
});

test("S10 explicit scoped absence and audited revocation", async () => {
  await check("confirmed leader absence and revocation UI", async () => {
    await page.goto(`/manager/projects/${project.id}/oversight`);
    const form = page.getByRole("group", {
      name: "Record scoped leader absence",
      exact: true,
    });
    await form
      .getByLabel("Absence reason", { exact: true })
      .fill(`Owned absence ${run.runId}`);
    await form
      .getByRole("combobox", { name: "Fallback scope", exact: true })
      .selectOption("REVIEWS");
    await form
      .getByLabel("Starts at", { exact: true })
      .fill(new Date(Date.now() - 86400000).toISOString().slice(0, 16));
    await form
      .getByLabel("Ends at", { exact: true })
      .fill(new Date(Date.now() + 86400000).toISOString().slice(0, 16));
    await form.getByLabel("I confirm this scoped absence change.").check();
    await form
      .getByRole("button", { name: "Record absence", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Active fallback", exact: true }),
    ).toBeVisible();
    const revoke = page.getByRole("group", {
      name: "Revoke fallback record",
      exact: true,
    });
    await revoke
      .getByLabel("Revocation reason", { exact: true })
      .fill(`Owned revocation ${run.runId}`);
    await revoke.getByLabel("I confirm this scoped absence change.").check();
    const reloaded = page.waitForEvent("load");
    const revocation = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return (
        url.origin === appOrigin &&
        url.pathname === "/projects/owner-command" &&
        response.request().method() === "POST" &&
        response.request().postDataJSON()?.command === "fallback-revoke"
      );
    });
    await revoke
      .getByRole("button", { name: "Revoke fallback", exact: true })
      .click();
    const recorded = await revocation;
    expect(recorded.status()).toBe(200);
    await reloaded;
    await expect(
      page.getByRole("heading", { name: "Inactive fallback", exact: true }),
    ).toBeVisible();
  });
});

test("S10 deadline revision preserves baseline and safely replays", async () => {
  await check(
    "fixture-produced escalation and confirmed deadline revision",
    async () => {
      inputs = run.ownerFixture(project.id, "seed");
      await page.goto(`/manager/projects/${project.id}/oversight`);
      const row = page.locator("article").filter({
        has: page.getByText(`Owned S10 revision ${run.runId}`, {
          exact: true,
        }),
      });
      await row
        .getByRole("combobox", { name: "Decision", exact: true })
        .selectOption("REVISE_DEADLINE");
      await row
        .getByLabel("Proposed deadline date", { exact: true })
        .fill(inputs.revisedDate);
      await row
        .getByRole("button", { name: "Preview deadline revision", exact: true })
        .click();
      await expect(
        row.getByRole("heading", {
          name: "Review deadline revision",
          exact: true,
        }),
      ).toBeVisible();
      await row
        .getByLabel("Decision reason", { exact: true })
        .fill(`Owned revision ${run.runId}`);
      await row
        .getByLabel("I confirm this decision and its recorded context.")
        .check();
      const submitted = page.waitForRequest(
        (request) =>
          new URL(request.url()).pathname === "/projects/owner-command" &&
          request.method() === "POST" &&
          request.postDataJSON()?.command === "decide",
      );
      await row
        .getByRole("button", { name: "Record decision", exact: true })
        .click();
      const input = (await submitted).postDataJSON().input;
      await expect(
        page.getByRole("heading", {
          name: "Project deadline revised",
          exact: true,
        }),
      ).toBeVisible();
      const replay = await run.graphql(owner, mutation, { input });
      expect(replay.errors).toBeUndefined();
      const state = await workspace();
      expect(state.history).toHaveLength(1);
      expect(state.escalations).toHaveLength(2);
      expect(state.project.approvedDeadline).toBe(project.approvedDeadline);
      expect(state.forecastState).toBe("STALE");
      expect(state.forecastAt).toBeNull();
      revision = state.currentDeadline;
      expect(revision).toBe(state.history[0].revisedDeadline);
    },
  );
});

test("S10 stale impact is rejected before accepting a late forecast", async () => {
  await check(
    "stale forecast fence and explicit late-forecast context",
    async () => {
      const state = await workspace();
      const stale = await run.graphql(owner, mutation, {
        input: decision("late", state.project.version, "ACCEPT_FORECAST_LATE"),
      });
      expect(stale.errors[0].extensions.reason).toBe(
        "owner_assessment_required",
      );
      const refreshed = run.ownerFixture(
        project.id,
        "refresh",
        inputs.requests.late.id,
      );
      inputs.requests.late.version = refreshed.version;
      const input = decision(
        "late",
        refreshed.projectVersion,
        "ACCEPT_FORECAST_LATE",
      );
      const result = await run.graphql(owner, mutation, { input });
      expect(result.errors).toBeUndefined();
      expect(await run.graphql(owner, mutation, { input })).toEqual(result);
      const after = await workspace();
      expect(after.currentDeadline).toBe(revision);
      expect(after.project.approvedDeadline).toBe(project.approvedDeadline);
      expect(after.actualDeliveryAt).toBeNull();
      expect(after.history).toHaveLength(2);
    },
  );
});

test("S10 unknown impact stays unapproved and decision history is responsive", async () => {
  await check(
    "unassessed request, completed owner decision and responsive history",
    async () => {
      const state = await workspace();
      const forbidden = await run.graphql(owner, mutation, {
        input: decision(
          "unknown",
          state.project.version,
          "ACCEPT_FORECAST_LATE",
        ),
      });
      expect(forbidden.errors[0].extensions.reason).toBe(
        "owner_assessment_required",
      );
      const result = await run.graphql(owner, mutation, {
        input: decision("unknown", state.project.version, "REQUEST_REPLAN"),
      });
      expect(result.errors).toBeUndefined();
      const after = await workspace();
      expect(after.escalations).toHaveLength(0);
      expect(after.history).toHaveLength(3);
      expect(after.currentDeadline).toBe(revision);
      expect(after.project.approvedDeadline).toBe(project.approvedDeadline);
      await page.goto(`/manager/projects/${project.id}/oversight`);
      await expect(
        page.getByRole("heading", {
          name: "Revised plan requested",
          exact: true,
        }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
    },
  );
});
