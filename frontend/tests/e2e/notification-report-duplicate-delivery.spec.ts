import { expect, test } from "@playwright/test";

import {
  Cleanup,
  type OwnedIdentity,
  assertOwnedRowsRemoved,
  checkedUuid,
  cleanupOwnedIdentity,
  compose,
  deleteJob,
  deleteNotification,
  discoverNotifications,
  discoverReportJobs,
  gql,
  protectedAdministrator,
  provisionDisposableMember,
  runMarker,
  signIn,
  sql,
  sqlLiteral,
} from "./notification-report-acceptance-support";

const username = process.env.DEV_USER_USERNAME;
const password = process.env.DEV_USER_PASSWORD;
const enabled =
  process.env.RUN_NOTIFICATION_REPORT_DUPLICATE_E2E === "1" &&
  username &&
  password &&
  process.env.PHASE4_E2E_TEMP_PASSWORD &&
  process.env.PHASE4_E2E_PASSWORD &&
  process.env.KEYCLOAK_ADMIN_USERNAME &&
  process.env.KEYCLOAK_ADMIN_PASSWORD;

function acknowledgedDeliveries(queue: string) {
  const result = compose([
    "exec",
    "-T",
    "notification-consumer",
    "python",
    "-c",
    [
      "import base64, json, os, sys",
      "from urllib.parse import quote, unquote, urlsplit",
      "from urllib.request import Request, urlopen",
      "broker = urlsplit(os.environ['RABBITMQ_URL'])",
      "vhost = quote(unquote(broker.path[1:]), safe='')",
      "credentials = f'{unquote(broker.username)}:{unquote(broker.password)}'",
      "token = base64.b64encode(credentials.encode()).decode()",
      "request = Request(f'http://{broker.hostname}:15672/api/queues/{vhost}/{sys.argv[1]}', headers={'Authorization': f'Basic {token}'})",
      "with urlopen(request, timeout=5) as response:",
      "    print(json.load(response).get('message_stats', {}).get('ack', 0))",
    ].join("\n"),
    queue,
  ]).trim();
  if (!/^\d+$/.test(result)) throw new Error("BROKER_ACK_COUNT_UNAVAILABLE");
  return Number(result);
}

async function replayAndWaitForAcknowledgements(
  exchange: string,
  routingKey: string,
  queue: string,
  payload: string,
) {
  const before = acknowledgedDeliveries(queue);
  const encoded = Buffer.from(payload, "utf8").toString("base64");
  compose([
    "exec",
    "-T",
    "-e",
    `P11_EVENT=${encoded}`,
    "notification-consumer",
    "python",
    "-c",
    [
      "import base64, json, os, sys",
      "from kombu import Connection, Exchange, Producer",
      "payload = json.loads(base64.b64decode(os.environ['P11_EVENT']))",
      "exchange = Exchange(sys.argv[1], type='direct', durable=True)",
      "with Connection(os.environ['RABBITMQ_URL'], transport_options={'confirm_publish': True}) as connection:",
      "    producer = Producer(connection)",
      "    for _ in range(2):",
      "        producer.publish(payload, exchange=exchange, routing_key=sys.argv[2], serializer='json', delivery_mode=2, mandatory=True)",
    ].join("\n"),
    exchange,
    routingKey,
  ]);
  await expect
    .poll(() => acknowledgedDeliveries(queue), {
      message: "DUPLICATE_DELIVERIES_NOT_ACKNOWLEDGED",
    })
    .toBeGreaterThanOrEqual(before + 2);
}

