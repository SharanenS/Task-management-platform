import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createClient } from "redis";
import { storageKey } from "../../src/shared/auth/policy";

const appOrigin = "http://127.0.0.1:3020";
const providerOrigin = "http://127.0.0.1:8180";
const realm = "taskspace-portals";
const privatePath = resolve("../../.local/auth/development.json");
const secrets: Record<string, string> = JSON.parse(
  readFileSync(privatePath, "utf8"),
);
let bearer = "";
let userId = "";
let adminId = "";
const runId = randomUUID();
const username = `s1-${runId}`;
const managedUsername = `s4-${runId}`;
const managedEmail = `${managedUsername}@example.invalid`;
let managedOperationId = "";
let recipientCleanupVerified = true;
const password = randomBytes(32).toString("base64url");
const disposablePasswords = new Set([password]);
let reauthenticationProved = false;
let organizationSubject = "";
let organizationCleanupVerified = true;
let organizationCreatedEarliest = 0;
let organizationCreatedLatest = 0;
let createdEarliest = 0;
let createdLatest = 0;
const administratorGrants: string[] = [];
const receiptDirectory = resolve("../../.local/auth/runs");
const receiptPath = resolve(receiptDirectory, `${runId}.json`);
function receipt(status: string, extra: Record<string, unknown> = {}) {
  mkdirSync(receiptDirectory, { recursive: true });
  writeFileSync(
    receiptPath,
    JSON.stringify(
      {
        runId,
        managedOperationId,
        realm,
        userId,
        username,
        email: `${username}@example.invalid`,
        createdEarliest,
        createdLatest,
        status,
        reauthenticationProved,
        organizationSubject,
        organizationCreatedEarliest,
        organizationCreatedLatest,
        organizationCleanupVerified,
        ...extra,
      },
      null,
      2,
    ),
  );
}
async function admin(path: string, options: RequestInit = {}) {
  let response = await fetch(`${providerOrigin}/admin/realms/${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${bearer}`,
      "Content-Type": "application/json",
      ...options.headers,
    },
    signal: AbortSignal.timeout(5000),
  });
  if (response.status === 401) {
    const renewed = await fetch(
      `${providerOrigin}/realms/master/protocol/openid-connect/token`,
      {
        method: "POST",
        body: new URLSearchParams({
          grant_type: "password",
          client_id: "admin-cli",
          username: "portal-bootstrap",
          password: secrets.AUTH_BOOTSTRAP_PASSWORD,
        }),
      },
    );
    if (!renewed.ok)
      throw new Error("Acceptance identity authorization unavailable");
    const grant = await renewed.json();
    bearer = grant.access_token;
    if (grant.refresh_token) administratorGrants.push(grant.refresh_token);
    response = await fetch(`${providerOrigin}/admin/realms/${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  }
  if (!response.ok)
    throw new Error(
      `Acceptance identity operation failed (${response.status})`,
    );
  return response;
}
async function ownedUser() {
  const value = await (await admin(`${realm}/users/${userId}`)).json();
  const proof = JSON.parse(readFileSync(receiptPath, "utf8"));
  expect(
    proof.runId === runId &&
      proof.realm === realm &&
      proof.userId === userId &&
      value.id === userId &&
      value.username === username &&
      value.email === `${username}@example.invalid` &&
      value.firstName === "Acceptance" &&
      value.lastName === "Account" &&
      value.createdTimestamp >= createdEarliest - 1000 &&
      value.createdTimestamp <= createdLatest + 1000,
  ).toBe(true);
  return value;
}
function accountFixture(action: string, value?: string | boolean | null) {
  const ids = execFileSync(
    "docker",
    [
      "ps",
      "--filter",
      "label=com.docker.compose.project=taskspace-portals-development",
      "--filter",
      "label=com.docker.compose.service=people",
      "--format",
      "{{.ID}}",
    ],
    { encoding: "utf8" },
  ).trim();
  if (!/^[a-f0-9]{12}$/.test(ids))
    throw new Error("People fixture ownership is ambiguous");
  const item = JSON.parse(
    execFileSync("docker", ["inspect", ids, "--format", "{{json .}}"], {
      encoding: "utf8",
    }),
  );
  if (
    item.Config.Labels["com.docker.compose.project"] !==
      "taskspace-portals-development" ||
    item.Config.Labels["com.docker.compose.service"] !== "people" ||
    item.State.Health.Status !== "healthy"
  )
    throw new Error("People fixture ownership or health mismatch");
  const source = readFileSync(
    resolve("../../tests/account_entry/fixture.py"),
    "utf8",
  );
  const output = execFileSync(
    "docker",
    ["exec", "-i", ids, "python", "-c", source],
    {
      input: JSON.stringify({
        runId,
        subject: userId,
        username,
        action,
        value,
      }),
      encoding: "utf8",
    },
  );
  return JSON.parse(output);
}
async function ownAccessToken(
  context: import("@playwright/test").BrowserContext,
) {
  const cookie = (await context.cookies(appOrigin)).find(
    (value) => value.name === "taskspace_session",
  );
  expect(Boolean(cookie)).toBe(true);
  const client = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
  });
  client.on("error", () => {});
  await client.connect();
  try {
    const raw = await client.get(storageKey("session", cookie!.value));
    expect(Boolean(raw)).toBe(true);
    const value = JSON.parse(raw!);
    expect(value.subject === userId).toBe(true);
    return value.accessToken as string;
  } finally {
    await client.quit();
  }
}
async function captureAdmin(
  page: import("@playwright/test").Page,
  name: string,
) {
  if (process.env.S3_CAPTURE_ADMIN !== "1") return;
  const directory = resolve(
    "../../.local/admin/screens",
    runId,
    test.info().project.name,
  );
  mkdirSync(directory, { recursive: true });
  await page.screenshot({
    path: resolve(directory, `${name}.png`),
    fullPage: true,
  });
}
async function login(
  page: import("@playwright/test").Page,
  invalid = false,
  credential = password,
) {
  await page.goto("/sign-in");
  await page.getByRole("button", { name: "Continue to sign in" }).click();
  await expect
    .poll(() => new URL(page.url()).origin === providerOrigin)
    .toBe(true);
  await expect(page.locator("#password")).toBeVisible();
  if (await page.locator("#username").isVisible())
    await page.locator("#username").fill(username);
  else {
    expect(
      (await page.locator("#kc-attempted-username").inputValue()) === username,
    ).toBe(true);
    reauthenticationProved = true;
  }
  await page
    .locator("#password")
    .fill(invalid ? "incorrect-disposable-password" : credential);
  await page.locator("#kc-login").click();
}
test.beforeAll(async () => {
  receipt("initializing");
  const response = await fetch(
    `${providerOrigin}/realms/master/protocol/openid-connect/token`,
    {
      method: "POST",
      body: new URLSearchParams({
        grant_type: "password",
        client_id: "admin-cli",
        username: "portal-bootstrap",
        password: secrets.AUTH_BOOTSTRAP_PASSWORD,
      }),
      signal: AbortSignal.timeout(5000),
    },
  );
  if (!response.ok)
    throw new Error("Isolated authentication bootstrap unavailable");
  const grant = await response.json();
  bearer = grant.access_token;
  if (grant.refresh_token) administratorGrants.push(grant.refresh_token);
  const admins = await (
    await admin("master/users?username=portal-bootstrap&exact=true")
  ).json();
  expect(admins.length).toBe(1);
  adminId = admins[0].id;
  createdEarliest = Date.now();
  const created = await admin(`${realm}/users`, {
    method: "POST",
    body: JSON.stringify({
      username,
      enabled: true,
      firstName: "Acceptance",
      lastName: "Account",
      email: `${username}@example.invalid`,
      emailVerified: true,
      credentials: [{ type: "password", value: password, temporary: false }],
    }),
  });
  createdLatest = Date.now();
  const location = created.headers.get("location");
  if (!location) throw new Error("Disposable identity location missing");
  userId = location.split("/").pop()!;
  receipt("created");
  expect((await ownedUser()).enabled).toBe(true);
  accountFixture("create");
});
let testStartedAt = 0;
test.beforeEach(() => {
  testStartedAt = Date.now();
});
test.afterEach(async ({ context, page }, info) => {
  if (info.status !== info.expectedStatus) {
    const location = new URL(page.url());
    const scrub = (value: string) => {
      let text = value
        .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, "Bearer [omitted]")
        .replace(
          /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g,
          "[token omitted]",
        )
        .replace(/https?:\/\/[^\s<>]+/g, "[address omitted]")
        .replace(
          /\b(?:code|state|nonce|session_state|id_token|access_token|session_code)=\S+/g,
          "[protocol parameter omitted]",
        );
      for (const value of [
        username,
        ...disposablePasswords,
        ...Object.values(secrets),
      ])
        text = text.split(value).join("[private]");
      return text.slice(0, 300);
    };
    const directory = resolve("../../.local/auth/failures", runId);
    mkdirSync(directory, { recursive: true });
    const diagnostic = {
      boundary: info.title,
      errors: info.errors.map((error) => ({
        message: scrub(error.message ?? ""),
        locations:
          error.stack?.match(/authentication\.spec\.ts:\d+:\d+/g) ?? [],
      })),
      checkpoint: info.annotations
        .filter((value) => value.type === "auth-boundary")
        .at(-1)?.description,
      applicationOrigin: location.origin === appOrigin,
      providerOrigin: location.origin === providerOrigin,
      headings: (
        await page
          .locator("h1,h2")
          .allTextContents()
          .catch(() => [])
      ).map(scrub),
      alerts: (
        await page
          .locator('[role="alert"],#input-error-username,.pf-v5-c-alert__title')
          .allTextContents()
          .catch(() => [])
      ).map(scrub),
      cookies: (await context.cookies(appOrigin)).map((cookie) => ({
        name: cookie.name,
        httpOnly: cookie.httpOnly,
        sameSite: cookie.sameSite,
      })),
    };
    writeFileSync(
      resolve(
        directory,
        `${info.project.name}-${info.title.replace(/[^a-z0-9]+/gi, "-")}.json`,
      ),
      JSON.stringify(diagnostic, null, 2),
    );
  }
  const cookies = await context.cookies(appOrigin);
  const redis = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
  });
  redis.on("error", () => {});
  await redis.connect();
  try {
    for (const cookie of cookies) {
      const kind =
        cookie.name === "taskspace_session"
          ? "session"
          : cookie.name === "taskspace_transaction"
            ? "transaction"
            : null;
      if (!kind) continue;
      const key = storageKey(kind, cookie.value);
      const raw = await redis.get(key);
      if (raw) {
        const record = JSON.parse(raw);
        expect(
          kind === "session"
            ? record.subject === userId
            : record.createdAt >= testStartedAt &&
                record.createdAt <= Date.now(),
        ).toBe(true);
        await redis.del(key);
      }
      expect(await redis.exists(key)).toBe(0);
    }
  } finally {
    await redis.quit();
  }
});
async function managedMail() {
  const response = await fetch(
    `http://127.0.0.1:8025/api/v1/search?query=${encodeURIComponent(`to:${managedEmail}`)}`,
  );
  if (!response.ok) throw new Error("Local mail capture unavailable");
  const value = await response.json();
  return (value.messages ?? []) as { ID: string; To: { Address: string }[] }[];
}
async function setupLink() {
  let messages: { ID: string; To: { Address: string }[] }[] = [];
  await expect
    .poll(async () => {
      messages = await managedMail();
      return messages.length > 0;
    })
    .toBe(true);
  const message = messages[0];
  expect(message.To.some((to) => to.Address === managedEmail)).toBe(true);
  const response = await fetch(
    `http://127.0.0.1:8025/api/v1/message/${message.ID}`,
  );
  expect(response.ok).toBe(true);
  const mail = await response.json();
  const candidates =
    String(mail.HTML ?? mail.Text ?? "").match(/https?:\/\/[^\s<>"']+/g) ?? [];
  const link = candidates
    .map((value) => value.replaceAll("&amp;", "&"))
    .find((value) => {
      try {
        const u = new URL(value);
        return (
          u.origin === providerOrigin &&
          u.pathname === `/realms/${realm}/login-actions/action-token`
        );
      } catch {
        return false;
      }
    });
  expect(Boolean(link)).toBe(true);
  return link!;
}
async function clearManagedMail() {
  for (const message of await managedMail()) {
    expect(message.To.some((to) => to.Address === managedEmail)).toBe(true);
    expect(
      (
        await fetch(`http://127.0.0.1:8025/api/v1/messages`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ IDs: [message.ID] }),
        })
      ).ok,
    ).toBe(true);
  }
  expect((await managedMail()).length).toBe(0);
}
async function cleanupManaged() {
  if (!managedOperationId) return;
  const proof = accountFixture("managed_inspect", managedOperationId);
  if (!proof.absent) {
    const matches = await (
      await admin(`${realm}/users?username=${managedUsername}&exact=true`)
    ).json();
    expect(matches.length <= 1).toBe(true);
    const user = matches[0];
    if (user) {
      expect(
        user.username === managedUsername &&
          user.email === managedEmail &&
          user.attributes?.taskspaceProvisioningId?.[0] ===
            managedOperationId &&
          (!proof.subject || proof.subject === user.id),
      ).toBe(true);
    }
    expect(accountFixture("managed_cleanup", managedOperationId).cleaned).toBe(
      true,
    );
    if (user) {
      await admin(`${realm}/users/${user.id}`, { method: "DELETE" });
      const removed = await fetch(
        `${providerOrigin}/admin/realms/${realm}/users/${user.id}`,
        { headers: { Authorization: `Bearer ${bearer}` } },
      );
      expect(removed.status).toBe(404);
      const redis = createClient({
        url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
      });
      redis.on("error", () => {});
      await redis.connect();
      try {
        for await (const keys of redis.scanIterator({
          MATCH: "taskspace:portals:auth:v1:session:*",
          COUNT: 100,
        })) {
          for (const key of keys) {
            const raw = await redis.get(key);
            if (raw && JSON.parse(raw).subject === user.id) {
              await redis.del(key);
              expect(await redis.exists(key)).toBe(0);
            }
          }
        }
      } finally {
        await redis.quit();
      }
    }
  }
  await clearManagedMail();
  expect(accountFixture("managed_inspect", managedOperationId).absent).toBe(
    true,
  );
}
test.afterAll(async () => {
  let failure: unknown;
  let accountRemoved = false;
  let identityRemoved = false;
  let bootstrapPreserved = false;
  let grantsRevoked = true;
  try {
    if (userId) {
      await cleanupOrganization();
      await cleanupManaged();
      await ownedUser();
      accountRemoved = accountFixture("cleanup").cleaned === true;
      expect(accountRemoved).toBe(true);
      await admin(`${realm}/users/${userId}`, { method: "DELETE" });
      const check = await fetch(
        `${providerOrigin}/admin/realms/${realm}/users/${userId}`,
        { headers: { Authorization: `Bearer ${bearer}` } },
      );
      expect(check.status).toBe(404);
      identityRemoved = true;
    }
    const admins = await (
      await admin("master/users?username=portal-bootstrap&exact=true")
    ).json();
    bootstrapPreserved =
      admins.length === 1 && admins[0].id === adminId && admins[0].enabled;
    expect(bootstrapPreserved).toBe(true);
  } catch (error) {
    failure = error;
  } finally {
    for (const token of administratorGrants) {
      try {
        const response = await fetch(
          `${providerOrigin}/realms/master/protocol/openid-connect/logout`,
          {
            method: "POST",
            body: new URLSearchParams({
              client_id: "admin-cli",
              refresh_token: token,
            }),
            signal: AbortSignal.timeout(5000),
          },
        );
        if (response.status !== 204)
          throw new Error("Administrator grant cleanup failed");
      } catch {
        grantsRevoked = false;
        failure ??= new Error("Administrator grant cleanup failed");
      }
    }
    if (!organizationCleanupVerified)
      failure ??= new Error("Organization cleanup failed");
    if (!recipientCleanupVerified)
      failure ??= new Error("Recipient authentication cleanup failed");
    receipt(
      !failure &&
        accountRemoved &&
        identityRemoved &&
        bootstrapPreserved &&
        grantsRevoked
        ? "cleaned"
        : "blocked",
      {
        identityRemoved,
        bootstrapPreserved,
        grantsRevoked,
        accountRemoved,
        recipientCleanupVerified,
      },
    );
  }
  if (failure) throw failure;
});

