import { test, expect, type BrowserContext } from "@playwright/test";
import { ProjectAcceptance, appOrigin } from "./project-acceptance-support";
const run = new ProjectAcceptance();
let otherContext: BrowserContext | undefined;
const previewQuery =
  "mutation($input:ProjectPreviewInput!){previewProject(input:$input){previewId deadlineLocal}}";
const createQuery =
  "mutation($input:CreateProjectInput!){createProject(input:$input){id creatorId ownerId}}";
function requestId() {
  return crypto.randomUUID();
}
test.beforeAll(async () => {
  await run.setup();
});
test.afterAll(async () => {
  await run.cleanup();
});
test.afterEach(async ({ context }) => {
  await run.sessions(context);
  if (otherContext) {
    await run.sessions(otherContext, run.secondary);
    await otherContext.close();
    otherContext = undefined;
  }
});
function workingDate(config: {
  week: { weekday: number; working: boolean }[];
  holidays: { date: string }[];
  exceptions: { date: string; working: boolean }[];
}) {
  const date = new Date("2030-01-07T00:00:00Z");
  for (let i = 0; i < 3660; i++) {
    const iso = date.toISOString().slice(0, 10);
    const exception = config.exceptions.find((r) => r.date === iso);
    const weekday = date.getUTCDay() || 7;
    const working = exception
      ? exception.working
      : !config.holidays.some((r) => r.date === iso) &&
        config.week.find((r) => r.weekday === weekday)?.working;
    if (working) return iso;
    date.setUTCDate(date.getUTCDate() + 1);
  }
  throw new Error("No eligible deadline in the tested calendar window");
}

