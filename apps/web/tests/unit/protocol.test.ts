import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer } from "node:http";
import { generateKeyPairSync, sign } from "node:crypto";
import { provider, oidc } from "../../src/shared/auth/provider.ts";
const signing = generateKeyPairSync("rsa", { modulusLength: 2048 });
const other = generateKeyPairSync("rsa", { modulusLength: 2048 });
async function exchange(
  mode: "valid" | "signature" | "nonce" | "issuer" | "audience" | "expired",
) {
  let issuer = "";
  let keyRequests = 0;
  let verifierSeen = false;
  const verifier = oidc.randomPKCECodeVerifier();
  const server = createServer(async (request, response) => {
    response.setHeader("Content-Type", "application/json");
    if (request.url?.endsWith("/certs")) {
      keyRequests++;
      response.end(
        JSON.stringify({
          keys: [
            {
              ...signing.publicKey.export({ format: "jwk" }),
              kid: "protocol-test",
              alg: "RS256",
              use: "sig",
            },
          ],
        }),
      );
      return;
    }
    if (request.url?.endsWith("/token")) {
      let raw = "";
      for await (const chunk of request) raw += chunk;
      const form = new URLSearchParams(raw);
      verifierSeen =
        form.get("code_verifier") === verifier &&
        form.get("redirect_uri") === "http://127.0.0.1:3020/auth/callback";
      const claims = {
        iss:
          mode === "issuer"
            ? "https://untrusted.invalid/realms/taskspace-portals"
            : issuer,
        aud: mode === "audience" ? "another-client" : "taskspace-portals-web",
        sub: "protocol-subject",
        nonce: mode === "nonce" ? "wrong-nonce" : "expected-nonce",
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + (mode === "expired" ? -3600 : 300),
      };
      const input = [{ alg: "RS256", kid: "protocol-test" }, claims]
        .map((value) =>
          Buffer.from(JSON.stringify(value)).toString("base64url"),
        )
        .join(".");
      const signature = sign(
        "RSA-SHA256",
        Buffer.from(input),
        mode === "signature" ? other.privateKey : signing.privateKey,
      ).toString("base64url");
      response.end(
        JSON.stringify({
          access_token: "protocol-test-access",
          token_type: "Bearer",
          expires_in: 300,
          id_token: `${input}.${signature}`,
        }),
      );
      return;
    }
    response.statusCode = 404;
    response.end("{}");
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  issuer = `http://127.0.0.1:${address.port}/realms/taskspace-portals`;
  const old = {
    issuer: process.env.AUTH_ISSUER,
    internal: process.env.AUTH_INTERNAL_ISSUER,
    local: process.env.AUTH_ALLOW_LOCAL_HTTP,
  };
  process.env.AUTH_ISSUER = issuer;
  delete process.env.AUTH_INTERNAL_ISSUER;
  process.env.AUTH_ALLOW_LOCAL_HTTP = "true";
  try {
    const action = () =>
      oidc.authorizationCodeGrant(
        provider(),
        new URL(
          "http://127.0.0.1:3020/auth/callback?code=protocol-test-code&state=expected-state",
        ),
        {
          pkceCodeVerifier: verifier,
          expectedState: "expected-state",
          expectedNonce: "expected-nonce",
          idTokenExpected: true,
        },
      );
    if (mode === "valid") {
      const tokens = await action();
      assert.equal(tokens.claims()?.sub, "protocol-subject");
      assert.ok(keyRequests > 0);
    } else await assert.rejects(action());
    assert.equal(verifierSeen, true);
  } finally {
    for (const [name, value] of [
      ["AUTH_ISSUER", old.issuer],
      ["AUTH_INTERNAL_ISSUER", old.internal],
      ["AUTH_ALLOW_LOCAL_HTTP", old.local],
    ]) {
      if (value === undefined) delete process.env[name!];
      else process.env[name!] = value;
    }
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}
for (const mode of [
  "valid",
  "signature",
  "nonce",
  "issuer",
  "audience",
  "expired",
] as const) {
  test(
    mode === "valid"
      ? "valid signed OIDC response uses the provider JWKS and bound PKCE verifier"
      : `OIDC rejects ${mode} failure before authentication`,
    () => exchange(mode),
  );
}