test("protected entry and responsive sign-in expose no old interface", async ({
  page,
}) => {
  await page.goto("http://localhost:3020/");
  expect(new URL(page.url()).origin).toBe(appOrigin);
  await expect(page).toHaveURL(new URL("/sign-in", appOrigin).href);
  await expect(
    page.getByRole("heading", { name: "Make room for your best work." }),
  ).toBeVisible();
  await page.goto("/auth/expired");
  await expect(page).toHaveURL(new URL("/sign-in", appOrigin).href);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page
      .getByRole("link", { name: /Projects|Employees|Design system|Dashboard/ })
      .count(),
  ).toBe(0);
  await page.goto("/projects");
  await expect(
    page.getByRole("heading", {
      name: "This page isn’t available.",
    }),
  ).toBeVisible();
});
test("invalid sign-in is rejected before any authenticated application session", async ({
  page,
  context,
}) => {
  let submitted = false;
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      request.method() === "POST" &&
      url.origin === providerOrigin &&
      url.pathname.startsWith(`/realms/${realm}/login-actions/authenticate`)
    )
      submitted = true;
  });
  await login(page, true);
  await expect(
    page
      .locator("#input-error-username, .pf-v5-c-alert__title")
      .filter({ hasText: /Invalid username or password/i })
      .first(),
  ).toBeVisible();
  expect(submitted).toBe(true);
  expect(new URL(page.url()).origin === providerOrigin).toBe(true);
  expect(
    (await context.cookies(appOrigin)).some((c) =>
      c.name.includes("taskspace_session"),
    ),
  ).toBe(false);
  expect(
    (await (await admin(`${realm}/users/${userId}/sessions`)).json()).length,
  ).toBe(0);
});
test("valid sign-in, cookie privacy, server expiry and logout", async ({
  page,
  context,
}) => {
  test.info().annotations.push({
    type: "auth-boundary",
    description: "initial-sign-in",
  });
  await login(page);
  await expect(
    page.getByRole("heading", {
      name: "You’re securely signed in.",
    }),
  ).toBeVisible();
  if (process.env.S1_CAPTURE_READY === "1")
    await page.screenshot({
      path: resolve(`../../.local/auth/ready-${test.info().project.name}.png`),
      fullPage: true,
    });
  test.info().annotations.push({
    type: "auth-boundary",
    description: "protected-session",
  });
  await page.goto("/");
  await expect(page).toHaveURL(new URL("/auth/ready", appOrigin).href);
  await page.goto("/auth/expired");
  await expect(
    page.getByRole("heading", { name: "You’re securely signed in." }),
  ).toBeVisible();
  expect((await context.request.get("/auth/logout")).status()).toBe(405);
  expect(
    new URL(page.url()).origin === appOrigin &&
      new URL(page.url()).pathname === "/auth/ready",
  ).toBe(true);
  const cookie = (await context.cookies(appOrigin)).find(
    (c) => c.name === "taskspace_session",
  );
  expect(
    Boolean(
      cookie?.httpOnly &&
      cookie.sameSite === "Lax" &&
      /^[\w-]{43}$/.test(cookie.value),
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
  ).toBe(0);
  const redis = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
  });
  redis.on("error", () => {});
  await redis.connect();
  try {
    const key = storageKey("session", cookie!.value);
    const record = JSON.parse((await redis.get(key))!);
    expect(record.subject === userId).toBe(true);
    test.info().annotations.push({
      type: "auth-boundary",
      description: "server-expiry",
    });
    record.expiresAt = Date.now() - 1;
    await redis.set(key, JSON.stringify(record), {
      expiration: { type: "EX", value: 30 },
    });
    await page.reload();
    await expect(
      page.getByRole("heading", {
        name: "Let’s get you signed in.",
      }),
    ).toBeVisible();
    expect(await redis.exists(key)).toBe(0);
    test.info().annotations.push({
      type: "auth-boundary",
      description: "reauthentication",
    });
    await login(page);
    await expect(
      page.getByRole("heading", {
        name: "You’re securely signed in.",
      }),
    ).toBeVisible();
    const next = (await context.cookies(appOrigin)).find(
      (c) => c.name === "taskspace_session",
    )!;
    expect(next.value !== cookie!.value).toBe(true);
    test.info().annotations.push({
      type: "auth-boundary",
      description: "provider-logout",
    });
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "See you next time." }),
    ).toBeVisible();
    expect(
      (await context.cookies(appOrigin)).some(
        (c) => c.name === "taskspace_session",
      ),
    ).toBe(false);
    expect(await redis.exists(storageKey("session", next.value))).toBe(0);
    await page.goto("/auth/ready");
    await expect(
      page.getByRole("heading", {
        name: "Make room for your best work.",
      }),
    ).toBeVisible();
  } finally {
    await redis.quit();
  }
});
test("callback tampering and cross-origin authentication POSTs are rejected", async ({
  page,
  request,
  context,
}) => {
  await page.goto("/auth/callback?code=not-a-code&state=not-a-state");
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "could not be completed",
  );
  expect(
    (await context.cookies(appOrigin)).some(
      (c) => c.name === "taskspace_session",
    ),
  ).toBe(false);
  for (const path of ["/auth/login", "/auth/logout"]) {
    const response = await request.post(path, {
      headers: { Origin: "http://untrusted.invalid" },
    });
    expect(response.status()).toBe(403);
  }
});

