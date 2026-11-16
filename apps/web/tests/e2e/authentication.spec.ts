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
const password = randomBytes(32).toString("base64url");
let reauthenticationProved = false;
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
        realm,
        userId,
        username,
        email: `${username}@example.invalid`,
        createdEarliest,
        createdLatest,
        status,
        reauthenticationProved,
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
async function login(page: import("@playwright/test").Page, invalid = false) {
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
    .fill(invalid ? "incorrect-disposable-password" : password);
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
      for (const value of [username, password, ...Object.values(secrets)])
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
test.afterAll(async () => {
  let failure: unknown;
  let accountRemoved = false;
  let identityRemoved = false;
  let bootstrapPreserved = false;
  let grantsRevoked = true;
  try {
    if (userId) {
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
    receipt(
      !failure &&
        accountRemoved &&
        identityRemoved &&
        bootstrapPreserved &&
        grantsRevoked
        ? "cleaned"
        : "blocked",
      { identityRemoved, bootstrapPreserved, grantsRevoked, accountRemoved },
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
