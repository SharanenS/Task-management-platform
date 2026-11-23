import { execFileSync } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";
import { createClient } from "redis";
import { expect, type BrowserContext, type Page } from "@playwright/test";
import { storageKey } from "../../src/shared/auth/policy";
export const appOrigin = "http://127.0.0.1:3020";
const providerOrigin = "http://127.0.0.1:8180";
const realm = "taskspace-portals";
export class ProjectAcceptance {
  runId = randomUUID();
  primary = {
    id: "",
    username: `s1-${this.runId}`,
    password: randomBytes(32).toString("base64url"),
    earliest: 0,
    latest: 0,
  };
  secondary = {
    id: "",
    username: `s7-${this.runId}`,
    password: randomBytes(32).toString("base64url"),
    earliest: 0,
    latest: 0,
  };
  privateSecrets: Record<string, string> = JSON.parse(
    readFileSync(resolve("../../.local/auth/development.json"), "utf8"),
  );
  primaryAccountCreated = false;
  secondaryAccountCreated = false;
  bearer = "";
  grants: string[] = [];
  bootstrapId = "";
  boundary = "initialization";
  diagnosticScope: "s7" | "s8" | "s9" = "s7";
  receiptPath = resolve(`../../.local/auth/runs/${this.runId}.json`);
  write(status: string, extra: Record<string, unknown> = {}) {
    mkdirSync(resolve("../../.local/auth/runs"), { recursive: true });
    writeFileSync(
      this.receiptPath,
      JSON.stringify(
        {
          runId: this.runId,
          status,
          realm,
          username: this.primary.username,
          userId: this.primary.id,
          secondaryUserId: this.secondary.id,
          primaryCreatedEarliest: this.primary.earliest,
          primaryCreatedLatest: this.primary.latest,
          secondaryCreatedEarliest: this.secondary.earliest,
          secondaryCreatedLatest: this.secondary.latest,
          ...extra,
        },
        null,
        2,
      ),
    );
  }
  async renew() {
    const response = await fetch(
      `${providerOrigin}/realms/master/protocol/openid-connect/token`,
      {
        method: "POST",
        body: new URLSearchParams({
          grant_type: "password",
          client_id: "admin-cli",
          username: "portal-bootstrap",
          password: this.privateSecrets.AUTH_BOOTSTRAP_PASSWORD,
        }),
        signal: AbortSignal.timeout(5000),
      },
    );
    if (!response.ok)
      throw new Error("Project fixture authorization unavailable");
    const value = await response.json();
    this.bearer = value.access_token;
    if (value.refresh_token) this.grants.push(value.refresh_token);
  }
  async admin(path: string, options: RequestInit = {}) {
    let response = await fetch(`${providerOrigin}/admin/realms/${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${this.bearer}`,
        "Content-Type": "application/json",
      },
      signal: AbortSignal.timeout(5000),
    });
    if (response.status === 401) {
      await this.renew();
      response = await fetch(`${providerOrigin}/admin/realms/${path}`, {
        ...options,
        headers: {
          Authorization: `Bearer ${this.bearer}`,
          "Content-Type": "application/json",
        },
        signal: AbortSignal.timeout(5000),
      });
    }
    if (!response.ok)
      throw new Error(
        `Project fixture identity operation failed (${response.status})`,
      );
    return response;
  }
  async owned(identity = this.primary) {
    const value = await (
      await this.admin(`${realm}/users/${identity.id}`)
    ).json();
    const proof = JSON.parse(readFileSync(this.receiptPath, "utf8"));
    expect(
      proof.runId === this.runId &&
        [proof.userId, proof.secondaryUserId].includes(identity.id) &&
        value.id === identity.id &&
        value.username === identity.username &&
        value.email === `${identity.username}@example.invalid` &&
        value.attributes?.taskspaceAcceptanceRun?.[0] === this.runId &&
        identity.earliest - 1000 <= value.createdTimestamp &&
        value.createdTimestamp <= identity.latest + 1000,
    ).toBe(true);
    return value;
  }
  container(service: string) {
    const ids = execFileSync(
      "docker",
      [
        "ps",
        "-q",
        "--filter",
        "label=com.docker.compose.project=taskspace-portals-development",
        "--filter",
        `label=com.docker.compose.service=${service}`,
      ],
      { encoding: "utf8" },
    )
      .trim()
      .split(/\s+/);
    if (ids.length !== 1 || !/^[a-f0-9]{12,64}$/.test(ids[0]))
      throw new Error("Project fixture service ownership ambiguous");
    const item = JSON.parse(
      execFileSync("docker", ["inspect", ids[0]], { encoding: "utf8" }),
    )[0];
    if (
      item.Config.Labels["com.docker.compose.project"] !==
        "taskspace-portals-development" ||
      item.Config.Labels["com.docker.compose.service"] !== service ||
      item.State.Health.Status !== "healthy"
    )
      throw new Error("Project fixture service health/ownership mismatch");
    return ids[0];
  }
  people(action: string, value?: string) {
    return JSON.parse(
      execFileSync(
        "docker",
        [
          "exec",
          "-i",
          this.container("people"),
          "python",
          "-c",
          readFileSync(resolve("../../tests/account_entry/fixture.py"), "utf8"),
        ],
        {
          input: JSON.stringify({
            runId: this.runId,
            subject: this.primary.id,
            username: this.primary.username,
            action,
            value,
          }),
          encoding: "utf8",
        },
      ),
    );
  }
  work(action: "inspect" | "cleanup") {
    return JSON.parse(
      execFileSync(
        "docker",
        [
          "exec",
          "-i",
          this.container("project-work"),
          "python",
          "-c",
          readFileSync(resolve("../../tests/projects/fixture.py"), "utf8"),
        ],
        {
          input: JSON.stringify({ runId: this.runId, action }),
          encoding: "utf8",
        },
      ),
    );
  }
  async setup() {
    this.write("initializing");
    await this.renew();
    const admins = await (
      await this.admin("master/users?username=portal-bootstrap&exact=true")
    ).json();
    expect(admins.length).toBe(1);
    this.bootstrapId = admins[0].id;
    for (const identity of [this.primary, this.secondary]) {
      identity.earliest = Date.now();
      const response = await this.admin(`${realm}/users`, {
        method: "POST",
        body: JSON.stringify({
          username: identity.username,
          email: `${identity.username}@example.invalid`,
          emailVerified: true,
          firstName: identity === this.primary ? "Acceptance" : "Project",
          lastName: identity === this.primary ? "Account" : "Manager",
          enabled: true,
          attributes: { taskspaceAcceptanceRun: [this.runId] },
          credentials: [
            { type: "password", value: identity.password, temporary: false },
          ],
        }),
      });
      identity.latest = Date.now();
      identity.id = response.headers.get("location")?.split("/").pop() ?? "";
      expect(/^[0-9a-f-]{36}$/.test(identity.id)).toBe(true);
      this.write("identities-created");
      await this.owned(identity);
    }
    this.people("create");
    this.primaryAccountCreated = true;
    await this.owned(this.secondary);
    const secondary = this.people("project_other_create", this.secondary.id);
    expect(secondary.subject).toBe(this.secondary.id);
    this.secondaryAccountCreated = true;
    this.people("role", "ADMIN");
    this.write("ready");
  }
  async calendar(context: BrowserContext) {
    let workspace = await this.graphql(
      context,
      "{companyCalendar{current{id config{timezone week{weekday working opens closes} holidays{date label} exceptions{date label working opens closes}}}}}",
    );
    expect(workspace.errors).toBeUndefined();
    if (!workspace.data.companyCalendar.current) {
      const config = {
        timezone: "Etc/UTC",
        week: Array.from({ length: 7 }, (_, i) => ({
          weekday: i + 1,
          working: i < 5,
          opens: i < 5 ? "09:00" : null,
          closes: i < 5 ? "17:00" : null,
        })),
        holidays: [
          { date: "2099-12-31", label: `Project calendar ${this.runId}` },
        ],
        exceptions: [],
      };
      const preview = await this.graphql(
        context,
        "mutation($input:CalendarConfigurationInput!){previewCompanyCalendar(input:$input){previewId}}",
        { input: config },
      );
      expect(preview.errors).toBeUndefined();
      const published = await this.graphql(
        context,
        "mutation($input:PublishCalendarInput!){publishCompanyCalendar(input:$input){id}}",
        {
          input: {
            requestId: randomUUID(),
            previewId: preview.data.previewCompanyCalendar.previewId,
            confirm: true,
          },
        },
      );
      expect(published.errors).toBeUndefined();
      workspace = await this.graphql(
        context,
        "{companyCalendar{current{id config{timezone week{weekday working} holidays{date} exceptions{date working}}}}}",
      );
    }
    return workingDate(workspace.data.companyCalendar.current.config);
  }
  async login(page: Page, identity = this.primary) {
    await page.goto("/sign-in");
    await page
      .getByRole("button", { name: "Continue to sign in", exact: true })
      .click();
    await page.locator("#username").fill(identity.username);
    await page.locator("#password").fill(identity.password);
    await page.locator("#kc-login").click();
  }
  async token(context: BrowserContext, identity = this.primary) {
    const cookie = (await context.cookies(appOrigin)).find(
      (c) => c.name === "taskspace_session",
    );
    expect(Boolean(cookie)).toBe(true);
    const client = createClient({
      url: `redis://:${this.privateSecrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
    });
    client.on("error", () => {});
    await client.connect();
    try {
      const raw = await client.get(storageKey("session", cookie!.value));
      expect(Boolean(raw)).toBe(true);
      const record = JSON.parse(raw!);
      expect(record.subject === identity.id).toBe(true);
      return record.accessToken as string;
    } finally {
      await client.quit();
    }
  }
  async graphql(
    context: BrowserContext,
    query: string,
    variables: Record<string, unknown> = {},
    identity = this.primary,
  ) {
    const response = await context.request.post(
      "http://127.0.0.1:8020/graphql",
      {
        headers: {
          Authorization: `Bearer ${await this.token(context, identity)}`,
          "X-Actor-Role": "ADMIN",
        },
        data: { query, variables },
      },
    );
    expect(response.status()).toBe(200);
    return response.json();
  }
  async sessions(context: BrowserContext, identity = this.primary) {
    const client = createClient({
      url: `redis://:${this.privateSecrets.AUTH_REDIS_PASSWORD}@127.0.0.1:6381/0`,
    });
    client.on("error", () => {});
    await client.connect();
    try {
      for (const cookie of await context.cookies(appOrigin)) {
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
              ? record.subject === identity.id
              : record.createdAt >= identity.earliest &&
                  record.createdAt <= Date.now(),
          ).toBe(true);
          await client.del(key);
        }
        expect(await client.exists(key)).toBe(0);
      }
    } finally {
      await client.quit();
    }
  }
  diagnostic(error: unknown, project: string) {
    let message =
      error instanceof Error ? error.message : "Project boundary failed";
    for (const secret of [
      this.primary.password,
      this.secondary.password,
      ...Object.values(this.privateSecrets),
    ])
      message = message.split(secret).join("[private]");
    message = message
      .replace(/https?:\/\/[^\s<>]+/g, "[address omitted]")
      .slice(0, 2000);
    mkdirSync(resolve(`../../test-results/reports/${this.diagnosticScope}`), {
      recursive: true,
    });
    writeFileSync(
      resolve(
        `../../test-results/reports/${this.diagnosticScope}/${this.runId}-${randomUUID()}.json`,
      ),
      JSON.stringify({ stage: this.boundary, project, message }, null, 2),
    );
  }
  checkpoint(project: string) {
    mkdirSync(resolve(`../../test-results/reports/${this.diagnosticScope}`), {
      recursive: true,
    });
    writeFileSync(
      resolve(
        `../../test-results/reports/${this.diagnosticScope}/${this.runId}-boundary.json`,
      ),
      JSON.stringify({ stage: this.boundary, project }, null, 2),
    );
  }
  async cleanup() {
    let failure: unknown;
    let removed = false;
    let bootstrapPreserved = false;
    let grantsRevoked = true;
    let projectsCleaned = false;
    try {
      if (this.primary.id) {
        await this.owned();
        if (this.secondary.id) await this.owned(this.secondary);
        expect(this.work("cleanup").cleaned).toBe(true);
        const check = this.work("inspect");
        expect(
          check.projects === 0 &&
            check.previews === 0 &&
            check.versions === 0 &&
            check.calendarPreviews === 0 &&
            check.memberships === 0 &&
            check.membershipChanges === 0 &&
            check.coordinationRecords === 0 &&
            check.coordinationRecipients === 0 &&
            check.coordinationFollowUps === 0,
        ).toBe(true);
        projectsCleaned = true;
        if (!this.people("inspect").absent) {
          expect(this.people("project_other_cleanup").cleaned).toBe(true);
          expect(this.people("cleanup").cleaned).toBe(true);
        } else {
          expect(
            !this.primaryAccountCreated && !this.secondaryAccountCreated,
          ).toBe(true);
        }
        for (const identity of [this.secondary, this.primary]) {
          if (!identity.id) continue;
          await this.owned(identity);
          await this.admin(`${realm}/users/${identity.id}`, {
            method: "DELETE",
          });
          const response = await fetch(
            `${providerOrigin}/admin/realms/${realm}/users/${identity.id}`,
            { headers: { Authorization: `Bearer ${this.bearer}` } },
          );
          expect(response.status).toBe(404);
        }
        removed = true;
      }
      const admins = await (
        await this.admin("master/users?username=portal-bootstrap&exact=true")
      ).json();
      bootstrapPreserved =
        admins.length === 1 &&
        admins[0].id === this.bootstrapId &&
        admins[0].enabled;
      expect(bootstrapPreserved).toBe(true);
    } catch (error) {
      failure = error;
    } finally {
      for (const token of this.grants) {
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
            throw new Error("Project operator grant cleanup failed");
        } catch (error) {
          grantsRevoked = false;
          failure ??= error;
        }
      }
      this.write(
        !failure &&
          removed &&
          projectsCleaned &&
          bootstrapPreserved &&
          grantsRevoked
          ? "cleaned"
          : "blocked",
        {
          identityRemoved: removed,
          accountRemoved: removed,
          bootstrapPreserved,
          grantsRevoked,
          projectsCleanupVerified: projectsCleaned,
          membershipCleanupVerified: projectsCleaned,
          coordinationCleanupVerified: projectsCleaned,
          calendarCleanupVerified: projectsCleaned,
          organizationCleanupVerified: true,
        },
      );
    }
    if (failure) throw failure;
  }
}

export function workingDate(config: {
  week: { weekday: number; working: boolean }[];
  holidays: { date: string }[];
  exceptions: { date: string; working: boolean }[];
}) {
  const date = new Date("2030-01-07T00:00:00Z");
  for (let i = 0; i < 3660; i++) {
    const iso = date.toISOString().slice(0, 10);
    const exception = config.exceptions.find((r) => r.date === iso);
    const weekday = date.getUTCDay() || 7;
    const working = exception
      ? exception.working
      : !config.holidays.some((r) => r.date === iso) &&
        config.week.find((r) => r.weekday === weekday)?.working;
    if (working) return iso;
    date.setUTCDate(date.getUTCDate() + 1);
  }
  throw new Error("No eligible deadline in the tested calendar window");
}