test("nonce mismatch rejects a valid provider response without an application session", async ({
  page,
  context,
}) => {
  await page.goto("/sign-in");
  await page.getByRole("button", { name: "Continue to sign in" }).click();
  await expect
    .poll(() => new URL(page.url()).origin === providerOrigin)
    .toBe(true);
  const transaction = (await context.cookies(appOrigin)).find(
    (c) => c.name === "taskspace_transaction",
  );
  expect(Boolean(transaction)).toBe(true);
  const redis = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
  });
  redis.on("error", () => {});
  await redis.connect();
  try {
    const key = storageKey("transaction", transaction!.value);
    const record = JSON.parse((await redis.get(key))!);
    expect(record.state === new URL(page.url()).searchParams.get("state")).toBe(
      true,
    );
    record.nonce = randomUUID();
    await redis.set(key, JSON.stringify(record), {
      expiration: { type: "EX", value: 300 },
    });
    await page.locator("#username").fill(username);
    await page.locator("#password").fill(password);
    await page.locator("#kc-login").click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "could not be completed",
    );
    expect(
      (await context.cookies(appOrigin)).some(
        (c) => c.name === "taskspace_session",
      ),
    ).toBe(false);
    expect(await redis.exists(key)).toBe(0);
  } finally {
    await redis.quit();
  }
});

