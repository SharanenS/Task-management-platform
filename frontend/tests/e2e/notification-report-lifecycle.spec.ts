import { expect, test } from "@playwright/test";

import {
  Cleanup,
  assertOwnedRowsRemoved,
  checkedUuid,
  compose,
  deleteJob,
  deleteNotification,
  discoverNotifications,
  discoverOwnedReportByWindow,
  gql,
  protectedAdministrator,
  runMarker,
  signIn,
  sql,
  sqlLiteral,
} from "./notification-report-acceptance-support";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled =
  process.env.RUN_NOTIFICATION_REPORT_E2E === "1" &&
  username &&
  password &&
  process.env.KEYCLOAK_ADMIN_USERNAME &&
  process.env.KEYCLOAK_ADMIN_PASSWORD;

const JOB_DATABASE = ["job-db", "job", "job"] as const;

function jobValue(query: string) {
  return sql(...JOB_DATABASE, query);
}

async function diagnoseReportPipeline(reportId: string) {
  const identifier = `${sqlLiteral(checkedUuid(reportId, "report Job ID"))}::uuid`;
  const job = jobValue(
    `select status::text || '|' || execution_generation::text from jobs where id=${identifier};`,
  );
  expect(job, "MISSING_PUBLICATION_INTENT").toMatch(
    /^(QUEUED|RUNNING|SUCCEEDED)\|1$/,
  );

  const publication = jobValue(
    `select event_type || '|' || execution_generation::text || '|' || status::text || '|' || case when available_at <= now() then 'ELIGIBLE' else 'FUTURE' end from job_publication_outbox where job_id=${identifier};`,
  );
  expect(publication.split("\n"), "MISSING_PUBLICATION_INTENT").toHaveLength(1);
  expect(publication, "INELIGIBLE_PUBLICATION_ROW").toMatch(
    /^EXECUTE_JOB\|1\|(PENDING|IN_FLIGHT|PUBLISHED)\|ELIGIBLE$/,
  );

  try {
    await expect
      .poll(
        () =>
          jobValue(
            `select status::text from job_publication_outbox where job_id=${identifier} and event_type='EXECUTE_JOB' and execution_generation=1;`,
          ),
        { timeout: 30_000, message: "PUBLICATION_DID_NOT_SETTLE" },
      )
      .toBe("PUBLISHED");
  } catch {
    const state = jobValue(
      `select status::text || '|' || attempt_count::text from job_publication_outbox where job_id=${identifier} and event_type='EXECUTE_JOB' and execution_generation=1;`,
    );
    if (state === "PENDING|0") throw new Error("PUBLISHER_CLAIM_FAILURE");
    throw new Error("BROKER_PUBLICATION_FAILURE");
  }
  await expect
    .poll(
      () =>
        jobValue(
          `select count(*) from job_attempts where job_id=${identifier};`,
        ),
      { timeout: 60_000, message: "WORKER_DELIVERY_FAILURE" },
    )
    .toBe("1");
  await expect
    .poll(
      () => jobValue(`select status::text from jobs where id=${identifier};`),
      { timeout: 90_000, message: "EXECUTION_FAILURE" },
    )
    .toBe("SUCCEEDED");
}

async function pollFixed(
  read: () => string,
  expected: string,
  timeout: number,
  label: string,
) {
  try {
    await expect.poll(read, { timeout, message: label }).toBe(expected);
  } catch {
    throw new Error(label);
  }
}

