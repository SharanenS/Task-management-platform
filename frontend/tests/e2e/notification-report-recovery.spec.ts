import { expect, test } from "@playwright/test";

import {
  BROKER_DEPENDENTS,
  Cleanup,
  type OwnedIdentity,
  assertOwnedRowsRemoved,
  checkedUuid,
  cleanupOwnedIdentity,
  compose,
  composeService,
  deleteJob,
  deleteNotification,
  discoverNotifications,
  discoverReportJobs,
  firstSignInDisposable,
  gql,
  protectedAdministrator,
  provisionDisposableMember,
  runMarker,
  signIn,
  sql,
  sqlLiteral,
  waitForHealthy,
} from "./notification-report-acceptance-support";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled =
  process.env.RUN_NOTIFICATION_REPORT_RECOVERY_E2E === "1" &&
  username &&
  password &&
  process.env.PHASE4_E2E_TEMP_PASSWORD &&
  process.env.PHASE4_E2E_PASSWORD &&
  process.env.KEYCLOAK_ADMIN_USERNAME &&
  process.env.KEYCLOAK_ADMIN_PASSWORD;
const cases = [
  "rabbitmq",
  "work-event-publisher",
  "notification-consumer",
  "notification",
  "job-domain-publisher",
  "job-worker",
] as const;