test("S7 manager project creation, current-owner isolation and administrator oversight", async ({
  page,
  context,
  browser,
}) => {
  try {
    run.boundary = "verified administrator fixture and company calendar";
    await run.login(page);
    await expect(
      page.getByRole("heading", { name: "Administration", exact: true }),
    ).toBeVisible();
    let workspace = await run.graphql(
      context,
      "{companyCalendar{current{id config{timezone week{weekday working opens closes} holidays{date label} exceptions{date label working opens closes}}}}}",
    );
    expect(workspace.errors).toBeUndefined();
    if (!workspace.data.companyCalendar.current) {
      const config = {
        timezone: "Etc/UTC",
        week: Array.from({ length: 7 }, (_, i) => ({
          weekday: i + 1,
          working: i < 5,
          opens: i < 5 ? "09:00" : null,
          closes: i < 5 ? "17:00" : null,
        })),
        holidays: [
          { date: "2099-12-31", label: `Project calendar ${run.runId}` },
        ],
        exceptions: [],
      };
      const preview = await run.graphql(
        context,
        "mutation($input:CalendarConfigurationInput!){previewCompanyCalendar(input:$input){previewId}}",
        { input: config },
      );
      expect(preview.errors).toBeUndefined();
      const published = await run.graphql(
        context,
        "mutation($input:PublishCalendarInput!){publishCompanyCalendar(input:$input){id}}",
        {
          input: {
            requestId: requestId(),
            previewId: preview.data.previewCompanyCalendar.previewId,
            confirm: true,
          },
        },
      );
      expect(published.errors).toBeUndefined();
      workspace = await run.graphql(
        context,
        "{companyCalendar{current{id config{timezone week{weekday working} holidays{date} exceptions{date working}}}}}",
      );
    }
    const deadline = workingDate(workspace.data.companyCalendar.current.config);
    run.boundary = "manager entry and confirmed project creation";
    run.people("role", "MANAGER");
    await page.goto("/auth/ready");
    await expect(page).toHaveURL(new URL("/manager", appOrigin).href);
    await expect(
      page.getByRole("heading", { name: "Manager workspace", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Create project", exact: true })
      .click();
    await page
      .getByLabel("Project name", { exact: true })
      .fill(`Manager ${run.runId}`);
    await page
      .getByLabel("Objectives", { exact: true })
      .fill(
        "Deliver the agreed result.\nKeep ownership and commitments clear.",
      );
    await page
      .getByLabel("Agreed deadline date", { exact: true })
      .fill(deadline);
    await page
      .getByRole("button", { name: "Preview project", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "Review project commitment",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "Create confirmed project",
        exact: true,
      }),
    ).toBeDisabled();
    await page
      .getByLabel("I confirm the objectives and initial agreed deadline")
      .check();
    await page
      .getByRole("button", { name: "Create confirmed project", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: `Manager ${run.runId}`, exact: true }),
    ).toBeVisible();
    const ownId = new URL(page.url()).pathname.split("/").pop()!;
    await expect(
      page.getByText("Original creator", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Current owner", { exact: true }),
    ).toBeVisible();
    run.boundary = "second verified manager creates unrelated project";
    otherContext = await browser.newContext({ baseURL: appOrigin });
    const otherPage = await otherContext.newPage();
    await run.login(otherPage, run.secondary);
    await expect(
      otherPage.getByRole("heading", {
        name: "Manager workspace",
        exact: true,
      }),
    ).toBeVisible();
    const otherPreview = await run.graphql(
      otherContext,
      previewQuery,
      {
        input: {
          name: `Other ${run.runId}`,
          objectives: "Unrelated manager project",
          deadlineDate: deadline,
        },
      },
      run.secondary,
    );
    expect(otherPreview.errors).toBeUndefined();
    const other = await run.graphql(
      otherContext,
      createQuery,
      {
        input: {
          requestId: requestId(),
          previewId: otherPreview.data.previewProject.previewId,
          confirm: true,
        },
      },
      run.secondary,
    );
    expect(other.errors).toBeUndefined();
    const otherProject = other.data.createProject;
    expect(
      otherProject.creatorId === otherProject.ownerId &&
        otherProject.ownerId !== run.runId,
    ).toBe(true);
    run.boundary = "manager cannot list search or read unrelated project";
    const scoped = await run.graphql(
      context,
      "{projectWorkspace{projects{id} hasMore}}",
    );
    expect(scoped.errors).toBeUndefined();
    expect(
      scoped.data.projectWorkspace.projects.map((r: { id: string }) => r.id),
    ).toEqual([ownId]);
    const search = await run.graphql(
      context,
      "query($search:String!){projectWorkspace(search:$search){projects{id}}}",
      { search: `Other ${run.runId}` },
    );
    expect(search.data.projectWorkspace.projects).toEqual([]);
    const denied = await run.graphql(
      context,
      "query($id:ID!){project(id:$id){id name}}",
      { id: otherProject.id },
    );
    expect(denied.errors[0].extensions.reason).toBe("project_not_found");
    await page.goto(`/manager/projects/${otherProject.id}`);
    await expect(
      page.getByRole("heading", {
        name: "This page isn’t available.",
        exact: true,
      }),
    ).toBeVisible();
    await page.goto("/manager/projects");
    await expect(
      page.getByRole("link", { name: `Other ${run.runId}`, exact: true }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    run.boundary = "administrator oversight and own project creation";
    run.people("role", "ADMIN");
    await page.goto("/admin/projects");
    await expect(
      page.getByRole("link", { name: `Other ${run.runId}`, exact: true }),
    ).toBeVisible();
    const adminPreview = await run.graphql(context, previewQuery, {
      input: {
        name: `Admin ${run.runId}`,
        objectives: "Administrator owns this project",
        deadlineDate: deadline,
      },
    });
    expect(adminPreview.errors).toBeUndefined();
    const adminProject = await run.graphql(context, createQuery, {
      input: {
        requestId: requestId(),
        previewId: adminPreview.data.previewProject.previewId,
        confirm: true,
      },
    });
    expect(adminProject.errors).toBeUndefined();
    expect(
      adminProject.data.createProject.creatorId === run.runId &&
        adminProject.data.createProject.ownerId === run.runId,
    ).toBe(true);
    run.boundary = "revoked and non-author roles cannot operate projects";
    for (const role of ["EMPLOYEE", "HR"]) {
      run.people("role", role);
      const forbidden = await run.graphql(
        context,
        "{projectWorkspace{projects{id}}}",
      );
      expect(forbidden.errors[0].extensions.code).toBe("FORBIDDEN");
      const createDenied = await run.graphql(context, createQuery, {
        input: {
          requestId: requestId(),
          previewId: requestId(),
          confirm: true,
        },
      });
      expect(createDenied.errors[0].extensions.code).toBe("FORBIDDEN");
      await page.goto("/manager/projects");
      await expect(page).toHaveURL(new URL("/access-denied", appOrigin).href);
    }
    expect(
      (
        await context.request.post(`${appOrigin}/projects/command`, {
          headers: { Origin: "http://untrusted.invalid" },
          data: { action: "create", input: {} },
        })
      ).status(),
    ).toBe(403);
  } catch (error) {
    run.diagnostic(error, test.info().project.name);
    throw new Error(`S7 boundary failed: ${run.boundary}`);
  } finally {
    run.people("role", "MANAGER");
  }
});