test.describe("Phase 11 duplicate RabbitMQ delivery", () => {
  test.skip(
    !enabled,
    "Set RUN_NOTIFICATION_REPORT_DUPLICATE_E2E=1 and development credentials.",
  );
  test.describe.configure({ mode: "serial" });

  test("duplicate assignment and report events remain logically unique", async ({
    page,
  }, info) => {
    test.skip(
      info.project.name !== "desktop",
      "Duplicate delivery runs once on desktop.",
    );
    test.setTimeout(240_000);
    const marker = runMarker();
    const projectKey = marker.slice(0, 20);
    const reportKey = crypto.randomUUID();
    let administratorEmployeeId: string | undefined;
    let recipient: OwnedIdentity | undefined;
    let projectId: string | undefined;
    let taskId: string | undefined;
    let reportId: string | undefined;
    const primary = protectedAdministrator();
    try {
      await signIn(page, username!, password!);
      const me = await gql(page, "query{me{id}}");
      administratorEmployeeId = checkedUuid(
        me.data.me.id,
        "administrator Employee ID",
      );
      recipient = await provisionDisposableMember(
        page,
        marker,
        primary.subject,
      );
      const project = await gql(
        page,
        "mutation($input:CreateProjectInput!){createProject(input:$input){id}}",
        { input: { key: projectKey, name: `Duplicate ${marker}` } },
      );
      projectId = checkedUuid(project.data.createProject.id, "project ID");
      const membership = await gql(
        page,
        "mutation($projectId:ID!,$employeeId:ID!){addProjectMember(projectId:$projectId,employeeId:$employeeId,role:CONTRIBUTOR){id}}",
        { projectId, employeeId: recipient.employeeId },
      );
      expect(membership.errors).toBeUndefined();
      const task = await gql(
        page,
        "mutation($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id version}}",
        {
          projectId,
          input: {
            title: `Assigned ${marker}`,
            priority: "MEDIUM",
          },
        },
      );
      taskId = checkedUuid(task.data.createTask.id, "task ID");
      const assigned = await gql(
        page,
        "mutation($projectId:ID!,$taskId:ID!,$employeeId:ID!,$version:Int!){assignTask(projectId:$projectId,taskId:$taskId,assigneeEmployeeId:$employeeId,expectedVersion:$version){id version}}",
        {
          projectId,
          taskId,
          employeeId: recipient.employeeId,
          version: task.data.createTask.version,
        },
      );
      expect(assigned.errors).toBeUndefined();
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
      const workPayload = sql(
        "work-db",
        "work",
        "work",
        `select json_build_object('eventId',id,'schemaVersion',schema_version,'eventType',event_type,'recipientEmployeeId',recipient_employee_id,'projectId',project_id,'taskId',task_id,'actorEmployeeId',actor_employee_id,'taskVersion',task_version,'occurredAt',created_at)::text from work_outbox_events where task_id=${sqlLiteral(taskId)}::uuid and event_type='TASK_ASSIGNED';`,
      );
      const assignmentEventId = checkedUuid(
        JSON.parse(workPayload).eventId,
        "assignment event ID",
      );
      await replayAndWaitForAcknowledgements(
        "work.domain",
        "work.task.assigned.v1",
        "notification.task.assigned",
        workPayload,
      );
      await expect
        .poll(() =>
          sql(
            "notification-db",
            "notification",
            "notification",
            `select count(*) from notification_source_events where id=${sqlLiteral(assignmentEventId)}::uuid;`,
          ),
        )
        .toBe("1");
      expect(
        discoverNotifications({
          recipientEmployeeId: recipient.employeeId!,
          taskId,
        }),
      ).toHaveLength(1);

      const requested = await gql(
        page,
        "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id}}",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: reportKey,
          },
        },
      );
      reportId = checkedUuid(
        requested.data.requestProjectTaskReport.id,
        "report ID",
      );
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
          { timeout: 60_000 },
        )
        .toBe(1);
      const reportPayload = sql(
        "job-db",
        "job",
        "job",
        `select json_build_object('eventId',id,'schemaVersion',schema_version,'eventType',event_type,'reportId',job_id,'reportType','PROJECT_TASK_EXPORT','recipientEmployeeId',recipient_employee_id,'projectId',project_id,'occurredAt',created_at)::text from job_domain_outbox where job_id=${sqlLiteral(reportId)}::uuid;`,
      );
      const reportEventId = checkedUuid(
        JSON.parse(reportPayload).eventId,
        "report event ID",
      );
      await replayAndWaitForAcknowledgements(
        "job.domain",
        "job.report.terminal.v1",
        "notification.report.terminal",
        reportPayload,
      );
      await expect
        .poll(() =>
          sql(
            "notification-db",
            "notification",
            "notification",
            `select count(*) from notification_source_events where id=${sqlLiteral(reportEventId)}::uuid;`,
          ),
        )
        .toBe("1");
      expect(
        discoverNotifications({
          recipientEmployeeId: administratorEmployeeId!,
          reportId,
        }),
      ).toHaveLength(1);
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from jobs where idempotency_key=${sqlLiteral(reportKey)};`,
        ),
      ).toBe("1");
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from job_attempts where job_id=${sqlLiteral(reportId)}::uuid and status='SUCCEEDED';`,
        ),
      ).toBe("1");
      expect(
        sql(
          "job-db",
          "job",
          "job",
          `select count(*) from jobs where id=${sqlLiteral(reportId)}::uuid and result_content is not null and result_checksum is not null and result_content_type='text/csv; charset=utf-8';`,
        ),
      ).toBe("1");
      console.info("DUPLICATE_DELIVERY_COMPLETE");
    } finally {
      const cleanup = new Cleanup();
      const notifications: ReturnType<typeof discoverNotifications> = [];
      const jobs = new Set<string>();
      await cleanup.stage("discover exact report jobs", () => {
        if (!projectId) return;
        for (const id of discoverReportJobs(reportKey, projectId)) jobs.add(id);
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
      console.info("DUPLICATE_CLEANUP_COMPLETE");
    }
  });
});