test.describe("Phase 11 serial notification and report recovery", () => {
  test.skip(
    !enabled,
    "Set RUN_NOTIFICATION_REPORT_RECOVERY_E2E=1 and development credentials.",
  );
  test.describe.configure({ mode: "serial" });

  for (const service of cases) {
    test(`${service} outage preserves committed intent and recovers once`, async ({
      page,
    }, info) => {
      test.skip(
        info.project.name !== "desktop",
        "Destructive recovery runs once on desktop.",
      );
      test.setTimeout(240_000);
      const marker = runMarker();
      const projectKey = marker.slice(0, 20);
      const reportKey = crypto.randomUUID();
      let stopped = false;
      let boundary = "ADMIN_SETUP";
      let administratorEmployeeId: string | undefined;
      let recipient: OwnedIdentity | undefined;
      let projectId: string | undefined;
      let taskId: string | undefined;
      let reportId: string | undefined;
      const primary = protectedAdministrator();
      try {
        await signIn(page, username!, password!);
        administratorEmployeeId = checkedUuid(
          (await gql(page, "query{me{id}}")).data.me.id,
          "Employee ID",
        );
        const project = await gql(
          page,
          "mutation($input:CreateProjectInput!){createProject(input:$input){id}}",
          { input: { key: projectKey, name: `Recovery ${marker}` } },
        );
        projectId = checkedUuid(project.data.createProject.id, "project ID");

        if (
          [
            "rabbitmq",
            "work-event-publisher",
            "notification-consumer",
            "notification",
          ].includes(service)
        ) {
          recipient = await provisionDisposableMember(
            page,
            marker,
            primary.subject,
          );
          const membership = await gql(
            page,
            "mutation($projectId:ID!,$employeeId:ID!){addProjectMember(projectId:$projectId,employeeId:$employeeId,role:CONTRIBUTOR){id}}",
            { projectId, employeeId: recipient.employeeId },
          );
          expect(membership.errors).toBeUndefined();
        }

        boundary = "STOP_SERVICE";
        stopped = true;
        composeService("stop", service);
        boundary = "COMMIT_INTENT_DURING_OUTAGE";

        if (
          [
            "rabbitmq",
            "work-event-publisher",
            "notification-consumer",
            "notification",
          ].includes(service)
        ) {
          const task = await gql(
            page,
            "mutation($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id version}}",
            {
              projectId,
              input: {
                title: `Recovery task ${marker}`,
                priority: "MEDIUM",
              },
            },
          );
          taskId = checkedUuid(task.data.createTask.id, "task ID");
          const assigned = await gql(
            page,
            "mutation($projectId:ID!,$taskId:ID!,$employeeId:ID!,$version:Int!){assignTask(projectId:$projectId,taskId:$taskId,assigneeEmployeeId:$employeeId,expectedVersion:$version){id}}",
            {
              projectId,
              taskId,
              employeeId: recipient!.employeeId,
              version: task.data.createTask.version,
            },
          );
          expect(assigned.errors).toBeUndefined();
          expect(
            sql(
              "work-db",
              "work",
              "work",
              `select count(*) from work_outbox_events where task_id=${sqlLiteral(taskId)}::uuid and event_type='TASK_ASSIGNED';`,
            ),
          ).toBe("1");
        }
        if (
          ["rabbitmq", "job-domain-publisher", "job-worker"].includes(service)
        ) {
          const requested = await gql(
            page,
            "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id status}}",
            {
              input: {
                projectId,
                includeCompleted: true,
                idempotencyKey: reportKey,
              },
            },
          );
          expect(requested.errors).toBeUndefined();
          reportId = checkedUuid(
            requested.data.requestProjectTaskReport.id,
            "report ID",
          );
          if (service === "job-worker")
            expect(["SUBMITTED", "QUEUED"]).toContain(
              requested.data.requestProjectTaskReport.status,
            );
        }
        boundary = "OBSERVE_OUTAGE";
        if (service === "notification") {
          const unavailable = await gql(
            page,
            "query{notifications(first:20,unreadOnly:false){nodes{id}}}",
          );
          expect(unavailable.errors).toEqual([
            expect.objectContaining({
              message: "Notifications are temporarily unavailable.",
              extensions: { code: "SERVICE_UNAVAILABLE" },
            }),
          ]);
          await expect
            .poll(
              () =>
                discoverNotifications({
                  recipientEmployeeId: recipient!.employeeId!,
                  taskId,
                }).length,
              { timeout: 60_000 },
            )
            .toBe(1);
        } else if (taskId) {
          expect(
            discoverNotifications({
              recipientEmployeeId: recipient!.employeeId!,
              taskId,
            }),
          ).toHaveLength(0);
        }

        if (service === "job-domain-publisher" && reportId) {
          boundary = "VERIFY_TERMINAL_INTENT_DURING_OUTAGE";
          const ownedReport = `${sqlLiteral(reportId)}::uuid`;
          await expect
            .poll(
              () =>
                sql(
                  "job-db",
                  "job",
                  "job",
                  `select count(*) from job_domain_outbox e join jobs j on j.id=e.job_id where e.job_id=${ownedReport} and e.event_type='REPORT_SUCCEEDED' and e.status='PENDING' and j.status='SUCCEEDED';`,
                ),
              { timeout: 90_000 },
            )
            .toBe("1");
          expect(
            discoverNotifications({
              recipientEmployeeId: administratorEmployeeId!,
              projectId,
              reportId,
            }),
          ).toHaveLength(0);
          console.info("RECOVERY_TERMINAL_INTENT_PENDING job-domain-publisher");
        }

        boundary = "RESTORE_SERVICE";
        composeService("start", service);
        await waitForHealthy(service);
        if (service === "rabbitmq")
          for (const dependent of BROKER_DEPENDENTS)
            await waitForHealthy(dependent);
        stopped = false;
        boundary = "VERIFY_RECOVERED_OUTCOME";
        if (taskId)
          await expect
            .poll(
              () =>
                discoverNotifications({
                  recipientEmployeeId: recipient!.employeeId!,
                  taskId,
                }).length,
              { timeout: 90_000 },
            )
            .toBe(1);
        if (reportId) {
          await expect
            .poll(
              () =>
                sql(
                  "job-db",
                  "job",
                  "job",
                  `select status::text from jobs where id=${sqlLiteral(reportId!)}::uuid;`,
                ),
              { timeout: 90_000 },
            )
            .toBe("SUCCEEDED");
          await expect
            .poll(
              () =>
                discoverNotifications({
                  recipientEmployeeId: administratorEmployeeId!,
                  reportId,
                }).length,
              { timeout: 90_000 },
            )
            .toBe(1);
          expect(
            sql(
              "job-db",
              "job",
              "job",
              `select count(*) from jobs where idempotency_key=${sqlLiteral(reportKey)};`,
            ),
          ).toBe("1");
        }
        if (service === "notification" && recipient) {
          boundary = "VERIFY_RECIPIENT_ACCESS";
          await page.getByRole("button", { name: /ADMIN/ }).click();
          await page.getByRole("menuitem", { name: "Sign out" }).click();
          await expect(page).toHaveURL(/\/signed-out$/);
          await firstSignInDisposable(page, recipient);
          const visible = await gql(
            page,
            "query{notifications(first:20,unreadOnly:false){nodes{id}}}",
          );
          expect(visible.errors).toBeUndefined();
          expect(visible.data.notifications.nodes).toHaveLength(1);
        }
        boundary = "RELOAD_APPLICATION";
        await page.reload();
        console.info(`RECOVERY_OUTCOME_COMPLETE ${service}`);
      } catch {
        console.info(`RECOVERY_FAILED_BEFORE_CLEANUP ${service} ${boundary}`);
        throw new Error(`RECOVERY_BOUNDARY_FAILED ${service} ${boundary}`);
      } finally {
        const cleanup = new Cleanup();
        await cleanup.stage(`restore ${service}`, async () => {
          if (stopped) composeService("start", service);
          await waitForHealthy(service);
        });
        if (service === "rabbitmq")
          for (const dependent of BROKER_DEPENDENTS)
            await cleanup.stage(`restore broker dependent ${dependent}`, () =>
              waitForHealthy(dependent),
            );
        const notifications: ReturnType<typeof discoverNotifications> = [];
        const jobs = new Set<string>();
        await cleanup.stage("discover exact report jobs", () => {
          if (!projectId) return;
          for (const id of discoverReportJobs(reportKey, projectId))
            jobs.add(id);
          if (reportId && !jobs.has(reportId))
            throw new Error("Known report ownership could not be verified.");
        });
        await cleanup.stage("discover exact notifications", () => {
          if (recipient?.employeeId && projectId && taskId)
            notifications.push(
              ...discoverNotifications({
                recipientEmployeeId: recipient.employeeId,
                projectId,
                taskId,
              }),
            );
          if (administratorEmployeeId && projectId)
            for (const id of jobs)
              notifications.push(
                ...discoverNotifications({
                  recipientEmployeeId: administratorEmployeeId,
                  projectId,
                  reportId: id,
                }),
              );
        });
        await cleanup.stage("delete exact report jobs", () =>
          jobs.forEach(deleteJob),
        );
        await cleanup.stage("delete exact notifications", () =>
          notifications.forEach(deleteNotification),
        );
        await cleanup.stage("delete exact Work project", () => {
          if (projectId)
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
        if (recipient)
          await cleanupOwnedIdentity(cleanup, recipient, primary.subject);
        await cleanup.stage("verify exact cleanup", () =>
          assertOwnedRowsRemoved({
            projectKey,
            projectId,
            taskIds: taskId ? [taskId] : [],
            jobIds: [...new Set([...jobs, ...(reportId ? [reportId] : [])])],
            notificationIds: notifications.map((item) => item.notificationId),
            sourceEventIds: notifications.map((item) => item.sourceEventId),
          }),
        );
        await cleanup.stage("verify protected administrator", () => {
          if (protectedAdministrator().subject !== primary.subject)
            throw new Error("Protected administrator subject changed.");
        });
        cleanup.finish();
        console.info(`RECOVERY_CLEANUP_COMPLETE ${service}`);
      }
    });
  }
});
