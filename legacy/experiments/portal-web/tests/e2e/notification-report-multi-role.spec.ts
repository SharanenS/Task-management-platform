import { expect, test, type Page } from "@playwright/test";

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
  gql,
  protectedAdministrator,
  recordIdentity,
  runMarker,
  signIn,
  sql,
  sqlLiteral,
  verifyPrimaryAdministrator,
} from "./notification-report-acceptance-support";

const env = process.env;
const enabled =
  env.RUN_NOTIFICATION_REPORT_MULTI_ROLE_E2E === "1" &&
  env.DEV_USER_USERNAME &&
  env.DEV_USER_PASSWORD &&
  env.PHASE4_E2E_TEMP_PASSWORD &&
  env.PHASE4_E2E_PASSWORD &&
  env.KEYCLOAK_ADMIN_USERNAME &&
  env.KEYCLOAK_ADMIN_PASSWORD;

async function endCurrentSession(page: Page) {
  const sessionResponse = await page.request.get("/auth/session");
  if (sessionResponse.ok()) {
    const session = (await sessionResponse.json()) as { csrfToken?: string };
    if (!session.csrfToken) throw new Error("SESSION_RESET_CSRF_UNAVAILABLE");
    const logoutResponse = await page.request.post("/auth/logout", {
      headers: { "X-CSRF-Token": session.csrfToken },
    });
    if (!logoutResponse.ok()) throw new Error("SESSION_RESET_FAILED");
    const result = (await logoutResponse.json()) as { logoutUrl?: string };
    if (!result.logoutUrl) throw new Error("SESSION_RESET_URL_UNAVAILABLE");
    await page.goto(result.logoutUrl);
    await expect(page).toHaveURL(/\/signed-out/);
  }
  await page.context().clearCookies();
}

async function logout(page: Page) {
  await endCurrentSession(page);
  await page.goto("/sign-in");
  await expect(page).toHaveURL(/\/sign-in/);
}

async function expectNoBrowserStorage(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(() => [
        ...Object.keys(window.localStorage),
        ...Object.keys(window.sessionStorage),
      ]),
    )
    .toEqual([]);
}

async function firstLogin(page: Page, identity: OwnedIdentity) {
  await signIn(page, identity.username, env.PHASE4_E2E_TEMP_PASSWORD!);
  await page.locator("#password-new").fill(env.PHASE4_E2E_PASSWORD!);
  await page.locator("#password-confirm").fill(env.PHASE4_E2E_PASSWORD!);
  await page.getByRole("button", { name: /submit/i }).click();
  await expect(page).toHaveURL("http://localhost:3010/");
}

