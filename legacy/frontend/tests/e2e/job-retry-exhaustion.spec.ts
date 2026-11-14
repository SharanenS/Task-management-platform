import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test, type Browser, type Page } from "@playwright/test";

const composeFile = fileURLToPath(
  new URL("../../../compose.yaml", import.meta.url),
);
const env = process.env;
const enabled =
  env.RUN_JOB_RETRY_E2E === "1" &&
  env.DEV_USER_USERNAME &&
  env.DEV_USER_PASSWORD &&
  env.PHASE4_E2E_TEMP_PASSWORD &&
  env.PHASE4_E2E_PASSWORD &&
  env.KEYCLOAK_ADMIN_USERNAME &&
  env.KEYCLOAK_ADMIN_PASSWORD;

type Identity = {
  username: string;
  email: string;
  role: "MEMBER" | "MANAGER";
  employeeId?: string;
  subject?: string;
  ownershipVerified?: boolean;
};

function docker(args: string[]) {
  const result = spawnSync("docker", ["compose", "-f", composeFile, ...args], {
    encoding: "utf8",
    windowsHide: true,
    env,
  });
  if (result.status !== 0) throw new Error("Scoped Docker command failed.");
  return result.stdout;
}

function configureKeycloakAdmin() {
  docker([
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
}

function exactKeycloakUsers(username: string) {
  const users = JSON.parse(
    docker([
      "exec",
      "-T",
      "keycloak",
      "/opt/keycloak/bin/kcadm.sh",
      "get",
      "users",
      "-r",
      "taskspace",
      "-q",
      `username=${username}`,
    ]),
  ) as Array<{ id: string; username: string; enabled?: boolean }>;
  return users.filter((user) => user.username === username);
}

function checkedUuid(value: string | undefined, label: string) {
  if (
    !value ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  )
    throw new Error(`${label} was not a UUID.`);
  return value;
}

function sqlLiteral(value: string) {
  return `'${value.replaceAll("'", "''")}'`;
}

function postgres(
  service: "employee-db" | "job-db" | "work-db",
  database: string,
  sql: string,
) {
  return docker([
    "exec",
    "-T",
    service,
    "psql",
    "-U",
    database,
    "-d",
    database,
    "-At",
    "-c",
    sql,
  ]).trim();
}

async function gql(page: Page, query: string, variables: object = {}) {
  return (
    await page.request.post("/graphql", { data: { query, variables } })
  ).json();
}

async function authenticatedPage(
  browser: Browser,
  username: string,
  password: string,
  replacement?: string,
) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("http://localhost:3010/sign-in");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  if (replacement) {
    await page.locator("#password-new").fill(replacement);
    await page.locator("#password-confirm").fill(replacement);
    await page.getByRole("button", { name: "Submit" }).click();
  }
  await expect(page).toHaveURL("http://localhost:3010/");
  return { context, page };
}

const retryMutation =
  "mutation R($id: ID!, $version: Int!) { retryJob(jobId: $id, expectedVersion: $version) { id status version executionGeneration manualRetryCount } }";

test.describe.configure({ mode: "serial", retries: 0 });

test("ADMIN retry follows real automatic exhaustion without duplicate intent", async ({
  browser,
}, info) => {
  test.skip(
    !enabled || info.project.name !== "desktop",
    "Set RUN_JOB_RETRY_E2E=1 with the protected administrator and disposable-identity credentials from the process environment.",
  );
  test.setTimeout(300_000);

  const marker = `p9-${Date.now().toString(36).toLowerCase()}`;
  const identities: Identity[] = [
    {
      username: `${marker}-member`,
      email: `${marker}-member@example.test`,
      role: "MEMBER",
    },
    {
      username: `${marker}-manager`,
      email: `${marker}-manager@example.test`,
      role: "MANAGER",
    },
  ];
  const [member, manager] = identities;
  const projectKey = `P9-${marker.toUpperCase()}`;
  const contexts: Array<{ close(): Promise<void> }> = [];
  let projectId: string | undefined;
  let jobId: string | undefined;
  let primarySubject: string | undefined;

  try {
    configureKeycloakAdmin();
    const primaryUsers = exactKeycloakUsers(env.DEV_USER_USERNAME!);
    if (primaryUsers.length !== 1 || !primaryUsers[0].enabled)
      throw new Error("Protected primary identity verification failed.");
    primarySubject = checkedUuid(
      primaryUsers[0].id,
      "Protected primary subject",
    );

    const admin = await authenticatedPage(
      browser,
      env.DEV_USER_USERNAME!,
      env.DEV_USER_PASSWORD!,
    );
    contexts.push(admin.context);

    for (const identity of identities) {
      if (exactKeycloakUsers(identity.username).length !== 0)
        throw new Error("A generated disposable username already exists.");
      const provisioned = await gql(
        admin.page,
        "mutation P($input: ProvisionEmployeeInput!) { provisionEmployee(input: $input) { id } }",
        {
          input: {
            idempotencyKey: `${marker}-${identity.role.toLowerCase()}`,
            username: identity.username,
            email: identity.email,
            displayName: identity.username,
            role: identity.role,
            active: true,
            temporaryPassword: env.PHASE4_E2E_TEMP_PASSWORD,
          },
        },
      );
      expect(provisioned.errors).toBeUndefined();
      identity.employeeId = checkedUuid(
        provisioned.data.provisionEmployee.id,
        "Disposable Employee ID",
      );
      const provisionedUsers = exactKeycloakUsers(identity.username);
      if (provisionedUsers.length !== 1)
        throw new Error("Disposable identity ownership is ambiguous.");
      identity.subject = checkedUuid(
        provisionedUsers[0].id,
        "Disposable Keycloak subject",
      );
      const employeeLink = postgres(
        "employee-db",
        "employee",
        `SELECT count(*) FROM employees WHERE id=${sqlLiteral(identity.employeeId)} AND keycloak_subject=${sqlLiteral(identity.subject)} AND username=${sqlLiteral(identity.username)};`,
      );
      if (employeeLink !== "1")
        throw new Error(
          "Disposable Employee subject link verification failed.",
        );
      identity.ownershipVerified = true;
      const first = await authenticatedPage(
        browser,
        identity.username,
        env.PHASE4_E2E_TEMP_PASSWORD!,
        env.PHASE4_E2E_PASSWORD!,
      );
      await first.context.close();
    }

    const project = await gql(
      admin.page,
      "mutation C($input: CreateProjectInput!) { createProject(input: $input) { id version } }",
      { input: { key: projectKey, name: `Phase 9 retry ${marker}` } },
    );
    projectId = project.data.createProject.id;
    await gql(
      admin.page,
      "mutation S($id: ID!, $version: Int!) { setProjectStatus(projectId: $id, status: ACTIVE, expectedVersion: $version) { id } }",
      { id: projectId, version: project.data.createProject.version },
    );
    await gql(
      admin.page,
      "mutation A($id: ID!, $employee: ID!) { addProjectMember(projectId: $id, employeeId: $employee, role: CONTRIBUTOR) { id } }",
      { id: projectId, employee: member.employeeId },
    );

    const memberSession = await authenticatedPage(
      browser,
      member.username,
      env.PHASE4_E2E_PASSWORD!,
    );
    contexts.push(memberSession.context);
    const managerSession = await authenticatedPage(
      browser,
      manager.username,
      env.PHASE4_E2E_PASSWORD!,
    );
    contexts.push(managerSession.context);

    const submitted = await gql(
      memberSession.page,
      "mutation S($input: SubmitProjectTaskExportInput!) { submitProjectTaskExport(input: $input) { id version } }",
      {
        input: {
          projectId,
          includeCompleted: true,
          idempotencyKey: `${marker}-exhaustion`,
        },
      },
    );
    expect(submitted.errors).toBeUndefined();
    jobId = submitted.data.submitProjectTaskExport.id;

    docker(["stop", "job-worker"]);
    const dispatched = await gql(
      memberSession.page,
      "mutation D($id: ID!, $version: Int!) { dispatchJob(jobId: $id, expectedVersion: $version) { id status } }",
      { id: jobId, version: submitted.data.submitProjectTaskExport.version },
    );
    expect(dispatched.errors).toBeUndefined();
    docker(["stop", "work"]);
    docker(["up", "-d", "--no-deps", "job-worker"]);

    await expect
      .poll(
        async () =>
          (
            await gql(
              admin.page,
              "query J($id: ID!) { job(id: $id) { status version executionGeneration retryExhausted manualRetryCount resultContent attempts { attemptNumber status failureCode retryable retryScheduledAt startedAt finishedAt } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 90_000 },
      )
      .toMatchObject({
        status: "FAILED",
        executionGeneration: 3,
        retryExhausted: true,
        manualRetryCount: 0,
        resultContent: null,
        attempts: [
          {
            attemptNumber: 1,
            status: "RETRY_SCHEDULED",
            failureCode: "DEPENDENCY_UNAVAILABLE",
            retryable: true,
          },
          {
            attemptNumber: 2,
            status: "RETRY_SCHEDULED",
            failureCode: "DEPENDENCY_UNAVAILABLE",
            retryable: true,
          },
          {
            attemptNumber: 3,
            status: "FAILED",
            failureCode: "DEPENDENCY_UNAVAILABLE",
            retryable: true,
          },
        ],
      });

    const exhaustedJob = (
      await gql(
        admin.page,
        "query J($id: ID!) { job(id: $id) { version attempts { attemptNumber startedAt finishedAt retryScheduledAt } } }",
        { id: jobId },
      )
    ).data.job;
    expect(exhaustedJob.attempts[0].retryScheduledAt).toBeTruthy();
    expect(exhaustedJob.attempts[1].retryScheduledAt).toBeTruthy();
    for (const attempt of exhaustedJob.attempts) {
      expect(attempt.startedAt).toBeTruthy();
      expect(attempt.finishedAt).toBeTruthy();
    }

    await memberSession.page.goto(`/jobs/${jobId}`);
    await expect(
      memberSession.page.getByText(/retry budget is exhausted/i),
    ).toBeVisible();
    await expect(
      memberSession.page.getByRole("button", { name: "Retry job" }),
    ).toHaveCount(0);
    expect(
      await memberSession.page.locator("text=/Attempt [123]/").count(),
    ).toBe(3);
    expect(await memberSession.page.locator("body").innerText()).not.toMatch(
      /lease token|fenc(e|ing)/i,
    );
    const memberDenied = await gql(memberSession.page, retryMutation, {
      id: jobId,
      version: exhaustedJob.version,
    });
    expect(memberDenied.errors[0].extensions.code).toBe("FORBIDDEN");

    await managerSession.page.goto(`/jobs/${jobId}`);
    await expect(
      managerSession.page.getByRole("button", { name: "Retry job" }),
    ).toHaveCount(0);
    const managerDenied = await gql(managerSession.page, retryMutation, {
      id: jobId,
      version: exhaustedJob.version,
    });
    expect(managerDenied.errors[0].extensions.code).toBe("FORBIDDEN");

    await admin.page.goto(`/jobs/${jobId}`);
    const retryButton = admin.page.getByRole("button", { name: "Retry job" });
    await expect(retryButton).toBeVisible();
    await retryButton.click();
    await admin.page.getByRole("button", { name: "Cancel" }).click();
    await expect(admin.page.getByRole("dialog")).toHaveCount(0);
    const afterCancel = (
      await gql(
        admin.page,
        "query J($id: ID!) { job(id: $id) { version executionGeneration } }",
        {
          id: jobId,
        },
      )
    ).data.job;
    expect(afterCancel).toEqual({
      version: exhaustedJob.version,
      executionGeneration: 3,
    });

    docker(["up", "-d", "--wait", "work"]);
    await retryButton.click();
    const confirm = admin.page.getByRole("button", { name: "Confirm retry" });
    await confirm.dblclick();

    const conflicts = await Promise.all([
      gql(admin.page, retryMutation, {
        id: jobId,
        version: exhaustedJob.version,
      }),
      gql(admin.page, retryMutation, {
        id: jobId,
        version: exhaustedJob.version,
      }),
    ]);
    for (const conflict of conflicts) {
      expect(["VERSION_CONFLICT", "JOB_NOT_RETRYABLE"]).toContain(
        conflict.errors[0].extensions.code,
      );
      expect(JSON.stringify(conflict)).not.toMatch(
        /traceback|lease|fenc|postgres|job:/i,
      );
    }

    await expect
      .poll(
        async () =>
          (
            await gql(
              admin.page,
              "query J($id: ID!) { job(id: $id) { status executionGeneration manualRetryCount resultContent attempts { attemptNumber status } } }",
              { id: jobId },
            )
          ).data.job,
        { timeout: 60_000 },
      )
      .toMatchObject({
        status: "SUCCEEDED",
        executionGeneration: 4,
        manualRetryCount: 1,
        attempts: [
          { attemptNumber: 1, status: "RETRY_SCHEDULED" },
          { attemptNumber: 2, status: "RETRY_SCHEDULED" },
          { attemptNumber: 3, status: "FAILED" },
          { attemptNumber: 4, status: "SUCCEEDED" },
        ],
      });

    const finalJob = (
      await gql(
        admin.page,
        "query J($id: ID!) { job(id: $id) { status version executionGeneration manualRetryCount resultContent resultChecksum attempts { attemptNumber status failureCode retryScheduledAt } } }",
        { id: jobId },
      )
    ).data.job;
    expect(finalJob.resultContent).toContain("reference,title");
    expect(finalJob.resultChecksum).toMatch(/^[a-f0-9]{64}$/);
    await expect
      .poll(
        async () =>
          (
            await gql(admin.page, retryMutation, {
              id: jobId,
              version: finalJob.version,
            })
          ).errors?.[0]?.extensions?.code,
        { timeout: 30_000 },
      )
      .toBe("JOB_NOT_RETRYABLE");

    await admin.page.reload();
    await expect(admin.page.getByText("Export result")).toBeVisible();
    expect(await admin.page.locator("text=/Attempt [1-4]/").count()).toBe(4);

    const persistedJobId = checkedUuid(jobId, "Persisted job ID");
    const counts = postgres(
      "job-db",
      "job",
      `SELECT (SELECT count(*) FROM jobs WHERE id=${sqlLiteral(persistedJobId)}),(SELECT count(*) FROM job_attempts WHERE job_id=${sqlLiteral(persistedJobId)}),(SELECT count(*) FROM job_publication_outbox WHERE job_id=${sqlLiteral(persistedJobId)}),(SELECT count(*) FROM jobs WHERE id=${sqlLiteral(persistedJobId)} AND result_content IS NOT NULL);`,
    );
    expect(counts).toBe("1|4|4|1");
  } finally {
    const cleanupFailures: string[] = [];
    const cleanup = async (
      label: string,
      action: () => unknown | Promise<unknown>,
    ) => {
      try {
        await action();
      } catch {
        cleanupFailures.push(label);
      }
    };

    await cleanup("restore Work Service", () =>
      docker(["up", "-d", "--wait", "work"]),
    );
    await cleanup("restore Job worker", () =>
      docker(["up", "-d", "--wait", "job-worker"]),
    );
    await cleanup("restore recovery process", () =>
      docker(["up", "-d", "--wait", "job-recovery"]),
    );
    for (const [index, context] of contexts.reverse().entries())
      await cleanup(`close browser context ${index + 1}`, () =>
        context.close(),
      );

    await cleanup("configure Keycloak administration", () =>
      configureKeycloakAdmin(),
    );
    await cleanup("remove exact job", () => {
      if (!jobId) return;
      docker([
        "exec",
        "-T",
        "job",
        "python",
        "-m",
        "app.development_cleanup",
        checkedUuid(jobId, "Cleanup job ID"),
      ]);
    });
    await cleanup("remove exact project", () => {
      if (!projectId) return;
      docker([
        "exec",
        "-T",
        "work",
        "python",
        "-m",
        "app.development_cleanup",
        "--project-id",
        checkedUuid(projectId, "Cleanup project ID"),
        "--expected-key",
        projectKey,
      ]);
    });

    for (const identity of identities) {
      await cleanup(`remove exact ${identity.role} Employee profile`, () => {
        if (
          !identity.employeeId ||
          !identity.subject ||
          !identity.ownershipVerified ||
          !primarySubject
        )
          return;
        checkedUuid(identity.employeeId, "Cleanup Employee ID");
        const subject = checkedUuid(
          identity.subject,
          "Cleanup Employee subject",
        );
        if (subject === primarySubject)
          throw new Error("Refusing to remove the protected primary subject.");
        const link = postgres(
          "employee-db",
          "employee",
          `SELECT count(*) FROM employees WHERE id=${sqlLiteral(identity.employeeId)} AND keycloak_subject=${sqlLiteral(subject)} AND username=${sqlLiteral(identity.username)};`,
        );
        if (link !== "1") {
          identity.ownershipVerified = false;
          throw new Error("Disposable Employee ownership is ambiguous.");
        }
        docker([
          "exec",
          "-T",
          "employee",
          "python",
          "-m",
          "app.development_access",
          "remove",
          "--subject",
          subject,
          "--protected-subject",
          primarySubject,
        ]);
      });
      await cleanup(`remove exact ${identity.role} Keycloak identity`, () => {
        if (!identity.subject || !identity.ownershipVerified || !primarySubject)
          return;
        const subject = checkedUuid(
          identity.subject,
          "Cleanup Keycloak subject",
        );
        if (subject === primarySubject)
          throw new Error("Refusing to remove the protected primary subject.");
        const exactUsers = exactKeycloakUsers(identity.username);
        if (exactUsers.length !== 1 || exactUsers[0].id !== subject)
          throw new Error("Disposable Keycloak ownership is ambiguous.");
        docker([
          "exec",
          "-T",
          "keycloak",
          "/opt/keycloak/bin/kcadm.sh",
          "delete",
          `users/${subject}`,
          "-r",
          "taskspace",
        ]);
      });
    }

    await cleanup("verify zero current-run persistence", () => {
      const jobCounts = postgres(
        "job-db",
        "job",
        `SELECT (SELECT count(*) FROM jobs WHERE idempotency_key=${sqlLiteral(`${marker}-exhaustion`)}),(SELECT count(*) FROM job_attempts a JOIN jobs j ON j.id=a.job_id WHERE j.idempotency_key=${sqlLiteral(`${marker}-exhaustion`)}),(SELECT count(*) FROM jobs WHERE idempotency_key=${sqlLiteral(`${marker}-exhaustion`)} AND result_content IS NOT NULL),(SELECT count(*) FROM job_publication_outbox o JOIN jobs j ON j.id=o.job_id WHERE j.idempotency_key=${sqlLiteral(`${marker}-exhaustion`)});`,
      );
      const workCounts = postgres(
        "work-db",
        "work",
        `SELECT (SELECT count(*) FROM projects WHERE key=${sqlLiteral(projectKey)}),(SELECT count(*) FROM tasks t JOIN projects p ON p.id=t.project_id WHERE p.key=${sqlLiteral(projectKey)});`,
      );
      const employeeCount = postgres(
        "employee-db",
        "employee",
        `SELECT count(*) FROM employees WHERE username IN (${sqlLiteral(member.username)},${sqlLiteral(manager.username)});`,
      );
      const identityCount = identities.reduce(
        (count, identity) =>
          count + exactKeycloakUsers(identity.username).length,
        0,
      );
      if (
        jobCounts !== "0|0|0|0" ||
        workCounts !== "0|0" ||
        employeeCount !== "0" ||
        identityCount !== 0
      )
        throw new Error("Current-run resources remain after cleanup.");
    });

    await cleanup("verify disrupted service health", () => {
      const services = docker([
        "ps",
        "--format",
        "json",
        "work",
        "job-worker",
        "job-recovery",
      ])
        .trim()
        .split(/\r?\n/)
        .filter(Boolean)
        .map((line) => JSON.parse(line) as { Health?: string; State?: string });
      if (
        services.length !== 3 ||
        services.some(
          (service) =>
            service.State !== "running" || service.Health !== "healthy",
        )
      )
        throw new Error("A disrupted service did not recover health.");
    });

    await cleanup("verify protected primary administrator", () => {
      if (!primarySubject) throw new Error("Primary subject was not recorded.");
      const primaryUsers = exactKeycloakUsers(env.DEV_USER_USERNAME!);
      if (
        primaryUsers.length !== 1 ||
        primaryUsers[0].id !== primarySubject ||
        !primaryUsers[0].enabled
      )
        throw new Error("Protected primary Keycloak identity changed.");
      const profile = postgres(
        "employee-db",
        "employee",
        `SELECT count(*) FROM employees WHERE username=${sqlLiteral(env.DEV_USER_USERNAME!)} AND keycloak_subject=${sqlLiteral(primarySubject)} AND active IS TRUE AND role='ADMIN';`,
      );
      if (profile !== "1")
        throw new Error("Protected primary Employee profile changed.");
    });

    if (cleanupFailures.length)
      throw new Error(
        `Cleanup or integrity checks failed: ${cleanupFailures.join(", ")}`,
      );
  }
});