test("S2 current account status and one company role govern entry and direct GraphQL", async ({
  page,
  context,
}) => {
  const query = { query: "{ viewer { accountId companyRoles permissions } }" };
  const unauthenticatedHeaders: Record<string, string>[] = [
    {},
    { "X-Actor-Role": "ADMIN", "X-Actor-Id": "someone-else" },
  ];
  for (const headers of unauthenticatedHeaders) {
    const response = await context.request.post(
      "http://127.0.0.1:8020/graphql",
      {
        maxRetries: 0,
        headers: {
          "Content-Type": "application/json",
          Connection: "close",
          ...headers,
        },
        data: query,
      },
    );
    expect(response.status()).toBe(401);
  }
  await login(page);
  await expect(
    page.getByRole("heading", { name: "You’re securely signed in." }),
  ).toBeVisible();
  const cookie = (await context.cookies(appOrigin)).find(
    (c) => c.name === "taskspace_session",
  );
  expect(Boolean(cookie)).toBe(true);
  const redis = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
  });
  redis.on("error", () => {});
  await redis.connect();
  try {
    const raw = await redis.get(storageKey("session", cookie!.value));
    expect(Boolean(raw)).toBe(true);
    const session = JSON.parse(raw!);
    expect(session.subject === userId).toBe(true);
    const direct = () =>
      context.request.post("http://127.0.0.1:8020/graphql", {
        maxRetries: 0,
        headers: {
          "Content-Type": "application/json",
          Connection: "close",
          Authorization: `Bearer ${session.accessToken}`,
          "X-Actor-Role": "ADMIN",
          "X-Actor-Id": "someone-else",
        },
        data: query,
      });
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s2-initial-authorized-account",
    });
    const allowed = await direct();
    expect(allowed.status()).toBe(200);
    const actor = (await allowed.json()).data.viewer;
    expect(actor.accountId === runId).toBe(true);
    expect(actor.companyRoles).toEqual(["EMPLOYEE"]);
    expect(actor.permissions).toEqual(["account:self:read"]);
    for (const [action, value] of [
      ["account_active", false],
      ["profile_active", false],
      ["role", null],
      ["profile_missing", null],
    ] as const) {
      test.info().annotations.push({
        type: "auth-boundary",
        description: `s2-${action}`,
      });
      await ownedUser();
      accountFixture(action, value);
      expect((await direct()).status()).toBe(403);
      await page.reload();
      await expect(
        page.getByRole("heading", { name: "Your account isn’t ready." }),
      ).toBeVisible();
      if (action === "profile_missing") accountFixture("profile_restore");
      else if (action === "role") accountFixture("role", "EMPLOYEE");
      else accountFixture(action, true);
    }
    await ownedUser();
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s2-role-change-same-session",
    });
    accountFixture("role", "HR");
    const changed = await direct();
    expect(changed.status()).toBe(200);
    expect((await changed.json()).data.viewer.companyRoles).toEqual(["HR"]);
    await page.reload();
    await expect(page.getByText("HR · Verified account")).toBeVisible();
    expect(
      (await context.cookies(appOrigin)).find(
        (c) => c.name === "taskspace_session",
      )?.value === cookie!.value,
    ).toBe(true);
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s2-missing-account",
    });
    accountFixture("cleanup");
    expect((await direct()).status()).toBe(403);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Your account isn’t ready." }),
    ).toBeVisible();
  } finally {
    await redis.quit();
  }
});

