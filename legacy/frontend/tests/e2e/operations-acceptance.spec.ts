import { expect, test, type Page } from "@playwright/test";

import {
  Cleanup,
  type OwnedIdentity,
  assertNoOneOffContainers,
  assertOwnedRowsRemoved,
  checkedUuid,
  cleanupOwnedIdentity,
  compose,
  deleteJob,
  deleteNotification,
  discoverNotifications,
  discoverOwnedReportByWindow,
  firstSignInDisposable,
  gql,
  protectedAdministrator,
  provisionDisposableManager,
  provisionDisposableMember,
  runMarker,
  signIn,
  sql,
  sqlLiteral,
  verifyPrimaryAdministrator,
} from "./notification-report-acceptance-support";

const env = process.env;
const baseURL = env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3010";
const rootURL = new URL("/", baseURL).toString();
const operationsURL = new URL("/operations", baseURL).toString();
const enabled =
  Boolean(env.DEV_USER_USERNAME) &&
  Boolean(env.DEV_USER_PASSWORD) &&
  Boolean(env.PHASE4_E2E_TEMP_PASSWORD) &&
  Boolean(env.PHASE4_E2E_PASSWORD) &&
  Boolean(env.KEYCLOAK_ADMIN_USERNAME) &&
  Boolean(env.KEYCLOAK_ADMIN_PASSWORD);

async function endCurrentSession(page: Page) {
  const sessionResponse = await page.request.get("/auth/session");
  if (sessionResponse.ok()) {
    const session = (await sessionResponse.json()) as { csrfToken?: string };
    if (session.csrfToken) {
      const logoutResponse = await page.request.post("/auth/logout", {
        headers: { "X-CSRF-Token": session.csrfToken },
      });
      if (logoutResponse.ok()) {
        const result = (await logoutResponse.json()) as { logoutUrl?: string };
        if (result.logoutUrl) {
          await page.goto(result.logoutUrl);
          await expect(page).toHaveURL(/\/signed-out/);
        }
      }
    }
  }
  await page.context().clearCookies();
}

const OPERATIONS_SUMMARY_QUERY = `
  query OperationsSummary {
    operationsSummary {
      overallStatus
      generatedAt
      services {
        serviceName
        status
        version
      }
      jobOperations {
        pendingCount
        runningCount
        completedCount
        failedCount
        recentFailuresCount
      }
      queues {
        queueName
        messagesReady
        messagesUnacknowledged
        consumersCount
      }
    }
  }
`;