async function restoreAdministratorSession(
  page: Page,
  primaryEmployeeId: string,
  primarySubject: string,
) {
  const currentProfile = await gql(page, "query{me{id role}}");
  const currentId = currentProfile.errors
    ? undefined
    : currentProfile.data?.me?.id;
  const currentRole = currentProfile.errors
    ? undefined
    : currentProfile.data?.me?.role;
  if (currentId !== primaryEmployeeId || currentRole !== "ADMIN") {
    await endCurrentSession(page);
    await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
  }
  const restored = await gql(page, "query{me{id role}}");
  if (restored.errors || restored.data?.me?.role !== "ADMIN")
    throw new Error("ADMIN_SESSION_RESTORE_FAILED");
  if (
    checkedUuid(restored.data.me.id, "restored administrator Employee ID") !==
    primaryEmployeeId
  )
    throw new Error("ADMIN_SESSION_PROFILE_MISMATCH");
  const currentAdministrator = protectedAdministrator();
  if (currentAdministrator.subject !== primarySubject)
    throw new Error("ADMIN_SESSION_SUBJECT_MISMATCH");
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

async function diagnoseAssignmentPipeline(
  options: {
    projectId: string;
    taskId: string;
    recipientEmployeeId: string;
    actorEmployeeId: string;
    assignedTaskVersion: number;
  },
  captureEventId: (eventId: string) => void,
) {
  const projectId = checkedUuid(options.projectId, "project ID");
  const taskId = checkedUuid(options.taskId, "task ID");
  const recipient = checkedUuid(
    options.recipientEmployeeId,
    "recipient Employee ID",
  );
  const actor = checkedUuid(options.actorEmployeeId, "actor Employee ID");
  const task = `${sqlLiteral(taskId)}::uuid`;
  const recipientValue = `${sqlLiteral(recipient)}::uuid`;
  const projectValue = `${sqlLiteral(projectId)}::uuid`;

  const raw = sql(
    "work-db",
    "work",
    "work",
    `select id::text || '|' || event_type || '|' || schema_version::text || '|' || project_id::text || '|' || task_id::text || '|' || recipient_employee_id::text || '|' || actor_employee_id::text || '|' || task_version::text || '|' || status::text || '|' || case when available_at <= now() then 'ELIGIBLE' else 'FUTURE' end from work_outbox_events where task_id=${task} and event_type='TASK_ASSIGNED';`,
  );
  const rows = raw ? raw.split(/\r?\n/).filter(Boolean) : [];
  expect(rows, "MISSING_ASSIGNMENT_EVENT_INTENT").toHaveLength(1);

  const [
    eventId,
    eventType,
    schemaVersion,
    eventProject,
    eventTask,
    eventRecipient,
    eventActor,
    eventTaskVersion,
    status,
    eligibility,
  ] = rows[0].split("|");

  const validatedEventId = checkedUuid(eventId, "assignment outbox event ID");
  captureEventId(validatedEventId);

  expect(
    [
      eventType,
      schemaVersion,
      checkedUuid(eventProject, "event project ID"),
      checkedUuid(eventTask, "event task ID"),
      checkedUuid(eventRecipient, "event recipient ID"),
      checkedUuid(eventActor, "event actor ID"),
      eventTaskVersion,
    ],
    "INVALID_ASSIGNMENT_EVENT_OWNERSHIP",
  ).toEqual([
    "TASK_ASSIGNED",
    "1",
    projectId,
    taskId,
    recipient,
    actor,
    String(options.assignedTaskVersion),
  ]);

  expect(eligibility, "INELIGIBLE_ASSIGNMENT_EVENT").toBe("ELIGIBLE");
  expect(status, "INELIGIBLE_ASSIGNMENT_EVENT").toMatch(
    /^(PENDING|IN_FLIGHT|PUBLISHED)$/,
  );

  const event = `${sqlLiteral(validatedEventId)}::uuid`;
  try {
    await expect
      .poll(
        () =>
          sql(
            "work-db",
            "work",
            "work",
            `select status::text from work_outbox_events where id=${event} and task_id=${task};`,
          ),
        { timeout: 30_000, message: "ASSIGNMENT_EVENT_DID_NOT_SETTLE" },
      )
      .toBe("PUBLISHED");
  } catch {
    const state = sql(
      "work-db",
      "work",
      "work",
      `select status::text || '|' || attempt_count::text from work_outbox_events where id=${event} and task_id=${task};`,
    );
    if (state === "PENDING|0")
      throw new Error("ASSIGNMENT_EVENT_PUBLISHER_CLAIM_FAILURE");
    throw new Error("ASSIGNMENT_EVENT_BROKER_PUBLICATION_FAILURE");
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
    "ASSIGNMENT_NOTIFICATION_CONSUMER_FAILURE",
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
    "ASSIGNMENT_NOTIFICATION_MATERIALIZATION_FAILURE",
  );
  await pollFixed(
    () =>
      sql(
        "notification-db",
        "notification",
        "notification",
        `select count(*) from notifications where source_event_id=${notificationEvent} and recipient_employee_id=${recipientValue} and task_id=${task} and project_id=${projectValue} and notification_type='TASK_ASSIGNED';`,
      ),
    "1",
    30_000,
    "ASSIGNMENT_NOTIFICATION_MATERIALIZATION_FAILURE",
  );
}

test.describe("Phase 11 notification and report four-role authorization", () => {
  test.skip(
    !enabled,
    "Set RUN_NOTIFICATION_REPORT_MULTI_ROLE_E2E=1 and disposable identity credentials.",
  );
  test.describe.configure({ mode: "serial" });

  test("ADMIN, manager, member, and non-member boundaries remain private", async ({
    page,
  }, info) => {
    test.skip(
      info.project.name !== "desktop",
      "The destructive four-role journey runs once on desktop.",
    );
    test.setTimeout(480_000);
    const marker = runMarker().toLowerCase();
    const projectKey = marker.slice(0, 20).toUpperCase();
    const identities: OwnedIdentity[] = ["manager", "member", "outsider"].map(
      (role) => ({
        username: `p11-${role}-${marker.slice(-8)}`,
        email: `p11-${role}-${marker.slice(-8)}@example.invalid`,
      }),
    );
    const [manager, member, outsider] = identities;
    let primarySubject: string | undefined;
    let primaryEmployeeId: string | undefined;
    let projectId: string | undefined;
    let taskId: string | undefined;
    let reportId: string | undefined;
    let memberReportId: string | undefined;
    let assignmentEventId: string | undefined;
    try {
      compose([
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "config",
        "credentials",
        "--server",
        "http://localhost:8080",
        "--realm",
        "master",
        "--user",
        env.KEYCLOAK_ADMIN_USERNAME!,
        "--password",
        env.KEYCLOAK_ADMIN_PASSWORD!,
      ]);
      const primaryUsers = JSON.parse(
        compose([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "get",
          "users",
          "-r",
          "taskspace",
          "-q",
          `username=${env.DEV_USER_USERNAME}`,
        ]),
      ) as Array<{ id: string; username: string }>;
      const primary = primaryUsers.filter(
        (user) => user.username === env.DEV_USER_USERNAME,
      );
      if (primary.length !== 1)
        throw new Error("Protected primary administrator is not unique.");
      primarySubject = checkedUuid(
        primary[0].id,
        "primary administrator subject",
      );
      verifyPrimaryAdministrator(env.DEV_USER_USERNAME!, primarySubject);

      await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
      await expectNoBrowserStorage(page);
      const primaryProfile = await gql(page, "query{me{id role}}");
      if (primaryProfile.errors || primaryProfile.data?.me?.role !== "ADMIN")
        throw new Error("ADMIN_SETUP_FAILED");
      primaryEmployeeId = checkedUuid(
        primaryProfile.data.me.id,
        "primary administrator Employee ID",
      );
      for (const identity of identities) {
        const provisioned = await gql(
          page,
          "mutation($input:ProvisionEmployeeInput!){provisionEmployee(input:$input){id}}",
          {
            input: {
              idempotencyKey: crypto.randomUUID(),
              username: identity.username,
              email: identity.email,
              displayName: identity.username,
              role: "MEMBER",
              active: true,
              temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD,
            },
          },
        );
        expect(provisioned.errors).toBeUndefined();
        identity.employeeId = checkedUuid(
          provisioned.data.provisionEmployee.id,
          "provisioned Employee ID",
        );
        recordIdentity(identity, primarySubject);
      }
      console.info("ADMIN_SETUP_COMPLETE");
      const project = await gql(
        page,
        "mutation($input:CreateProjectInput!){createProject(input:$input){id version}}",
        { input: { key: projectKey, name: `Roles ${marker}` } },
      );
      projectId = checkedUuid(project.data.createProject.id, "project ID");
      await gql(
        page,
        "mutation($id:ID!,$employee:ID!){addProjectMember(projectId:$id,employeeId:$employee,role:PROJECT_MANAGER){id}}",
        { id: projectId, employee: manager.employeeId },
      );
      await gql(
        page,
        "mutation($id:ID!,$employee:ID!){addProjectMember(projectId:$id,employeeId:$employee,role:CONTRIBUTOR){id}}",
        { id: projectId, employee: member.employeeId },
      );
      const task = await gql(
        page,
        "mutation($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id version assigneeEmployeeId}}",
        {
          projectId,
          input: {
            title: `Private task ${marker}`,
            priority: "MEDIUM",
          },
        },
      );
      expect(task.errors).toBeUndefined();
      expect(task.data?.createTask).toBeDefined();
      taskId = checkedUuid(task.data.createTask.id, "created task ID");
      const initialVersion = task.data.createTask.version;
      expect(typeof initialVersion).toBe("number");
      expect(task.data.createTask.assigneeEmployeeId).toBeNull();

      const assigned = await gql(
        page,
        "mutation($projectId:ID!,$taskId:ID!,$assigneeEmployeeId:ID,$expectedVersion:Int!){assignTask(projectId:$projectId,taskId:$taskId,assigneeEmployeeId:$assigneeEmployeeId,expectedVersion:$expectedVersion){id version assigneeEmployeeId}}",
        {
          projectId,
          taskId,
          assigneeEmployeeId: member.employeeId,
          expectedVersion: initialVersion,
        },
      );
      expect(assigned.errors).toBeUndefined();
      expect(assigned.data?.assignTask).toBeDefined();
      expect(checkedUuid(assigned.data.assignTask.id, "assigned task ID")).toBe(
        taskId,
      );
      expect(assigned.data.assignTask.assigneeEmployeeId).toBe(
        member.employeeId,
      );
      const assignedVersion = assigned.data.assignTask.version;
      expect(assignedVersion).toBe(initialVersion + 1);

      await diagnoseAssignmentPipeline(
        {
          projectId,
          taskId,
          recipientEmployeeId: member.employeeId!,
          actorEmployeeId: primaryEmployeeId,
          assignedTaskVersion: assignedVersion,
        },
        (eventId) => {
          assignmentEventId = eventId;
        },
      );

      const discoveredNotifications = discoverNotifications({
        recipientEmployeeId: member.employeeId!,
        taskId,
      });
      expect(discoveredNotifications).toHaveLength(1);
      const privateNotification = discoveredNotifications[0];

      await logout(page);
      await firstLogin(page, manager);
      await expectNoBrowserStorage(page);
      const managerReport = await gql(
        page,
        "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id}}",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: crypto.randomUUID(),
          },
        },
      );
      expect(managerReport.errors).toBeUndefined();
      reportId = checkedUuid(
        managerReport.data.requestProjectTaskReport.id,
        "manager report ID",
      );
      expect(
        (
          await gql(page, "query($id:ID!){report(id:$id){id}}", {
            id: reportId,
          })
        ).errors,
      ).toBeUndefined();
      console.info("MANAGER_BOUNDARY_COMPLETE");

      await logout(page);
      await firstLogin(page, member);
      await expectNoBrowserStorage(page);
      const memberForeignReport = await gql(
        page,
        "query($id:ID!){report(id:$id){id}}",
        { id: reportId },
      );
      expect(memberForeignReport.errors?.[0]?.extensions?.code).toBe(
        "JOB_NOT_FOUND",
      );
      expect(memberForeignReport.errors?.[0]?.message).toBe(
        "The job was not found.",
      );
      const memberForeignArtifact = await gql(
        page,
        "query($id:ID!){reportArtifact(id:$id){checksum}}",
        { id: reportId },
      );
      expect(memberForeignArtifact.errors?.[0]?.extensions?.code).toBe(
        "JOB_NOT_FOUND",
      );
      const memberReport = await gql(
        page,
        "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id}}",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: crypto.randomUUID(),
          },
        },
      );
      expect(memberReport.errors).toBeUndefined();
      memberReportId = checkedUuid(
        memberReport.data.requestProjectTaskReport.id,
        "member report ID",
      );
      const memberOwnedReport = await gql(
        page,
        "query($id:ID!){report(id:$id){id}}",
        { id: memberReportId },
      );
      expect(memberOwnedReport.errors).toBeUndefined();
      expect(memberOwnedReport.data?.report?.id).toBe(memberReportId);
      const memberNotifications = await gql(
        page,
        "query{notifications(first:20,unreadOnly:false){nodes{id}}}",
      );
      expect(
        memberNotifications.data.notifications.nodes.map(
          (item: { id: string }) => item.id,
        ),
      ).toContain(privateNotification.notificationId);
      console.info("MEMBER_BOUNDARY_COMPLETE");

      await logout(page);
      await firstLogin(page, outsider);
      await expectNoBrowserStorage(page);
      for (const operation of [
        ["query($id:ID!){report(id:$id){id}}", reportId],
        ["query($id:ID!){reportArtifact(id:$id){checksum}}", reportId],
        ["query($id:ID!){report(id:$id){id}}", memberReportId],
        ["query($id:ID!){reportArtifact(id:$id){checksum}}", memberReportId],
        [
          "mutation($id:ID!){markNotificationRead(id:$id){id}}",
          privateNotification.notificationId,
        ],
      ] as const) {
        const result = await gql(page, operation[0], { id: operation[1] });
        expect(result.errors?.[0]?.extensions?.code).toMatch(
          /FORBIDDEN|NOT_FOUND|JOB_NOT_FOUND/,
        );
      }
      const outsiderReportMutation = await gql(
        page,
        "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id}}",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: crypto.randomUUID(),
          },
        },
      );
      expect(outsiderReportMutation.errors?.[0]?.extensions?.code).toMatch(
        /FORBIDDEN|NOT_FOUND/,
      );
      console.info("NON_MEMBER_BOUNDARY_COMPLETE");

      await logout(page);
      await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
      await expectNoBrowserStorage(page);
      expect(
        (
          await gql(page, "query($id:ID!){report(id:$id){id}}", {
            id: reportId,
          })
        ).errors,
      ).toBeUndefined();
      expect(
        (
          await gql(page, "query($id:ID!){report(id:$id){id}}", {
            id: memberReportId,
          })
        ).errors,
      ).toBeUndefined();
      await gql(
        page,
        "mutation($id:ID!,$employee:ID!){removeProjectMember(projectId:$id,employeeId:$employee){id}}",
        { id: projectId, employee: manager.employeeId },
      );
      await logout(page);
      await signIn(page, manager.username, env.PHASE4_E2E_PASSWORD!);
      await expectNoBrowserStorage(page);
      expect(
        (
          await gql(page, "query($id:ID!){report(id:$id){id}}", {
            id: reportId,
          })
        ).errors,
      ).toBeUndefined();
      const foreignReportForRemovedManager = await gql(
        page,
        "query($id:ID!){report(id:$id){id}}",
        { id: memberReportId },
      );
      expect(
        foreignReportForRemovedManager.errors?.[0]?.extensions?.code,
      ).toMatch(/FORBIDDEN|NOT_FOUND|JOB_NOT_FOUND/);
      const foreignArtifactForRemovedManager = await gql(
        page,
        "query($id:ID!){reportArtifact(id:$id){checksum}}",
        { id: memberReportId },
      );
      expect(
        foreignArtifactForRemovedManager.errors?.[0]?.extensions?.code,
      ).toMatch(/FORBIDDEN|NOT_FOUND|JOB_NOT_FOUND/);
      const removedManagerReportMutation = await gql(
        page,
        "mutation($input:SubmitProjectTaskExportInput!){requestProjectTaskReport(input:$input){id}}",
        {
          input: {
            projectId,
            includeCompleted: true,
            idempotencyKey: crypto.randomUUID(),
          },
        },
      );
      expect(
        removedManagerReportMutation.errors?.[0]?.extensions?.code,
      ).toMatch(/FORBIDDEN|NOT_FOUND/);
      console.info("REMOVED_MANAGER_BOUNDARY_COMPLETE");
      await logout(page);
      await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
      await expectNoBrowserStorage(page);

      const deactivation = await gql(
        page,
        "mutation($id:ID!){setEmployeeActive(employeeId:$id,active:false){id active}}",
        { id: outsider.employeeId },
      );
      expect(deactivation.errors).toBeUndefined();
      expect(deactivation.data?.setEmployeeActive).toEqual({
        id: outsider.employeeId,
        active: false,
      });

      const inactiveEmployeeCount = sql(
        "employee-db",
        "employee",
        "employee",
        `select count(*) from employees where id=${sqlLiteral(outsider.employeeId!)}::uuid and username=${sqlLiteral(outsider.username)} and email=${sqlLiteral(outsider.email)} and keycloak_subject=${sqlLiteral(outsider.subject!)} and active=false;`,
      );
      expect(inactiveEmployeeCount, "DISPOSABLE_EMPLOYEE_NOT_INACTIVE").toBe(
        "1",
      );

      const keycloakUsers = JSON.parse(
        compose([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "get",
          "users",
          "-r",
          "taskspace",
          "-q",
          `username=${outsider.username}`,
        ]),
      ) as Array<{
        id: string;
        username: string;
        email?: string;
        enabled?: boolean;
      }>;
      const exactKeycloakUsers = keycloakUsers.filter(
        (user) => user.username === outsider.username,
      );
      expect(
        exactKeycloakUsers.length === 1 &&
          exactKeycloakUsers[0].id === outsider.subject &&
          exactKeycloakUsers[0].email === outsider.email &&
          exactKeycloakUsers[0].enabled === false,
        "DISPOSABLE_KEYCLOAK_IDENTITY_NOT_DISABLED",
      ).toBe(true);

      await logout(page);
      let issuer: URL;
      try {
        issuer = new URL(
          compose(["exec", "-T", "frontend", "printenv", "OIDC_ISSUER"]).trim(),
        );
      } catch {
        throw new Error("IDENTITY_PROVIDER_ISSUER_UNAVAILABLE");
      }

      try {
        await signIn(page, outsider.username, env.PHASE4_E2E_PASSWORD!);
        await page
          .getByText("Account is disabled, contact your administrator.", {
            exact: true,
          })
          .waitFor({ state: "visible" });
      } catch {
        throw new Error("DISABLED_IDENTITY_REJECTION_NOT_OBSERVED");
      }
      const rejectionLocation = new URL(page.url());
      expect(
        rejectionLocation.origin === issuer.origin &&
          rejectionLocation.pathname.startsWith(
            `${issuer.pathname}/login-actions/`,
          ),
        "DISABLED_IDENTITY_REJECTION_NOT_FROM_CONFIGURED_PROVIDER",
      ).toBe(true);

      const sessionResponse = await page.request.get("/auth/session");
      expect(sessionResponse.status()).toBe(401);
      const sessionData = (await sessionResponse.json()) as {
        authenticated?: boolean;
      };
      if (sessionData.authenticated) {
        throw new Error("INACTIVE_IDENTITY_AUTHENTICATION_NOT_BLOCKED");
      }
      expect(sessionData.authenticated).toBe(false);
      expect(
        (await page.context().cookies()).some(
          (cookie) => cookie.name === "taskspace.session",
        ),
      ).toBe(false);
      await expectNoBrowserStorage(page);

      console.info("INACTIVE_PROFILE_BOUNDARY_COMPLETE");
    } finally {
      const cleanup = new Cleanup();
      await cleanup.stage("restore administrator session", async () => {
        if (!primaryEmployeeId || !primarySubject)
          throw new Error("ADMIN_SESSION_IDENTITY_UNAVAILABLE");
        await restoreAdministratorSession(
          page,
          primaryEmployeeId,
          primarySubject,
        );
      });
      const notifications: ReturnType<typeof discoverNotifications> = [];
      const jobs = new Set<string>();
      const knownJobIds = [
        ...(reportId ? [reportId] : []),
        ...(memberReportId ? [memberReportId] : []),
      ];
      await cleanup.stage("discover exact notifications", () => {
        if (member.employeeId) {
          notifications.push(
            ...discoverNotifications({
              recipientEmployeeId: member.employeeId,
              taskId,
            }),
          );
          if (memberReportId) {
            notifications.push(
              ...discoverNotifications({
                recipientEmployeeId: member.employeeId,
                projectId,
                reportId: memberReportId,
              }),
            );
          }
        }
        if (manager.employeeId && reportId) {
          notifications.push(
            ...discoverNotifications({
              recipientEmployeeId: manager.employeeId,
              projectId,
              reportId,
            }),
          );
        }
      });
      await cleanup.stage("discover exact report jobs", () => {
        if (reportId && projectId && manager.employeeId) {
          const count = sql(
            "job-db",
            "job",
            "job",
            `select count(*) from jobs where id=${sqlLiteral(reportId)}::uuid and related_project_id=${sqlLiteral(projectId)}::uuid and submitter_employee_id=${sqlLiteral(manager.employeeId)}::uuid and job_type='PROJECT_TASK_EXPORT';`,
          );
          if (count !== "1") throw new Error("Known report ownership changed.");
          jobs.add(reportId);
        }
        if (memberReportId && projectId && member.employeeId) {
          const count = sql(
            "job-db",
            "job",
            "job",
            `select count(*) from jobs where id=${sqlLiteral(memberReportId)}::uuid and related_project_id=${sqlLiteral(projectId)}::uuid and submitter_employee_id=${sqlLiteral(member.employeeId)}::uuid and job_type='PROJECT_TASK_EXPORT';`,
          );
          if (count !== "1")
            throw new Error("Known member report ownership changed.");
          jobs.add(memberReportId);
        }
      });
      await cleanup.stage("delete exact report jobs", () => {
        jobs.forEach(deleteJob);
      });
      await cleanup.stage("delete exact notification", () =>
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
      for (const identity of identities) {
        await cleanupOwnedIdentity(cleanup, identity, primarySubject!);
      }
      await cleanup.stage("verify identity zero counts", () => {
        const names = identities
          .map((identity) => sqlLiteral(identity.username))
          .join(",");
        if (
          sql(
            "employee-db",
            "employee",
            "employee",
            `select count(*) from employees where username in (${names});`,
          ) !== "0"
        )
          throw new Error("Disposable Employee profiles remain.");
      });
      await cleanup.stage("verify exact cleanup", () =>
        assertOwnedRowsRemoved({
          projectKey,
          projectId,
          taskIds: taskId ? [taskId] : [],
          jobIds: knownJobIds,
          notificationIds: notifications.map((item) => item.notificationId),
          sourceEventIds: [
            ...new Set([
              ...notifications.map((item) => item.sourceEventId),
              ...(assignmentEventId ? [assignmentEventId] : []),
            ]),
          ],
          workOutboxEventIds: assignmentEventId ? [assignmentEventId] : [],
        }),
      );
      await cleanup.stage("verify protected administrator", () => {
        const current = protectedAdministrator();
        if (current.subject !== primarySubject)
          throw new Error("Protected administrator subject changed.");
        verifyPrimaryAdministrator(current.username, current.subject);
      });
      cleanup.finish();
      console.info("CLEANUP_COMPLETE");
    }
  });
});