test("S3 administrator workspace, password change and revoked-role denial", async ({
  page,
  context,
  request,
}) => {
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s3-unauthenticated-admin-entry",
  });
  await page.goto("/admin");
  await expect(
    page.getByRole("heading", { name: "Make room for your best work." }),
  ).toBeVisible();
  expect((await request.get("/auth/change-password")).status()).toBe(405);
  expect(
    (
      await request.post("/auth/change-password", {
        headers: { Origin: "https://untrusted.invalid" },
      })
    ).status(),
  ).toBe(403);
  await ownedUser();
  accountFixture("cleanup");
  accountFixture("create");
  await login(page);
  await expect(
    page.getByRole("heading", { name: "You’re securely signed in." }),
  ).toBeVisible();
  const adminQuery = {
    query: "{ adminWorkspace { viewer { accountId companyRoles } } }",
  };
  const directAdmin = async () =>
    request.post("http://127.0.0.1:8020/graphql", {
      headers: {
        Authorization: `Bearer ${await ownAccessToken(context)}`,
        "X-Actor-Role": "ADMIN",
        "X-Actor-Id": "another-person",
        Connection: "close",
      },
      data: adminQuery,
      maxRetries: 0,
    });
  const denied = await directAdmin();
  expect(denied.status()).toBe(200);
  const deniedResult = await denied.json();
  expect(deniedResult.data).toBeNull();
  expect(deniedResult.errors[0].extensions.code).toBe("FORBIDDEN");
  await page.goto("/admin/profile");
  await expect(
    page.getByRole("heading", { name: "You don’t have access to this page." }),
  ).toBeVisible();
  expect(
    (
      await context.request.post("/auth/change-password", {
        headers: { Origin: appOrigin },
        maxRedirects: 0,
      })
    ).status(),
  ).toBe(403);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "See you next time." }),
  ).toBeVisible();
  accountFixture("role", "ADMIN");
  await ownedUser();
  await admin(`${realm}/users/${userId}/reset-password`, {
    method: "PUT",
    body: JSON.stringify({
      type: "password",
      value: password,
      temporary: true,
    }),
  });
  expect((await ownedUser()).requiredActions.includes("UPDATE_PASSWORD")).toBe(
    true,
  );
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s3-required-first-password-change",
  });
  await login(page);
  await expect(page.locator("#password-new")).toBeVisible();
  expect(new URL(page.url()).origin === providerOrigin).toBe(true);
  expect(
    (await context.cookies(appOrigin)).some(
      (c) => c.name === "taskspace_session",
    ),
  ).toBe(false);
  const firstPassword = randomBytes(32).toString("base64url") + "aA1!";
  const finalPassword = randomBytes(32).toString("base64url") + "bB2!";
  disposablePasswords.add(firstPassword);
  disposablePasswords.add(finalPassword);
  await page.locator("#password-new").fill(firstPassword);
  await page.locator("#password-confirm").fill(firstPassword);
  await page.getByRole("button", { name: /submit/i }).click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Administration",
      exact: true,
    }),
  ).toBeVisible();
  expect((await ownedUser()).requiredActions.includes("UPDATE_PASSWORD")).toBe(
    false,
  );
  await expect(
    page.getByRole("navigation", { name: "Administration" }),
  ).toBeVisible();
  const navigation = page.getByRole("navigation", { name: "Administration" });
  for (const [name, href] of [
    ["Employees", "/admin/employees"],
    ["Company structure", "/admin/organization"],
  ] as const) {
    const link = navigation.getByRole("link", { name, exact: true });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", href);
  }
  expect(
    await page
      .getByRole("link", {
        name: /Projects|Workflows|Reports|Design system/,
      })
      .count(),
  ).toBe(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await captureAdmin(page, "overview");
  const authorized = await directAdmin();
  expect(authorized.status()).toBe(200);
  expect(
    (await authorized.json()).data.adminWorkspace.viewer.accountId === runId,
  ).toBe(true);
  const profileLink = page
    .getByRole("navigation", { name: "Administration" })
    .getByRole("link", { name: "Your profile" });
  await profileLink.focus();
  await expect(profileLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new URL("/admin/profile", appOrigin).href);
  await expect(
    page.getByRole("heading", { level: 1, name: "Your profile", exact: true }),
  ).toBeVisible();
  await captureAdmin(page, "profile");
  await page
    .getByRole("navigation", { name: "Administration" })
    .getByRole("link", { name: "Account security" })
    .click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Account security",
      exact: true,
    }),
  ).toBeVisible();
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s3-initiated-password-change",
  });
  await captureAdmin(page, "security");
  await page.getByRole("button", { name: "Change password" }).click();
  await expect(page.locator("#password")).toBeVisible();
  expect(new URL(page.url()).origin === providerOrigin).toBe(true);
  const usernameInput = page.locator("#username");
  if (await usernameInput.isVisible()) await usernameInput.fill(username);
  else {
    expect(
      (await page.locator("#kc-attempted-username").inputValue()) === username,
    ).toBe(true);
    reauthenticationProved = true;
  }
  await page.locator("#password").fill(firstPassword);
  await page.locator("#kc-login").click();
  await expect(page.locator("#password-new")).toBeVisible();
  await page.locator("#password-new").fill(finalPassword);
  await page.locator("#password-confirm").fill(finalPassword);
  await page.getByRole("button", { name: /submit/i }).click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Account security",
      exact: true,
    }),
  ).toBeVisible();
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s3-repeat-provisioning-preserves-password",
  });
  const adminsBefore = await (
    await admin(`${realm}/users?username=admin&exact=true`)
  ).json();
  execFileSync("python", ["scripts/initial-admin.py", "--verify"], {
    cwd: resolve("../.."),
    encoding: "utf8",
  });
  const provision = JSON.parse(
    readFileSync(resolve("../../.local/admin/last-result.json"), "utf8"),
  );
  expect(provision.created).toBe(false);
  const adminsAfter = await (
    await admin(`${realm}/users?username=admin&exact=true`)
  ).json();
  expect(
    JSON.stringify(adminsBefore.map((u: { id: string }) => u.id).sort()) ===
      JSON.stringify(adminsAfter.map((u: { id: string }) => u.id).sort()),
  ).toBe(true);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("heading", { name: "See you next time." }),
  ).toBeVisible();
  await login(page, false, firstPassword);
  await expect(page.locator("#input-error-username")).toBeVisible();
  expect(
    (await context.cookies(appOrigin)).some(
      (c) => c.name === "taskspace_session",
    ),
  ).toBe(false);
  await login(page, false, finalPassword);
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Administration",
      exact: true,
    }),
  ).toBeVisible();
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s3-role-revoked-same-session",
  });
  await ownedUser();
  accountFixture("role", "EMPLOYEE");
  const revoked = await directAdmin();
  expect(revoked.status()).toBe(200);
  const revokedResult = await revoked.json();
  expect(revokedResult.data).toBeNull();
  expect(revokedResult.errors[0].extensions.code).toBe("FORBIDDEN");
  await page.goto("/admin/security");
  await expect(
    page.getByRole("heading", { name: "You don’t have access to this page." }),
  ).toBeVisible();
});

