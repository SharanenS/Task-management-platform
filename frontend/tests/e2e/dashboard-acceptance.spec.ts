import { expect, test, type Page } from "@playwright/test";

import {
  Cleanup,
  type OwnedIdentity,
  checkedUuid,
  cleanupOwnedIdentity,
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
const baseURL = env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3010";
const rootURL = new URL("/", baseURL).toString();
const enabled =
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

async function firstLogin(page: Page, identity: OwnedIdentity) {
  await signIn(page, identity.username, env.PHASE4_E2E_TEMP_PASSWORD!);
  await page.locator("#password-new").fill(env.PHASE4_E2E_PASSWORD!);
  await page.locator("#password-confirm").fill(env.PHASE4_E2E_PASSWORD!);
  await page.getByRole("button", { name: /submit/i }).click();
  await expect(page).toHaveURL(rootURL);
}

test.describe("Phase 12: Advanced Dashboard + UX Refinement Acceptance", () => {
  test.skip(
    !enabled,
    "Phase 12 acceptance environment credentials not fully configured.",
  );

  test("Dashboard Multi-Role Scope, Viewports, Navigation, and Dynamics", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    const cleanup = new Cleanup();
    const marker = runMarker("P12-DASH");
    const adminIdentity = protectedAdministrator();
    verifyPrimaryAdministrator(adminIdentity.username, adminIdentity.subject);

    let memberIdentity: OwnedIdentity | undefined;
    let managerIdentity: OwnedIdentity | undefined;
    let projectId: string | undefined;
    let taskId: string | undefined;

    try {
      // 1. Authenticate as Primary Administrator
      console.log("MULTI_ROLE_ENV_READY");
      await page.goto("/sign-in");
      await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
      await expect(page).toHaveURL(rootURL);

      const adminProfile = await gql(page, "query{me{id role}}");
      expect(adminProfile.errors).toBeUndefined();
      expect(adminProfile.data.me.role).toBe("ADMIN");

      // Provision disposable Member
      const safeSuffix = marker
        .toLowerCase()
        .replaceAll(/[^a-z0-9-]/g, "")
        .slice(-18);
      const memberUsername = `p12-member-${safeSuffix}`;
      const memberEmail = `${memberUsername}@example.invalid`;
      const provMemberRes = await gql(
        page,
        "mutation($input:ProvisionEmployeeInput!){provisionEmployee(input:$input){id}}",
        {
          input: {
            idempotencyKey: crypto.randomUUID(),
            username: memberUsername,
            email: memberEmail,
            displayName: "P12 Member",
            role: "MEMBER",
            active: true,
            temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD!,
          },
        },
      );
      expect(provMemberRes.errors).toBeUndefined();
      memberIdentity = {
        username: memberUsername,
        email: memberEmail,
        employeeId: checkedUuid(
          provMemberRes.data.provisionEmployee.id,
          "Member Employee ID",
        ),
      };
      recordIdentity(memberIdentity, adminIdentity.subject);

      // Provision disposable Manager
      const managerUsername = `p12-mgr-${safeSuffix}`;
      const managerEmail = `${managerUsername}@example.invalid`;
      const provMgrRes = await gql(
        page,
        "mutation($input:ProvisionEmployeeInput!){provisionEmployee(input:$input){id}}",
        {
          input: {
            idempotencyKey: crypto.randomUUID(),
            username: managerUsername,
            email: managerEmail,
            displayName: "P12 Manager",
            role: "MANAGER",
            active: true,
            temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD!,
          },
        },
      );
      expect(provMgrRes.errors).toBeUndefined();
      managerIdentity = {
        username: managerUsername,
        email: managerEmail,
        employeeId: checkedUuid(
          provMgrRes.data.provisionEmployee.id,
          "Manager Employee ID",
        ),
      };
      recordIdentity(managerIdentity, adminIdentity.subject);

      // Admin creates project and assigns members
      const createProjRes = await gql(
        page,
        "mutation($input:CreateProjectInput!){createProject(input:$input){id key}}",
        {
          input: {
            key: `P12${safeSuffix.slice(-6).toUpperCase()}`,
            name: `Dashboard Project ${marker}`,
            description: "Acceptance testing project",
          },
        },
      );
      expect(createProjRes.errors).toBeUndefined();
      projectId = checkedUuid(
        createProjRes.data.createProject.id,
        "Project ID",
      );

      // Add Manager as PROJECT_MANAGER
      const addMgrRes = await gql(
        page,
        "mutation($id:ID!,$employee:ID!){addProjectMember(projectId:$id,employeeId:$employee,role:PROJECT_MANAGER){id}}",
        {
          id: projectId,
          employee: managerIdentity.employeeId,
        },
      );
      expect(addMgrRes.errors).toBeUndefined();

      // Add Member as CONTRIBUTOR
      const addMemRes = await gql(
        page,
        "mutation($id:ID!,$employee:ID!){addProjectMember(projectId:$id,employeeId:$employee,role:CONTRIBUTOR){id}}",
        {
          id: projectId,
          employee: memberIdentity.employeeId,
        },
      );
      expect(addMemRes.errors).toBeUndefined();

      // Create Task assigned to Member
      const createDailyTask = await gql(
        page,
        "mutation($projectId:ID!,$input:CreateTaskInput!){createTask(projectId:$projectId,input:$input){id number}}",
        {
          projectId,
          input: {
            title: `Task for Member ${marker}`,
            priority: "HIGH",
            assigneeEmployeeId: memberIdentity.employeeId,
          },
        },
      );
      expect(createDailyTask.errors).toBeUndefined();
      taskId = checkedUuid(createDailyTask.data.createTask.id, "Task ID");
      console.log("ADMIN_SETUP_COMPLETE");

      // 2. Member Acceptance: First login, initial password change, verify Member dashboard
      await logout(page);
      await firstLogin(page, memberIdentity);

      // Verify Dashboard content for Member
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back, P12 Member/,
        }),
      ).toBeVisible();
      // Member should see project metrics (accessible = 1)
      const memberAccessibleCard = page.getByRole("link", {
        name: /Accessible/i,
      });
      await expect(memberAccessibleCard).toBeVisible();
      await expect(memberAccessibleCard).toContainText("Accessible");
      await expect(memberAccessibleCard).toContainText("1");
      // Member does NOT manage projects -> Managed project cards should not be shown
      await expect(page.getByText("Projects you manage")).not.toBeVisible();
      // Member sees Assigned Work summary
      await expect(
        page.getByRole("heading", { name: "My Assigned Work" }),
      ).toBeVisible();
      // Recent assigned tasks contains the created task
      await expect(page.getByText(`Task for Member ${marker}`)).toBeVisible();
      console.log("MEMBER_BOUNDARY_COMPLETE");

      // Test Responsive Viewports and Document Overflow for Member
      // Desktop (1280px)
      await page.setViewportSize({ width: 1280, height: 800 });
      let isOverflowing = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      );
      expect(isOverflowing).toBe(false);

      // Tablet (768px)
      await page.setViewportSize({ width: 768, height: 1024 });
      isOverflowing = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      );
      expect(isOverflowing).toBe(false);

      // Mobile (390px)
      await page.setViewportSize({ width: 390, height: 844 });
      isOverflowing = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      );
      expect(isOverflowing).toBe(false);

      // Reset to Desktop
      await page.setViewportSize({ width: 1280, height: 800 });

      // Keyboard Reachability and Visible Focus
      const refreshButton = page.getByRole("button", { name: /Refresh/i });
      await expect(refreshButton).toBeVisible();
      await refreshButton.focus();
      await expect(refreshButton).toBeFocused();

      const activeCard = page.locator('a[href="/projects?status=ACTIVE"]');
      await expect(activeCard).toBeVisible();
      await activeCard.focus();
      await expect(activeCard).toBeFocused();
      await expect(activeCard).toHaveClass(/focus:ring-2/);
      console.log("VIEWPORT_AND_ACCESSIBILITY_COMPLETE");

      // Filter Handoff, Navigation, and Cursor Reset via Keyboard activation
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/.*\/projects\?status=ACTIVE/);
      await expect(
        page.getByRole("heading", { name: "Projects" }),
      ).toBeVisible();
      // Verify no leftover pagination cursor in URL
      const currentUrl = page.url();
      expect(currentUrl).not.toContain("after=");
      expect(currentUrl).not.toContain("cursor=");

      // Browser History: Back to Dashboard
      await page.goBack();
      await expect(page).toHaveURL(rootURL);
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back, P12 Member/,
        }),
      ).toBeVisible();

      // Browser History: Forward to filtered directory
      await page.goForward();
      await expect(page).toHaveURL(/.*\/projects\?status=ACTIVE/);

      // Browser History: Back to Dashboard
      await page.goBack();
      await expect(page).toHaveURL(rootURL);
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back, P12 Member/,
        }),
      ).toBeVisible();

      // Refresh behavior
      await page.reload();
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back, P12 Member/,
        }),
      ).toBeVisible();
      await expect(page.getByText(`Task for Member ${marker}`)).toBeVisible();
      console.log("FILTER_AND_HISTORY_COMPLETE");

      // 3. Manager Acceptance
      await logout(page);
      await firstLogin(page, managerIdentity);

      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back, P12 Manager/,
        }),
      ).toBeVisible();
      // Manager manages 1 project -> Managed Projects card must be visible with scope note
      await expect(page.getByText("Projects you manage")).toBeVisible();
      const managerManagedCard = page.getByRole("link", {
        name: /Managed/i,
      });
      await expect(managerManagedCard).toContainText("Managed");
      await expect(managerManagedCard).toContainText("1");
      // Manager Managed Task Breakdown card is visible
      await expect(
        page.getByRole("heading", { name: "Managed Projects Tasks" }),
      ).toBeVisible();
      console.log("MANAGER_BOUNDARY_COMPLETE");

      // 4. Admin Acceptance
      await logout(page);
      await signIn(page, env.DEV_USER_USERNAME!, env.DEV_USER_PASSWORD!);
      await expect(page).toHaveURL(rootURL);
      await expect(
        page.getByRole("heading", {
          level: 1,
          name: /Welcome back/,
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("heading", { name: "Platform Tasks Breakdown" }),
      ).toBeVisible();
      await expect(page.getByText("All managed projects")).toBeVisible();
      console.log("ADMIN_BOUNDARY_COMPLETE");

      // 5. Dynamic Role/Membership Revocation
      // Attempting to remove member while task is assigned must be rejected by work domain policy
      const blockedRemoval = await gql(
        page,
        "mutation($id:ID!,$employee:ID!){removeProjectMember(projectId:$id,employeeId:$employee){id}}",
        {
          id: projectId,
          employee: memberIdentity.employeeId,
        },
      );
      expect(blockedRemoval.errors).toBeDefined();
      expect(blockedRemoval.errors?.[0]?.message).toContain(
        "Reassign the employee's tasks before removing project membership.",
      );

      // Reassign/unassign task before removing membership as required by work domain policy
      const unassignRes = await gql(
        page,
        "mutation($projectId:ID!,$taskId:ID!,$assigneeEmployeeId:ID,$expectedVersion:Int!){assignTask(projectId:$projectId,taskId:$taskId,assigneeEmployeeId:$assigneeEmployeeId,expectedVersion:$expectedVersion){id}}",
        {
          projectId,
          taskId,
          assigneeEmployeeId: null,
          expectedVersion: 1,
        },
      );
      expect(unassignRes.errors).toBeUndefined();

      // Admin removes Member from the project
      const removeMemberRes = await gql(
        page,
        "mutation($id:ID!,$employee:ID!){removeProjectMember(projectId:$id,employeeId:$employee){id}}",
        {
          id: projectId,
          employee: memberIdentity.employeeId,
        },
      );
      expect(removeMemberRes.errors).toBeUndefined();

      // Member signs back in: Dashboard should now reflect 0 accessible projects
      await logout(page);
      await signIn(page, memberIdentity.username, env.PHASE4_E2E_PASSWORD!);
      await expect(page).toHaveURL(rootURL);
      // Accessible projects total should now be 0
      const totalProjectsCard = page.getByRole("link", {
        name: /Accessible/i,
      });
      await expect(totalProjectsCard).toContainText("0");
      // Assigned tasks should now display empty state
      await expect(page.getByText("No assigned tasks")).toBeVisible();
      console.log("DYNAMIC_REVOCATION_COMPLETE");
    } finally {
      // Clean up disposable records using captured validated IDs
      if (taskId) {
        await cleanup.stage("delete task records", () => {
          sql(
            "work-db",
            "work",
            "work",
            `DELETE FROM task_activities WHERE task_id = ${sqlLiteral(taskId!)};`,
          );
          sql(
            "work-db",
            "work",
            "work",
            `DELETE FROM work_outbox_events WHERE task_id = ${sqlLiteral(taskId!)};`,
          );
          sql(
            "work-db",
            "work",
            "work",
            `DELETE FROM tasks WHERE id = ${sqlLiteral(taskId!)};`,
          );
        });
      }
      if (projectId) {
        await cleanup.stage("delete project records", () => {
          sql(
            "work-db",
            "work",
            "work",
            `DELETE FROM project_memberships WHERE project_id = ${sqlLiteral(projectId!)};`,
          );
          sql(
            "work-db",
            "work",
            "work",
            `DELETE FROM projects WHERE id = ${sqlLiteral(projectId!)};`,
          );
        });
      }
      if (memberIdentity?.employeeId || managerIdentity?.employeeId) {
        await cleanup.stage("delete notification records", () => {
          const ids = [
            memberIdentity?.employeeId,
            managerIdentity?.employeeId,
          ].filter(Boolean) as string[];
          for (const empId of ids) {
            sql(
              "notification-db",
              "notification",
              "notification",
              `DELETE FROM notification_source_events WHERE id IN (SELECT source_event_id FROM notifications WHERE recipient_employee_id = ${sqlLiteral(empId)});`,
            );
            sql(
              "notification-db",
              "notification",
              "notification",
              `DELETE FROM notifications WHERE recipient_employee_id = ${sqlLiteral(empId)};`,
            );
          }
        });
      }
      if (memberIdentity) {
        await cleanupOwnedIdentity(
          cleanup,
          memberIdentity,
          adminIdentity.subject,
        );
      }
      if (managerIdentity) {
        await cleanupOwnedIdentity(
          cleanup,
          managerIdentity,
          adminIdentity.subject,
        );
      }
      cleanup.finish();

      // Post-cleanup reconciliation assertions for exact captured IDs
      if (taskId) {
        const remainingTasks = sql(
          "work-db",
          "work",
          "work",
          `SELECT count(*) FROM tasks WHERE id = ${sqlLiteral(taskId)};`,
        );
        expect(remainingTasks.trim()).toBe("0");
      }
      if (projectId) {
        const remainingProjects = sql(
          "work-db",
          "work",
          "work",
          `SELECT count(*) FROM projects WHERE id = ${sqlLiteral(projectId)};`,
        );
        expect(remainingProjects.trim()).toBe("0");
      }
      if (memberIdentity?.employeeId) {
        const remainingMember = sql(
          "employee-db",
          "employee",
          "employee",
          `SELECT count(*) FROM employees WHERE id = ${sqlLiteral(memberIdentity.employeeId)};`,
        );
        expect(remainingMember.trim()).toBe("0");
      }
      if (managerIdentity?.employeeId) {
        const remainingManager = sql(
          "employee-db",
          "employee",
          "employee",
          `SELECT count(*) FROM employees WHERE id = ${sqlLiteral(managerIdentity.employeeId)};`,
        );
        expect(remainingManager.trim()).toBe("0");
      }

      console.log("CLEANUP_COMPLETE");
    }
  });
});
