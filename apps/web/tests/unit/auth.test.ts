import assert from "node:assert/strict";
import { test } from "node:test";
import {
  consumeTransaction,
  identifier,
  readSession,
  returnPath,
  sameOrigin,
  sessionLifetime,
  storageKey,
  validIdentifier,
  type Store,
} from "../../src/shared/auth/policy.ts";

function memory() {
  const values = new Map<string, string>();
  const store: Store = {
    async put(k, v) {
      values.set(k, v);
    },
    async get(k) {
      return values.get(k) ?? null;
    },
    async take(k) {
      const v = values.get(k) ?? null;
      values.delete(k);
      return v;
    },
    async remove(k) {
      values.delete(k);
    },
  };
  return { store, values };
}
test("opaque identifiers reject attacker-controlled cookie values", () => {
  assert.ok(validIdentifier(identifier()));
  for (const value of [undefined, "", "../../key", "a".repeat(44)])
    assert.equal(validIdentifier(value), false);
  assert.throws(() => storageKey("session", "untrusted"));
});
test("store keys do not expose the browser session identifier", () => {
  const id = identifier();
  assert.ok(!storageKey("session", id).includes(id));
  assert.notEqual(storageKey("session", id), storageKey("transaction", id));
});
test("return destinations cannot escape the implemented authenticated page", () => {
  for (const path of [
    "https://evil.invalid",
    "//evil.invalid",
    "/\\evil.invalid",
    "/projects",
    "/portals/admin",
    "/auth/logout",
    "/auth/ready?next=evil",
    null,
  ])
    assert.equal(returnPath(path), "/auth/ready");
});
test("POST origin checks include the full scheme, host and port", () => {
  assert.equal(
    sameOrigin("http://127.0.0.1:3020", "http://127.0.0.1:3020"),
    true,
  );
  for (const origin of [
    null,
    "http://localhost:3020",
    "https://127.0.0.1:3020",
    "http://evil.invalid:3020",
  ])
    assert.equal(sameOrigin(origin, "http://127.0.0.1:3020"), false);
});
test("application lifetime never exceeds access-token or ID-token expiry", () => {
  assert.equal(sessionLifetime(300, 1100, 1000000), 100);
  assert.equal(sessionLifetime(3600, 9000, 1000000), 1800);
  assert.equal(sessionLifetime(300, 999, 1000000), 0);
});
test("valid transaction is consumed once even under replay", async () => {
  const { store } = memory();
  const id = identifier();
  await store.put(
    storageKey("transaction", id),
    JSON.stringify({
      state: "s",
      nonce: "n",
      verifier: "v",
      returnTo: "/auth/ready",
      createdAt: 1000,
    }),
    300,
  );
  assert.equal((await consumeTransaction(store, id, "s", 1001)).state, "s");
  await assert.rejects(consumeTransaction(store, id, "s", 1002));
});
test("wrong state consumes the transaction without authorizing a retry", async () => {
  const { store } = memory();
  const id = identifier();
  await store.put(
    storageKey("transaction", id),
    JSON.stringify({ state: "s", nonce: "n", verifier: "v", createdAt: 1000 }),
    300,
  );
  await assert.rejects(consumeTransaction(store, id, "wrong", 1001));
  await assert.rejects(consumeTransaction(store, id, "s", 1002));
});
test("expired and future-dated transactions fail closed", async () => {
  for (const createdAt of [0, 500000]) {
    const { store } = memory();
    const id = identifier();
    await store.put(
      storageKey("transaction", id),
      JSON.stringify({ state: "s", nonce: "n", verifier: "v", createdAt }),
      300,
    );
    await assert.rejects(consumeTransaction(store, id, "s", 300001));
  }
});
test("expired sessions are rejected and removed from storage", async () => {
  const { store, values } = memory();
  const id = identifier();
  await store.put(
    storageKey("session", id),
    JSON.stringify({
      subject: "u",
      displayName: "User",
      accessToken: "access",
      idToken: "id",
      expiresAt: 1000,
    }),
    10,
  );
  assert.equal(await readSession(store, id, 1001), null);
  assert.equal(values.size, 0);
});
test("malformed records cannot authenticate", async () => {
  for (const value of [
    "{",
    "{}",
    JSON.stringify({ subject: "u", expiresAt: Infinity }),
  ]) {
    const { store } = memory();
    const id = identifier();
    await store.put(storageKey("session", id), value, 10);
    assert.equal(await readSession(store, id), null);
  }
});
test("valid server session retains tokens on the server record", async () => {
  const { store } = memory();
  const id = identifier();
  await store.put(
    storageKey("session", id),
    JSON.stringify({
      subject: "u",
      displayName: "User",
      accessToken: "access",
      idToken: "id",
      expiresAt: 10000,
    }),
    10,
  );
  assert.equal((await readSession(store, id, 1000))?.subject, "u");
});
test("session-store failure is never replaced by an authenticated fallback", async () => {
  const { store } = memory();
  store.get = async () => {
    throw new Error("offline");
  };
  await assert.rejects(readSession(store, identifier()));
});