test("S4 account creation, email activation, company access and reset history", async ({
  page,
  browser,
}) => {
  await ownedUser();
  accountFixture("role", "ADMIN");
  await admin(`${realm}/users/${userId}/reset-password`, {
    method: "PUT",
    body: JSON.stringify({
      type: "password",
      value: password,
      temporary: false,
    }),
  });
  await login(page);
  await expect(page).toHaveURL(`${appOrigin}/admin`);
  await page.goto("/admin/accounts");
  await expect(
    page.getByRole("heading", { name: "User accounts", exact: true, level: 1 }),
  ).toBeVisible();
  const create = page.locator("form").filter({
    has: page.getByRole("button", {
      name: "Create account & send setup email",
    }),
  });
  managedOperationId = await create
    .locator('input[name="requestId"]')
    .inputValue();
  receipt("managed-planned");
  await create
    .getByLabel("Full name", { exact: true })
    .fill("Managed Acceptance");
  await create.getByLabel("Username", { exact: true }).fill(managedUsername);
  await create.getByLabel("Email address", { exact: true }).fill(managedEmail);
  await create.getByRole("button").click();
  await expect(page.getByRole("status")).toContainText("request completed");
  const account = page.getByRole("article").filter({
    has: page.getByRole("heading", {
      name: "Managed Acceptance",
      exact: true,
    }),
  });
  await expect(account).toBeVisible();
  await captureAdmin(page, "accounts");
  test.info().annotations.push({
    type: "auth-boundary",
    description: "s4-email-accepted-and-owned-account-created",
  });
  const recipient = await browser.newContext({ baseURL: appOrigin });
  const member = await recipient.newPage();
  const recipientSubject = accountFixture(
    "managed_inspect",
    managedOperationId,
  ).subject;
  let recipientFailure: unknown;
  const clearRecipientRecords = async () => {
    const client = createClient({
      url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
    });
    client.on("error", () => {});
    await client.connect();
    try {
      for (const cookie of await recipient.cookies(appOrigin)) {
        const kind =
          cookie.name === "taskspace_session"
            ? "session"
            : cookie.name === "taskspace_transaction"
              ? "transaction"
              : null;
        if (!kind) continue;
        const key = storageKey(kind, cookie.value);
        const raw = await client.get(key);
        if (raw) {
          const record = JSON.parse(raw);
          expect(
            kind === "session"
              ? record.subject === recipientSubject
              : record.createdAt >= testStartedAt &&
                  record.createdAt <= Date.now() &&
                  (!record.expectedSubject ||
                    record.expectedSubject === recipientSubject),
          ).toBe(true);
          await client.del(key);
        }
        expect(await client.exists(key)).toBe(0);
      }
    } finally {
      await client.quit();
    }
    await recipient.clearCookies();
  };
  const memberPassword = randomBytes(32).toString("base64url");
  disposablePasswords.add(memberPassword);
  try {
    const link = await setupLink();
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-open-email-link",
    });
    await member.goto(link);
    const proceed = member.getByRole("link", { name: /proceed/i });
    if (await proceed.isVisible()) {
      const destination = new URL(
        (await proceed.getAttribute("href"))!,
        providerOrigin,
      );
      expect(destination.origin === providerOrigin).toBe(true);
      test.info().annotations.push({
        type: "auth-boundary",
        description: "s4-confirm-email-actions",
      });
      await proceed.click();
    }
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-require-password-form",
    });
    await expect(member.locator("#password-new")).toBeVisible();
    expect(new URL(member.url()).origin === providerOrigin).toBe(true);
    expect(
      (await recipient.cookies(appOrigin)).some(
        (c) => c.name === "taskspace_session",
      ),
    ).toBe(false);
    await member.locator("#password-new").fill(memberPassword);
    await member.locator("#password-confirm").fill(memberPassword);
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-submit-first-password",
    });
    await member.getByRole("button", { name: /submit/i }).click();
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-verify-email-and-required-actions",
    });
    await expect
      .poll(async () => {
        const users = await (
          await admin(`${realm}/users?username=${managedUsername}&exact=true`)
        ).json();
        return (
          users.length === 1 &&
          users[0].emailVerified &&
          !users[0].requiredActions.includes("UPDATE_PASSWORD")
        );
      })
      .toBe(true);
    const signIn = async (credential: string) => {
      await clearRecipientRecords();
      await member.goto(`${appOrigin}/sign-in`);
      await member.getByRole("button", { name: "Continue to sign in" }).click();
      await expect(member.locator("#username")).toBeVisible();
      await member.locator("#username").fill(managedUsername);
      await member.locator("#password").fill(credential);
      await member.locator("#kc-login").click();
    };
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-sign-in-created-account",
    });
    await signIn(memberPassword);
    await expect(
      member.getByRole("heading", { name: "You’re securely signed in." }),
    ).toBeVisible();
    const recipientCookie = (await recipient.cookies(appOrigin)).find(
      (c) => c.name === "taskspace_session",
    );
    expect(Boolean(recipientCookie)).toBe(true);
    const recipientStore = createClient({
      url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
    });
    recipientStore.on("error", () => {});
    await recipientStore.connect();
    let recipientToken = "";
    try {
      const raw = await recipientStore.get(
        storageKey("session", recipientCookie!.value),
      );
      expect(Boolean(raw)).toBe(true);
      const record = JSON.parse(raw!);
      expect(
        record.subject ===
          accountFixture("managed_inspect", managedOperationId).subject,
      ).toBe(true);
      recipientToken = record.accessToken;
    } finally {
      await recipientStore.quit();
    }
    const recipientViewer = () =>
      recipient.request.post("http://127.0.0.1:8020/graphql", {
        headers: {
          Authorization: `Bearer ${recipientToken}`,
          "X-Actor-Role": "ADMIN",
        },
        data: { query: "{viewer{accountId companyRoles}}" },
      });
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-check-created-account-boundary",
    });
    await member.goto(`${appOrigin}/admin/accounts`);
    await expect(
      member.getByRole("heading", {
        name: "You don’t have access to this page.",
        exact: true,
      }),
    ).toBeVisible();
    const statusForm = account.locator("form").filter({
      has: page.getByRole("button", {
        name: "Deactivate account",
        exact: true,
      }),
    });
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-deactivate-owned-account",
    });
    await expect(statusForm.getByRole("checkbox")).toBeVisible();
    await statusForm.getByRole("checkbox").check();
    await statusForm.getByRole("button").click();
    await expect(page.getByRole("status")).toContainText("request completed");
    const exact = await (
      await admin(`${realm}/users?username=${managedUsername}&exact=true`)
    ).json();
    expect(exact.length === 1 && exact[0].enabled === false).toBe(true);
    expect((await recipientViewer()).status()).toBe(403);
    await member.goto(`${appOrigin}/auth/ready`);
    await expect(
      member.getByRole("heading", {
        name: "Your account isn’t ready.",
        exact: true,
      }),
    ).toBeVisible();
    const activate = account.locator("form").filter({
      has: page.getByRole("button", {
        name: "Activate account",
        exact: true,
      }),
    });
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-reactivate-owned-account",
    });
    await expect(activate.getByRole("checkbox")).toBeVisible();
    await activate.getByRole("checkbox").check();
    await activate.getByRole("button").click();
    await expect(page.getByRole("status")).toContainText("request completed");
    const role = account.locator("form").filter({
      has: page.getByRole("button", { name: "Save role", exact: true }),
    });
    test.info().annotations.push({
      type: "auth-boundary",
      description: "s4-change-owned-company-role",
    });
    await role.getByRole("combobox").selectOption("HR");
    await role.getByRole("checkbox").check();
    await role.getByRole("button").click();
    await expect(page.getByRole("status")).toContainText("request completed");
    await expect(account.getByRole("combobox")).toHaveValue("HR");
    await clearManagedMail();
    const reset = account.locator("form").filter({
      has: page.getByRole("button", {
        name: "Send password reset email",
        exact: true,
      }),
    });
    await reset.getByRole("checkbox").check();
    await reset.getByRole("button").click();
    await expect(page.getByRole("status")).toContainText("request completed");
    const resetLink = await setupLink();
    await member.goto(resetLink);
    const resetProceed = member.getByRole("link", { name: /proceed/i });
    if (await resetProceed.isVisible()) {
      const destination = new URL(
        (await resetProceed.getAttribute("href"))!,
        providerOrigin,
      );
      expect(destination.origin === providerOrigin).toBe(true);
      await resetProceed.click();
    }
    await expect(member.locator("#password-new")).toBeVisible();
    const replacementPassword = randomBytes(32).toString("base64url");
    disposablePasswords.add(replacementPassword);
    await member.locator("#password-new").fill(replacementPassword);
    await member.locator("#password-confirm").fill(replacementPassword);
    await member.getByRole("button", { name: /submit/i }).click();
    await expect(member.locator("#password-new")).not.toBeVisible();
    await signIn(memberPassword);
    await expect(member.locator("#input-error-username")).toBeVisible();
    expect(
      (await recipient.cookies(appOrigin)).some(
        (c) => c.name === "taskspace_session",
      ),
    ).toBe(false);
    await signIn(replacementPassword);
    await expect(
      member.getByRole("heading", { name: "You’re securely signed in." }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Recent account changes",
        exact: true,
      }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    test.info().annotations.push({
      type: "auth-boundary",
      description:
        "s4-email-activation-disable-enable-role-reset-audit-complete",
    });
  } catch (error) {
    recipientFailure = error;
    const directory = resolve("../../.local/auth/failures", runId);
    mkdirSync(directory, { recursive: true });
    writeFileSync(
      resolve(directory, "recipient-boundary.json"),
      JSON.stringify(
        {
          providerOrigin: new URL(member.url()).origin === providerOrigin,
          applicationOrigin: new URL(member.url()).origin === appOrigin,
          headings: await member
            .locator("h1,h2")
            .allTextContents()
            .catch(() => []),
          alerts: await member
            .locator("#kc-error-message,.instruction,.alert-error")
            .allTextContents()
            .catch(() => []),
          controls: await member
            .locator("input,button")
            .evaluateAll((elements) =>
              elements.map((e) => ({
                id: e.id,
                name: e.getAttribute("name"),
                type: e.getAttribute("type"),
                label: e.tagName === "BUTTON" ? e.textContent : null,
              })),
            ),
        },
        null,
        2,
      ),
    );
    throw error;
  } finally {
    try {
      await clearRecipientRecords();
    } catch (error) {
      recipientCleanupVerified = false;
      if (!recipientFailure) throw error;
    } finally {
      await recipient.close();
    }
  }
});

