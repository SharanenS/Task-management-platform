import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createClient } from "redis";
import { storageKey } from "../../src/shared/auth/policy";
const project = "taskspace-portals-development";
let target: string | undefined;
let verifyRecovery: ((page: Page) => Promise<void>) | undefined;
function container(service: string) {
  if (!["identity", "auth-sessions"].includes(service))
    throw new Error("Unapproved recovery target");
  const id = execFileSync(
    "docker",
    [
      "ps",
      "-a",
      "--filter",
      `label=com.docker.compose.project=${project}`,
      "--filter",
      `label=com.docker.compose.service=${service}`,
      "--format",
      "{{.ID}}",
    ],
    { encoding: "utf8" },
  ).trim();
  if (!/^[a-f0-9]{12}$/.test(id))
    throw new Error("Recovery ownership is ambiguous");
  const item = JSON.parse(
    execFileSync("docker", ["inspect", id, "--format", "{{json .}}"], {
      encoding: "utf8",
    }),
  );
  if (
    item.Config.Labels["com.docker.compose.project"] !== project ||
    item.Config.Labels["com.docker.compose.service"] !== service ||
    !item.State.Running ||
    item.State.Health.Status !== "healthy"
  )
    throw new Error("Recovery ownership or health failed");
  return id;
}
function start(id: string) {
  execFileSync("docker", ["start", id], { stdio: "pipe" });
}
async function restored(id: string) {
  start(id);
  await expect
    .poll(
      () =>
        execFileSync(
          "docker",
          ["inspect", id, "--format", "{{.State.Health.Status}}"],
          { encoding: "utf8" },
        ).trim(),
      { timeout: 40_000 },
    )
    .toBe("healthy");
}
test.beforeAll(() => {
  if (process.env.S1_RECOVERY !== "1")
    throw new Error("Recovery tests require explicit opt-in");
});
// Restoration has its own cleanup budget so a failed probe cannot consume it.
// The readiness deadline remains 40 seconds, and any cleanup failure fails the test.
test.afterEach(async ({ page }, info) => {
  try {
    if (target) await restored(target);
    if (verifyRecovery) await verifyRecovery(page);
  } catch (error) {
    const location = new URL(page.url());
    const directory = resolve("../../.local/auth/failures");
    mkdirSync(directory, { recursive: true });
    writeFileSync(
      resolve(directory, `recovery-${Date.now()}.json`),
      JSON.stringify(
        {
          boundary: info.title,
          applicationOrigin: location.origin === "http://127.0.0.1:3020",
          providerOrigin: location.origin === "http://127.0.0.1:8180",
          headings: await page
            .locator("h1,h2")
            .allTextContents()
            .catch(() => []),
        },
        null,
        2,
      ),
    );
    throw error;
  } finally {
    target = undefined;
    verifyRecovery = undefined;
  }
});
async function cleanTransaction(page: Page) {
  const cookie = (await page.context().cookies("http://127.0.0.1:3020")).find(
    (value) => value.name === "taskspace_transaction",
  );
  expect(Boolean(cookie)).toBe(true);
  const secrets = JSON.parse(
    readFileSync(resolve("../../.local/auth/development.json"), "utf8"),
  );
  const redis = createClient({
    url: `redis://:${secrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
    socket: { connectTimeout: 3000, reconnectStrategy: false },
  });
  redis.on("error", () => {});
  await redis.connect();
  try {
    const key = storageKey("transaction", cookie!.value);
    const value = JSON.parse((await redis.get(key))!);
    expect(value.state === new URL(page.url()).searchParams.get("state")).toBe(
      true,
    );
    await redis.del(key);
    expect(await redis.exists(key)).toBe(0);
  } finally {
    await redis.quit();
  }
}
test("identity outage denies sign-in and recovers", async ({ page }) => {
  const id = container("identity");
  target = id;
  verifyRecovery = async (page) => {
    await page.goto("/sign-in");
    await page.getByRole("button", { name: "Continue to sign in" }).click();
    await expect
      .poll(() => new URL(page.url()).origin === "http://127.0.0.1:8180")
      .toBe(true);
    await expect(page.locator("#username")).toBeVisible();
    await cleanTransaction(page);
  };
  try {
    execFileSync("docker", ["stop", "--time", "10", id], { stdio: "pipe" });
    await page.goto("/sign-in");
    await page.getByRole("button", { name: "Continue to sign in" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "couldn’t reach",
    );
  } finally {
    start(id);
  }
});
test("session-store outage denies protected entry and recovers", async ({
  page,
}) => {
  const id = container("auth-sessions");
  target = id;
  verifyRecovery = async (page) => {
    await page.goto("/auth/ready");
    await expect(
      page.getByRole("heading", { name: "Let’s get you signed in." }),
    ).toBeVisible();
  };
  await page.context().addCookies([
    {
      name: "taskspace_session",
      value: "a".repeat(43),
      url: "http://127.0.0.1:3020",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  try {
    execFileSync("docker", ["stop", "--time", "10", id], { stdio: "pipe" });
    await page.goto("/auth/ready");
    await expect(
      page.getByRole("heading", { name: "We can’t check your session." }),
    ).toBeVisible();
  } finally {
    start(id);
  }
});