async function diagnoseNotificationPipeline(
  options: {
    reportId: string;
    recipientEmployeeId: string;
    projectId: string;
  },
  captureEventId: (eventId: string) => void,
) {
  const reportId = checkedUuid(options.reportId, "report Job ID");
  const recipient = checkedUuid(
    options.recipientEmployeeId,
    "report notification recipient ID",
  );
  const projectId = checkedUuid(
    options.projectId,
    "report notification project ID",
  );
  const report = `${sqlLiteral(reportId)}::uuid`;
  const recipientValue = `${sqlLiteral(recipient)}::uuid`;
  const project = `${sqlLiteral(projectId)}::uuid`;
  const raw = jobValue(
    `select id::text || '|' || event_type || '|' || schema_version::text || '|' || recipient_employee_id::text || '|' || project_id::text || '|' || status::text || '|' || case when available_at <= now() then 'ELIGIBLE' else 'FUTURE' end from job_domain_outbox where job_id=${report};`,
  );
  const rows = raw ? raw.split(/\r?\n/) : [];
  expect(rows, "MISSING_REPORT_EVENT_INTENT").toHaveLength(1);
  const [
    eventId,
    eventType,
    schemaVersion,
    eventRecipient,
    eventProject,
    status,
    eligibility,
  ] = rows[0].split("|");
  const validatedEventId = checkedUuid(eventId, "report domain event ID");
  captureEventId(validatedEventId);
  expect(
    [
      eventType,
      schemaVersion,
      checkedUuid(eventRecipient, "report event recipient ID"),
      checkedUuid(eventProject, "report event project ID"),
      eligibility,
    ],
    "INELIGIBLE_REPORT_EVENT",
  ).toEqual(["REPORT_SUCCEEDED", "1", recipient, projectId, "ELIGIBLE"]);
  expect(status, "INELIGIBLE_REPORT_EVENT").toMatch(
    /^(PENDING|IN_FLIGHT|PUBLISHED|FAILED)$/,
  );
  const event = `${sqlLiteral(validatedEventId)}::uuid`;
  try {
    await expect
      .poll(
        () =>
          jobValue(
            `select status::text from job_domain_outbox where id=${event} and job_id=${report};`,
          ),
        { timeout: 30_000, message: "REPORT_EVENT_DID_NOT_SETTLE" },
      )
      .toBe("PUBLISHED");
  } catch {
    const state = jobValue(
      `select status::text || '|' || attempt_count::text from job_domain_outbox where id=${event} and job_id=${report};`,
    );
    if (state === "PENDING|0")
      throw new Error("REPORT_EVENT_PUBLISHER_CLAIM_FAILURE");
    throw new Error("REPORT_EVENT_BROKER_PUBLICATION_FAILURE");
  }
  const notificationEvent = `${sqlLiteral(validatedEventId)}::uuid`;
  await pollFixed(
    () =>
      sql(
        "notification-db",
        "notification",
        "notification",
        `select count(*) from notification_source_events where id=${notificationEvent};`,
      ),
    "1",
    30_000,
    "NOTIFICATION_CONSUMER_FAILURE",
  );
  await pollFixed(
    () =>
      sql(
        "notification-db",
        "notification",
        "notification",
        `select status::text from notification_source_events where id=${notificationEvent};`,
      ),
    "PROCESSED",
    30_000,
    "NOTIFICATION_MATERIALIZATION_FAILURE",
  );
  await pollFixed(
    () =>
      sql(
        "notification-db",
        "notification",
        "notification",
        `select count(*) from notifications where source_event_id=${notificationEvent} and recipient_employee_id=${recipientValue} and report_id=${report} and project_id=${project} and notification_type='REPORT_SUCCEEDED';`,
      ),
    "1",
    30_000,
    "NOTIFICATION_MATERIALIZATION_FAILURE",
  );
}