async function ownedOrganizationIdentity() {
  const user = await (
    await admin(`${realm}/users/${organizationSubject}`)
  ).json();
  expect(
    user.id === organizationSubject &&
      user.username === `s5-${runId}` &&
      user.email === `s5-${runId}@example.invalid` &&
      user.attributes?.taskspaceAcceptanceRun?.[0] === runId &&
      user.createdTimestamp >= organizationCreatedEarliest - 1000 &&
      user.createdTimestamp <= organizationCreatedLatest + 1000,
  ).toBe(true);
  return user;
}
async function cleanupOrganization() {
  if (organizationCleanupVerified) return;
  if (organizationSubject) await ownedOrganizationIdentity();
  expect(accountFixture("organization_cleanup").cleaned).toBe(true);
  if (organizationSubject) {
    await admin(`${realm}/users/${organizationSubject}`, { method: "DELETE" });
    const response = await fetch(
      `${providerOrigin}/admin/realms/${realm}/users/${organizationSubject}`,
      { headers: { Authorization: `Bearer ${bearer}` } },
    );
    expect(response.status).toBe(404);
  }
  const check = accountFixture("organization_inspect");
  expect(
    check.employees.length === 0 &&
      check.auditCount === 0 &&
      check.subject === null,
  ).toBe(true);
  organizationCleanupVerified = true;
  receipt("organization-cleaned");
}

