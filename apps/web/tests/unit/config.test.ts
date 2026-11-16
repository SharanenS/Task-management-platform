import assert from "node:assert/strict";
import { test } from "node:test";
import { authConfig } from "../../src/shared/auth/config.ts";
const names = [
  "AUTH_APP_URL",
  "AUTH_ISSUER",
  "AUTH_INTERNAL_ISSUER",
  "AUTH_ALLOW_LOCAL_HTTP",
];
function withEnv(values: Record<string, string | undefined>, body: () => void) {
  const previous = Object.fromEntries(
    names.map((name) => [name, process.env[name]]),
  );
  try {
    for (const name of names) delete process.env[name];
    Object.assign(process.env, values);
    body();
  } finally {
    for (const name of names) {
      if (previous[name] === undefined) delete process.env[name];
      else process.env[name] = previous[name];
    }
  }
}
test("plain HTTP requires explicit loopback-only development opt-in", () => {
  withEnv({}, () => assert.throws(authConfig));
  withEnv({ AUTH_ALLOW_LOCAL_HTTP: "true" }, () =>
    assert.equal(authConfig().secure, false),
  );
  withEnv(
    { AUTH_ALLOW_LOCAL_HTTP: "true", AUTH_APP_URL: "http://external.invalid" },
    () => assert.throws(authConfig),
  );
});
test("HTTPS uses host-prefixed secure cookie names", () => {
  withEnv(
    {
      AUTH_APP_URL: "https://app.example.invalid",
      AUTH_ISSUER: "https://identity.example.invalid/realms/taskspace-portals",
    },
    () => {
      assert.equal(authConfig().secure, true);
      assert.equal(authConfig().sessionCookie, "__Host-taskspace_session");
    },
  );
});
test("issuer path, credentials and internal origin cannot escape the configured boundary", () => {
  for (const values of [
    { AUTH_ISSUER: "http://127.0.0.1:8180/realms/other" },
    { AUTH_APP_URL: "http://user:private@127.0.0.1:3020" },
    { AUTH_INTERNAL_ISSUER: "http://untrusted:8080/realms/taskspace-portals" },
    {
      AUTH_ISSUER:
        "http://127.0.0.1:8180/realms/taskspace-portals?code=private",
    },
  ]) {
    withEnv({ AUTH_ALLOW_LOCAL_HTTP: "true", ...values }, () =>
      assert.throws(authConfig),
    );
  }
});