test.describe("Phase 11 responsive notification and report lifecycle", () => {
  test.skip(
    !enabled,
    "Set RUN_NOTIFICATION_REPORT_E2E=1 and development credentials.",
  );
  test.describe.configure({ mode: "serial" });

  test("report completion creates one private persistent notification", async ({
    page,
  }) => {
    test.setTimeout(420_000);
    const marker = runMarker();
    const projectKey = marker.slice(0, 20);
    let projectId: string | undefined;
    let employeeId: string | undefined;
    let reportId: string | undefined;
    let reportEventId: string | undefined;
    let taskId: string | undefined;
    const primary = protectedAdministrator();
    try {
      await signIn(page, username!, password!);
      await expect(page).toHaveURL("http://localhost:3010/");
      const me = await gql(page, "query{me{id}}");
      employeeId = checkedUuid(me.data.me.id, "current Employee ID");
      const created = await gql(
        page,
        "mutation($input:CreateProjectInput!){createProject(input:$input){id}}",
        { input: { key: projectKey, name: `Report ${marker}` } },
      );
      expect(created.errors).toBeUndefined();
      projectId = checkedUuid(created.data.createProject.id, "project ID");
      const task = await gql(
        page,
        "mutation($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id}}",
        {
          projectId,
          input: { title: `Owned task ${marker}`, priority: "MEDIUM" },
        },
      );
      expect(task.errors).toBeUndefined();
      taskId = checkedUuid(task.data.createTask.id, "task ID");

      await page.goto("/reports");
      await page.getByLabel("Report project").selectOption(projectId);
      const createdAfter = new Date(Date.now() - 5_000).toISOString();
      await page.getByRole("button", { name: "Request report" }).click();
      await expect(
        page.getByText(/SUBMITTED|QUEUED|RUNNING/).first(),
      ).toBeVisible();
      const createdBefore = new Date(Date.now() + 5_000).toISOString();
      reportId = discoverOwnedReportByWindow({
        projectId,
        submitterEmployeeId: employeeId,
        createdAfter,
        createdBefore,
      });
      await diagnoseReportPipeline(reportId);

      await page.goto(`/reports/${reportId}`, {
        waitUntil: "domcontentloaded",
      });

      await expect(
        page.getByText("SUCCEEDED", { exact: true }),
        "UI_FRESHNESS_FAILURE",
      ).toBeVisible({ timeout: 30_000 });

      expect(
        await page.getByText("SUCCEEDED", { exact: true }).count(),
        "UI_FRESHNESS_FAILURE",
      ).toBe(1);
      await expect(page.getByText("Checksum")).toBeVisible();
      await expect(page.getByText("Rows")).toBeVisible();
      const artifact = await gql(
        page,
        "query($id:ID!){reportArtifact(id:$id){filename contentType checksum rowCount content}}",
        { id: reportId },
      );
      expect(artifact.errors).toBeUndefined();
      expect(artifact.data.reportArtifact.filename).toMatch(/\.csv$/);
      expect(artifact.data.reportArtifact.contentType).toBe(
        "text/csv; charset=utf-8",
      );
      expect(artifact.data.reportArtifact.checksum).toBeTruthy();
      expect(artifact.data.reportArtifact.rowCount).toBe(1);
      expect(artifact.data.reportArtifact.content).toContain(
        `Owned task ${marker}`,
      );
      expect(artifact.data.reportArtifact.content).not.toMatch(
        /\/app\/|[A-Z]:\\/i,
      );
      const download = page.waitForEvent("download");
      await page.getByRole("button", { name: "Download CSV" }).click();
      expect((await download).suggestedFilename()).toBe(
        artifact.data.reportArtifact.filename,
      );
      await diagnoseNotificationPipeline(
        {
          reportId,
          recipientEmployeeId: employeeId,
          projectId,
        },
        (eventId) => {
          reportEventId = eventId;
        },
      );

      expect(
        discoverNotifications({
          recipientEmployeeId: employeeId,
          reportId,
        }).length,
        "NOTIFICATION_DISCOVERY_FAILURE",
      ).toBe(1);
      await page.goto("/notifications");
      await expect(page.getByText("1 unread", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Mark read" }).click();
      await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
      const overflow = await page.evaluate(() => {
        const clientWidth = document.documentElement.clientWidth;
        const scrollWidth = document.documentElement.scrollWidth;
        const safeAttribute = (value: string | null) =>
          value && /^[a-zA-Z0-9_-]{1,80}$/.test(value) ? value : null;
        const candidates = Array.from(
          document.querySelectorAll<HTMLElement>("body *"),
        )
          .map((element) => ({
            element,
            rectangle: element.getBoundingClientRect(),
          }))
          .filter(
            ({ rectangle }) =>
              rectangle.width > 0 &&
              (rectangle.left < -1 || rectangle.right > clientWidth + 1),
          )
          .slice(0, 8)
          .map(({ element, rectangle }) => ({
            tag: element.tagName.toLowerCase(),
            role: safeAttribute(element.getAttribute("role")),
            testId: safeAttribute(element.getAttribute("data-testid")),
            classes: Array.from(element.classList)
              .filter((value) => /^[a-zA-Z0-9_:[\]./-]{1,80}$/.test(value))
              .slice(0, 8),
            left: Math.round(rectangle.left),
            right: Math.round(rectangle.right),
            width: Math.round(rectangle.width),
          }));
        return {
          fits: scrollWidth <= clientWidth + 1,
          clientWidth,
          scrollWidth,
          candidates,
        };
      });
      expect(
        overflow.fits,
        `MOBILE_HORIZONTAL_OVERFLOW ${JSON.stringify(overflow)}`,
      ).toBe(true);
      expect(
        await page.evaluate(() =>
          Object.keys(localStorage).concat(Object.keys(sessionStorage)),
        ),
      ).toEqual([]);
    } finally {
      const cleanup = new Cleanup();
      const notifications: ReturnType<typeof discoverNotifications> = [];
      const jobs = new Set<string>();
      if (reportId) jobs.add(reportId);
      await cleanup.stage("discover exact notifications", () => {
        if (employeeId)
          notifications.push(
            ...discoverNotifications({
              recipientEmployeeId: employeeId,
              projectId,
              reportId,
            }),
          );
      });
      await cleanup.stage("discover exact report jobs", () => {
        if (!projectId || !employeeId || !reportId) return;
        const count = sql(
          "job-db",
          "job",
          "job",
          `select count(*) from jobs where id=${sqlLiteral(reportId)}::uuid and related_project_id=${sqlLiteral(projectId)}::uuid and submitter_employee_id=${sqlLiteral(employeeId)}::uuid and job_type='PROJECT_TASK_EXPORT';`,
        );
        if (count !== "1") throw new Error("Known report ownership changed.");
      });
      await cleanup.stage("delete exact report jobs", () =>
        jobs.forEach(deleteJob),
      );
      await cleanup.stage("delete exact notifications", () =>
        notifications.forEach(deleteNotification),
      );
      await cleanup.stage("delete exact Work project", () => {
        if (!projectId) return;
        compose([
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
      });
      await cleanup.stage("verify exact cleanup", () =>
        assertOwnedRowsRemoved({
          projectKey,
          projectId,
          taskIds: taskId ? [taskId] : [],
          jobIds: [...jobs],
          notificationIds: notifications.map((item) => item.notificationId),
          sourceEventIds: [
            ...new Set([
              ...notifications.map((item) => item.sourceEventId),
              ...(reportEventId ? [reportEventId] : []),
            ]),
          ],
          jobDomainEventIds: reportEventId ? [reportEventId] : [],
        }),
      );
      await cleanup.stage("verify protected administrator", () => {
        if (protectedAdministrator().subject !== primary.subject)
          throw new Error("Protected administrator subject changed.");
      });
      cleanup.finish();
    }
  });
});