test("S5 company structure, directory-first reporting and verified account association", async ({
  page,
  context,
}) => {
  page.setDefaultTimeout(5000);
  let boundary = "administrator entry";
  organizationCleanupVerified = false;
  receipt("organization-started");
  try {
    accountFixture("role", "ADMIN");
    await login(page);
    await page.goto("/admin/organization");
    await expect(
      page.getByRole("heading", { name: "Company structure", exact: true }),
    ).toBeVisible();
    boundary = "department creation";
    const department = `Department ${runId}`;
    const title = `Title ${runId}`;
    await page.getByLabel("Department name", { exact: true }).fill(department);
    await page
      .getByRole("button", { name: "Add department", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    boundary = "job title creation";
    await page.getByLabel("Job title name", { exact: true }).fill(title);
    await page
      .getByRole("button", { name: "Add job title", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    boundary = "directory-first employee creation";
    await page.goto("/admin/employees");
    const create = page.locator("form").filter({
      has: page.getByRole("button", { name: "Add employee", exact: true }),
    });
    const leader = `Leader ${runId}`;
    const contributor = `Contributor ${runId}`;
    boundary = "leader name entry";
    await create.getByLabel("Full name", { exact: true }).fill(leader);
    boundary = "leader department selection";
    await create
      .getByLabel("Department", { exact: true })
      .selectOption({ label: department });
    boundary = "leader title selection";
    await create
      .getByLabel("Job title", { exact: true })
      .selectOption({ label: title });
    boundary = "employee create submit";
    await create
      .getByRole("button", { name: "Add employee", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    await create.getByLabel("Full name", { exact: true }).fill(contributor);
    await create
      .getByLabel("Reports to", { exact: true })
      .selectOption({ label: leader });
    boundary = "employee create submit";
    await create
      .getByRole("button", { name: "Add employee", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    const owned = accountFixture("organization_inspect");
    expect(
      owned.employees.length === 2 &&
        owned.employees.every(
          (e: { accountId: string | null }) => e.accountId === null,
        ),
    ).toBe(true);
    const leaderId = owned.employees.find(
      (e: { name: string }) => e.name === leader,
    ).id;
    const contributorId = owned.employees.find(
      (e: { name: string }) => e.name === contributor,
    ).id;
    boundary = "reporting cycle rejection";
    const leaderRow = page
      .locator("details")
      .filter({ has: page.locator("summary").filter({ hasText: leader }) });
    await leaderRow.locator("summary").click();
    await leaderRow
      .getByLabel("Reports to", { exact: true })
      .selectOption(contributorId);
    await leaderRow
      .getByRole("button", { name: "Save employee", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("rejected");
    boundary = "verified identity creation";
    organizationCreatedEarliest = Date.now();
    const response = await admin(`${realm}/users`, {
      method: "POST",
      body: JSON.stringify({
        username: `s5-${runId}`,
        email: `s5-${runId}@example.invalid`,
        enabled: true,
        attributes: { taskspaceAcceptanceRun: [runId] },
      }),
    });
    organizationCreatedLatest = Date.now();
    const location = response.headers.get("location");
    organizationSubject = location?.split("/").pop() ?? "";
    expect(/^[0-9a-f-]{36}$/.test(organizationSubject)).toBe(true);
    receipt("organization-identity-created");
    await ownedOrganizationIdentity();
    const secondary = accountFixture(
      "organization_account",
      organizationSubject,
    );
    boundary = "disabled identity rejection";
    await ownedOrganizationIdentity();
    await admin(`${realm}/users/${organizationSubject}`, {
      method: "PUT",
      body: JSON.stringify({ enabled: false }),
    });
    expect((await ownedOrganizationIdentity()).enabled).toBe(false);
    const rejectedLink = await context.request.post(
      "http://127.0.0.1:8020/graphql",
      {
        headers: { Authorization: `Bearer ${await ownAccessToken(context)}` },
        data: {
          query:
            "mutation($input: OrganizationChangeInput!) { changeOrganization(input:$input) { state } }",
          variables: {
            input: {
              requestId: randomUUID(),
              action: "ACCOUNT_LINK",
              entityId: contributorId,
              version: 1,
              accountId: secondary.accountId,
            },
          },
        },
      },
    );
    const rejection = await rejectedLink.json();
    expect(rejection.errors?.[0]?.extensions?.code).toBe(
      "ACCOUNT_CHANGE_REJECTED",
    );
    expect(rejection.errors?.[0]?.message).toBe("identity_not_active");
    expect(
      accountFixture("organization_inspect").employees.find(
        (e: { id: string }) => e.id === contributorId,
      ).accountId === null,
    ).toBe(true);
    await admin(`${realm}/users/${organizationSubject}`, {
      method: "PUT",
      body: JSON.stringify({ enabled: true }),
    });
    expect((await ownedOrganizationIdentity()).enabled).toBe(true);
    boundary = "existing employee account-entry selection";
    await page.goto(
      `/admin/accounts?employeeId=${encodeURIComponent(leaderId)}`,
    );
    await expect(
      page.getByLabel("Employee record", { exact: true }),
    ).toHaveValue(leaderId);
    await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(
      leader,
    );
    await expect(page.getByLabel("Full name", { exact: true })).toHaveAttribute(
      "readonly",
      "",
    );
    boundary = "employee account association";
    await page.goto("/admin/employees");
    const row = page.locator("details").filter({
      has: page.locator("summary").filter({ hasText: contributor }),
    });
    await row.locator("summary").click();
    const link = row.locator("form").filter({
      has: page.getByRole("button", { name: "Link account", exact: true }),
    });
    await link
      .getByLabel("Existing account", { exact: true })
      .selectOption(secondary.accountId);
    await link.getByLabel("I confirm this change").check();
    await link
      .getByRole("button", { name: "Link account", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    const linked = accountFixture("organization_inspect");
    expect(
      linked.employees.find((e: { id: string }) => e.id === contributorId)
        .accountId === secondary.accountId,
    ).toBe(true);
    expect(
      linked.employees.find((e: { id: string }) => e.id === leaderId)
        .accountId === null,
    ).toBe(true);
    boundary = "employment changes preserve company role";
    await page
      .getByLabel("Search employees", { exact: true })
      .fill(contributor);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const edited = page.locator("details").filter({
      has: page.locator("summary").filter({ hasText: contributor }),
    });
    await edited.locator("summary").click();
    await edited
      .getByLabel("Job title", { exact: true })
      .selectOption({ label: title });
    await edited
      .getByRole("button", { name: "Save employee", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("saved");
    await page
      .getByLabel("Search employees", { exact: true })
      .fill(contributor);
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(
      page.locator("summary").filter({ hasText: contributor }),
    ).toContainText("EMPLOYEE account");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    boundary = "direct non-administrator authorization";
    const access = await ownAccessToken(context);
    for (const role of ["EMPLOYEE", "MANAGER", "HR"]) {
      accountFixture("role", role);
      const denied = await context.request.post(
        "http://127.0.0.1:8020/graphql",
        {
          headers: {
            Authorization: `Bearer ${access}`,
            "X-Actor-Role": "ADMIN",
          },
          data: { query: "{ organizationWorkspace { employees { id } } }" },
        },
      );
      expect((await denied.json()).errors[0].extensions.code).toBe("FORBIDDEN");
      await page.goto("/admin/employees");
      await expect(page).toHaveURL(new URL("/access-denied", appOrigin).href);
    }
    boundary = "owned resource cleanup";
    await cleanupOrganization();
  } catch (error) {
    let message =
      error instanceof Error ? error.message : "Unknown test boundary failure";
    for (const value of [...disposablePasswords, ...Object.values(secrets)])
      message = message.split(value).join("[private]");
    message = message
      .replace(/https?:\/\/[^\s<>]+/g, "[address omitted]")
      .slice(0, 2000);
    const diagnostic = {
      stage: boundary,
      message,
      project: test.info().project.name,
      status: "failed",
      origin:
        new URL(page.url()).origin === appOrigin
          ? "application"
          : new URL(page.url()).origin === providerOrigin
            ? "identity-provider"
            : "other",
    };
    mkdirSync(resolve("../../test-results/reports/s5"), { recursive: true });
    writeFileSync(
      resolve(`../../test-results/reports/s5/${runId}.json`),
      JSON.stringify(diagnostic, null, 2),
    );
    throw new Error(`S5 boundary failed: ${boundary}`);
  } finally {
    accountFixture("role", "EMPLOYEE");
  }
});