test.describe("Phase 13: Observability + Security Hardening Acceptance", () => {
  test.skip(
    !enabled,
    "Set environment credentials for Docker-backed acceptance.",
  );

  test("comprehensive observability, direct GraphQL authorization, end-to-end distributed tracing, and CSP verification", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    const cleanup = new Cleanup();
    const marker = runMarker("P13");
    const projectKey = marker.slice(0, 20);
    const admin = protectedAdministrator();
    const adminPassword = env.DEV_USER_PASSWORD!;

    let memberIdentity: OwnedIdentity | null = null;
    let managerIdentity: OwnedIdentity | null = null;
    let employeeId: string | undefined;
    let projectId: string | undefined;
    let taskId: string | undefined;
    let reportId: string | undefined;
    let reportEventId: string | undefined;
    const jobs: string[] = [];
    const cspViolations: string[] = [];

    page.on("console", (msg) => {
      if (
        msg.type() === "error" &&
        (msg.text().includes("Content Security Policy") ||
          msg
            .text()
            .includes(
              "violates the following Content Security Policy directive",
            ))
      ) {
        cspViolations.push(msg.text());
      }
    });

    try {
      // -------------------------------------------------------------
      // 1. Unauthenticated boundary & direct GraphQL rejection
      // -------------------------------------------------------------
      await page.goto("/operations");
      await expect(page).toHaveURL(/\/session-expired$/);

      const unauthResult = await gql(page, OPERATIONS_SUMMARY_QUERY);
      expect(unauthResult.errors).toBeDefined();

      // Sign in as Admin first to provision disposable test identities
      await signIn(page, admin.username, adminPassword);
      await expect(page).toHaveURL(rootURL);

      // Direct GraphQL query as Admin MUST succeed
      const adminGqlResult = await gql(page, OPERATIONS_SUMMARY_QUERY);
      expect(adminGqlResult.errors).toBeUndefined();
      expect(adminGqlResult.data.operationsSummary.overallStatus).toBe(
        "HEALTHY",
      );
      expect(
        adminGqlResult.data.operationsSummary.services.length,
      ).toBeGreaterThanOrEqual(6);

      // Verify nullable queue inspection on celery
      const queues = adminGqlResult.data.operationsSummary.queues as Array<{
        queueName: string;
        messagesReady: number | null;
        consumersCount: number | null;
      }>;
      const celeryQueue = queues.find((q) => q.queueName === "celery");
      expect(celeryQueue).toBeDefined();
      expect(celeryQueue!.messagesReady).toBeNull();

      memberIdentity = await provisionDisposableMember(
        page,
        marker,
        admin.subject,
      );
      managerIdentity = await provisionDisposableManager(
        page,
        marker,
        admin.subject,
      );
      await endCurrentSession(page);

      // -------------------------------------------------------------
      // 2. Direct GraphQL authorization for MEMBER and MANAGER
      // -------------------------------------------------------------
      // 2a. MEMBER
      await firstSignInDisposable(page, memberIdentity);
      await expect(page).toHaveURL(rootURL);

      // Nav link hidden
      await expect(
        page.getByRole("link", { name: /^Operations$/i }),
      ).not.toBeVisible();

      // Direct page navigation forbidden
      await page.goto("/operations");
      await expect(page).toHaveURL(/\/access-denied$/);

      // Direct GraphQL query forbidden
      const memberGqlResult = await gql(page, OPERATIONS_SUMMARY_QUERY);
      expect(memberGqlResult.errors).toBeDefined();
      expect(memberGqlResult.errors![0].message).toContain(
        "Administrator access is required.",
      );

      await endCurrentSession(page);

      // 2b. MANAGER
      await firstSignInDisposable(page, managerIdentity);
      await expect(page).toHaveURL(rootURL);

      // Nav link hidden
      await expect(
        page.getByRole("link", { name: /^Operations$/i }),
      ).not.toBeVisible();

      // Direct page navigation forbidden
      await page.goto("/operations");
      await expect(page).toHaveURL(/\/access-denied$/);

      // Direct GraphQL query forbidden
      const managerGqlResult = await gql(page, OPERATIONS_SUMMARY_QUERY);
      expect(managerGqlResult.errors).toBeDefined();
      expect(managerGqlResult.errors![0].message).toContain(
        "Administrator access is required.",
      );

      await endCurrentSession(page);

      // -------------------------------------------------------------
      // 3. Admin operational dashboard UI & data truthfulness
      // -------------------------------------------------------------
      await signIn(page, admin.username, adminPassword);
      await expect(page).toHaveURL(rootURL);

      const navOperationsLink = page.getByRole("link", {
        name: /^Operations$/i,
      });
      await expect(navOperationsLink).toBeVisible();
      await navOperationsLink.click();
      await expect(page).toHaveURL(operationsURL);

      // Verify header, operational status badge, and freshness indicator
      await expect(
        page.getByRole("heading", { name: "Operations & Telemetry" }),
      ).toBeVisible();
      await expect(
        page.getByText(/Updated \d{1,2}:\d{2}:\d{2}/i),
      ).toBeVisible();

      // Verify Service Health Matrix
      await expect(page.getByText("Gateway", { exact: true })).toBeVisible();
      await expect(
        page.getByText("Work Service", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Job Service", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Employee Service", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Workflow Service", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Notification Service", { exact: true }),
      ).toBeVisible();

      // Verify Job Operations Diagnostics
      await expect(page.getByText("Job Operations Diagnostics")).toBeVisible();
      await expect(page.getByText("Oldest Pending Job Age")).toBeVisible();
      await expect(page.getByText("Recent Failures (Last 24h)")).toBeVisible();

      // Verify Queue Observations Table: distinguish Broker Queue vs Database Outbox
      await expect(
        page.getByText("Queues & Outbox Observations"),
      ).toBeVisible();
      await expect(page.getByText("Type", { exact: true })).toBeVisible();
      await expect(page.getByText("celery", { exact: true })).toBeVisible();
      await expect(
        page.getByText("work.outbox.events", { exact: true }),
      ).toBeVisible();
      await expect(page.getByText("Database Outbox")).toBeVisible();
      await expect(page.getByText("Broker Queue").first()).toBeVisible();
      // celery passive declaration fails -> shows Unavailable rather than false zero
      await expect(page.getByText("Unavailable").first()).toBeVisible();

      // Verify Local Telemetry Tool Links & Security Attributes
      const grafanaLink = page.getByRole("link", {
        name: /Grafana Dashboards/i,
      });
      await expect(grafanaLink).toBeVisible();
      await expect(grafanaLink).toHaveAttribute(
        "href",
        "http://127.0.0.1:3001",
      );
      await expect(grafanaLink).toHaveAttribute("target", "_blank");
      await expect(grafanaLink).toHaveAttribute("rel", "noopener noreferrer");

      const jaegerLink = page.getByRole("link", { name: /Jaeger Tracing/i });
      await expect(jaegerLink).toBeVisible();
      await expect(jaegerLink).toHaveAttribute(
        "href",
        "http://127.0.0.1:16686",
      );
      await expect(jaegerLink).toHaveAttribute("target", "_blank");
      await expect(jaegerLink).toHaveAttribute("rel", "noopener noreferrer");

      const prometheusLink = page.getByRole("link", {
        name: /Prometheus Metrics/i,
      });
      await expect(prometheusLink).toBeVisible();
      await expect(prometheusLink).toHaveAttribute(
        "href",
        "http://127.0.0.1:9090",
      );
      await expect(prometheusLink).toHaveAttribute("target", "_blank");
      await expect(prometheusLink).toHaveAttribute(
        "rel",
        "noopener noreferrer",
      );

      // Refresh action
      const refreshButton = page.getByRole("button", { name: /^Refresh$/i });
      await expect(refreshButton).toBeVisible();
      await refreshButton.click();
      await expect(
        page.getByRole("heading", { name: "Operations & Telemetry" }),
      ).toBeVisible();

      // Multi-viewport layout without overflow
      for (const vp of [
        { name: "desktop", width: 1280, height: 800 },
        { name: "tablet", width: 768, height: 1024 },
        { name: "mobile", width: 390, height: 844 },
      ]) {
        await page.setViewportSize({ width: vp.width, height: vp.height });
        await page.waitForTimeout(100);
        const overflow = await page.evaluate(() => {
          return (
            document.documentElement.scrollWidth >
            document.documentElement.clientWidth
          );
        });
        expect(
          overflow,
          `Horizontal overflow detected on ${vp.name} viewport`,
        ).toBe(false);
      }
      await page.setViewportSize({ width: 1280, height: 800 });

      // Keyboard focus
      await expect(refreshButton).toBeEnabled();
      await refreshButton.focus();
      await expect(refreshButton).toBeFocused();

      // -------------------------------------------------------------
      // 4. Real Asynchronous Trace Journey & CSP Regression
      // -------------------------------------------------------------
      // Session refresh check
      const sessionRefresh = await page.request.get("/auth/session");
      expect(sessionRefresh.ok()).toBe(true);

      // Create project & task to report on
      const me = await gql(page, "query { me { id } }");
      employeeId = checkedUuid(me.data.me.id, "current Employee ID");

      const projectRes = await gql(
        page,
        "mutation($input: CreateProjectInput!) { createProject(input: $input) { id } }",
        { input: { key: projectKey, name: `Report ${marker}` } },
      );
      expect(projectRes.errors).toBeUndefined();
      projectId = checkedUuid(projectRes.data.createProject.id, "project ID");

      const taskRes = await gql(
        page,
        "mutation($projectId: ID!, $input: CreateTaskInput!) { createTask(projectId: $projectId, input: $input) { id } }",
        { projectId, input: { title: `Task ${marker}`, priority: "MEDIUM" } },
      );
      expect(taskRes.errors).toBeUndefined();
      taskId = checkedUuid(taskRes.data.createTask.id, "task ID");

      // Navigate to /reports and request project task export
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
      jobs.push(reportId);

      // Await publication outbox settlement
      const reportIdentifier = `${sqlLiteral(checkedUuid(reportId, "report Job ID"))}::uuid`;
      await expect
        .poll(
          () =>
            sql(
              "job-db",
              "job",
              "job",
              `select status::text from job_publication_outbox where job_id=${reportIdentifier} and event_type='EXECUTE_JOB' and execution_generation=1;`,
            ),
          { timeout: 30_000, message: "PUBLICATION_DID_NOT_SETTLE" },
        )
        .toBe("PUBLISHED");

      // Await Celery worker execution attempt
      await expect
        .poll(
          () =>
            sql(
              "job-db",
              "job",
              "job",
              `select count(*) from job_attempts where job_id=${reportIdentifier};`,
            ),
          { timeout: 60_000, message: "WORKER_DELIVERY_FAILURE" },
        )
        .toBe("1");

      // Await Job completion
      await expect
        .poll(
          () =>
            sql(
              "job-db",
              "job",
              "job",
              `select status::text from jobs where id=${reportIdentifier};`,
            ),
          { timeout: 60_000, message: "JOB_EXECUTION_FAILURE" },
        )
        .toBe("SUCCEEDED");

      // Await terminal domain event outbox publication
      await expect
        .poll(
          () =>
            sql(
              "job-db",
              "job",
              "job",
              `select status::text from job_domain_outbox where job_id=${reportIdentifier} and event_type='REPORT_SUCCEEDED';`,
            ),
          { timeout: 30_000, message: "DOMAIN_EVENT_DID_NOT_SETTLE" },
        )
        .toBe("PUBLISHED");

      const eventRow = sql(
        "job-db",
        "job",
        "job",
        `select id::text from job_domain_outbox where job_id=${reportIdentifier} and event_type='REPORT_SUCCEEDED';`,
      );
      reportEventId = checkedUuid(eventRow.trim(), "terminal domain event ID");

      // Await Notification materialization
      await expect
        .poll(
          () =>
            sql(
              "notification-db",
              "notification",
              "notification",
              `select count(*) from notifications where report_id=${reportIdentifier} and recipient_employee_id=${sqlLiteral(employeeId!)}::uuid;`,
            ),
          { timeout: 30_000, message: "NOTIFICATION_NOT_RECEIVED" },
        )
        .toBe("1");

      // Navigate to /reports/[id] page and verify UI
      await page.goto(`/reports/${reportId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByText("SUCCEEDED", { exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByText("Checksum")).toBeVisible();
      await expect(page.getByText("Rows")).toBeVisible();

      // Test CSV Download and verify no CSP console violations occur
      const downloadButton = page.getByRole("button", {
        name: /Download CSV/i,
      });
      await expect(downloadButton).toBeVisible();

      const downloadPromise = page.waitForEvent("download");
      await downloadButton.click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.csv$/);

      // Verify Job trace metadata in PostgreSQL
      const traceMeta = sql(
        "job-db",
        "job",
        "job",
        `select traceparent || '|' || coalesce(correlation_id, '') from jobs where id=${reportIdentifier};`,
      ).trim();
      expect(traceMeta).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01\|.+$/);
      const [persistedTraceparent] = traceMeta.split("|");
      const traceId = persistedTraceparent.split("-")[1];
      expect(traceId).toHaveLength(32);

      // Query Jaeger API for the exact distributed trace
      const jaegerPort = process.env.JAEGER_UI_PORT ?? "16686";
      await expect
        .poll(
          async () => {
            const resp = await page.request.get(
              `http://127.0.0.1:${jaegerPort}/api/traces/${traceId}`,
            );
            if (!resp.ok()) return 0;
            const body = (await resp.json()) as {
              data: Array<{
                traceID: string;
                spans: Array<{
                  operationName: string;
                  spanID: string;
                  references: Array<{ refType: string; spanID: string }>;
                }>;
              }>;
            };
            return body.data?.[0]?.spans?.length ?? 0;
          },
          { timeout: 15_000, message: "JAEGER_TRACE_NOT_FOUND" },
        )
        .toBeGreaterThanOrEqual(5);

      const jaegerResp = await page.request.get(
        `http://127.0.0.1:${jaegerPort}/api/traces/${traceId}`,
      );
      expect(jaegerResp.ok()).toBe(true);
      const jaegerData = (await jaegerResp.json()) as {
        data: Array<{
          traceID: string;
          spans: Array<{
            operationName: string;
            spanID: string;
            processID: string;
            references: Array<{ refType: string; spanID: string }>;
          }>;
          processes: Record<string, { serviceName: string }>;
        }>;
      };

      const trace = jaegerData.data[0];
      expect(trace.traceID).toBe(traceId);

      const spanMap = new Map<
        string,
        {
          operationName: string;
          service: string;
          spanID: string;
          parentSpanId?: string;
        }
      >();
      for (const s of trace.spans) {
        const service = trace.processes[s.processID]?.serviceName ?? "unknown";
        const parentRef = s.references.find((r) => r.refType === "CHILD_OF");
        spanMap.set(s.spanID, {
          operationName: s.operationName,
          service,
          spanID: s.spanID,
          parentSpanId: parentRef?.spanID,
        });
      }

      const operationNames = trace.spans.map((s) => s.operationName);
      expect(operationNames).toContain("publish_job_task");
      expect(operationNames).toContain("job_execution");
      expect(operationNames).toContain("publish_job_domain_event");
      expect(operationNames).toContain("notification_consume_event");

      // Verify parentage hierarchy across boundaries:
      const jobExecutionSpan = trace.spans.find(
        (s) => s.operationName === "job_execution",
      );
      expect(jobExecutionSpan).toBeDefined();
      const publishTaskSpan = trace.spans.find(
        (s) => s.operationName === "publish_job_task",
      );
      expect(publishTaskSpan).toBeDefined();
      const publishDomainSpan = trace.spans.find(
        (s) => s.operationName === "publish_job_domain_event",
      );
      expect(publishDomainSpan).toBeDefined();
      const consumeSpan = trace.spans.find(
        (s) => s.operationName === "notification_consume_event",
      );
      expect(consumeSpan).toBeDefined();

      // job_execution child of publish_job_task
      expect(
        jobExecutionSpan!.references.some(
          (r) =>
            r.refType === "CHILD_OF" && r.spanID === publishTaskSpan!.spanID,
        ),
      ).toBe(true);

      // publish_job_domain_event child of job_execution
      expect(
        publishDomainSpan!.references.some(
          (r) =>
            r.refType === "CHILD_OF" && r.spanID === jobExecutionSpan!.spanID,
        ),
      ).toBe(true);

      // notification_consume_event child of publish_job_domain_event
      expect(
        consumeSpan!.references.some(
          (r) =>
            r.refType === "CHILD_OF" && r.spanID === publishDomainSpan!.spanID,
        ),
      ).toBe(true);

      // -------------------------------------------------------------
      // 5. Final Logout & CSP Assertion
      // -------------------------------------------------------------
      await endCurrentSession(page);

      // Confirm zero CSP violations across all phases
      expect(
        cspViolations,
        `Unexpected CSP violations observed: ${cspViolations.join(", ")}`,
      ).toHaveLength(0);
    } finally {
      // Clean up notifications
      const notifications = employeeId
        ? discoverNotifications({
            recipientEmployeeId: employeeId,
            projectId,
            reportId,
          })
        : [];
      for (const n of notifications) {
        deleteNotification(n);
      }

      // Clean up jobs
      for (const j of jobs) {
        deleteJob(j);
      }

      // Clean up Work project and tasks
      if (projectId) {
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
      }

      // Clean up disposable users
      if (memberIdentity) {
        await cleanupOwnedIdentity(cleanup, memberIdentity, admin.subject);
      }
      if (managerIdentity) {
        await cleanupOwnedIdentity(cleanup, managerIdentity, admin.subject);
      }

      // Verify exact row removals
      if (projectId) {
        assertOwnedRowsRemoved({
          projectKey,
          projectId,
          taskIds: taskId ? [taskId] : [],
          jobIds: jobs,
          notificationIds: notifications.map((n) => n.notificationId),
          sourceEventIds: [
            ...new Set([
              ...notifications.map((n) => n.sourceEventId),
              ...(reportEventId ? [reportEventId] : []),
            ]),
          ],
          jobDomainEventIds: reportEventId ? [reportEventId] : [],
        });
      }

      cleanup.finish();
      verifyPrimaryAdministrator(admin.username, admin.subject);
      assertNoOneOffContainers(marker);
    }
  });
});
