import "server-only";
import * as oidc from "openid-client";
import { authConfig } from "./config.ts";

export function provider() {
  const c = authConfig();
  const base = `${c.internalIssuer}/protocol/openid-connect`;
  const config = new oidc.Configuration(
    {
      issuer: c.issuer,
      authorization_endpoint: `${c.issuer}/protocol/openid-connect/auth`,
      token_endpoint: `${base}/token`,
      jwks_uri: `${base}/certs`,
      end_session_endpoint: `${c.issuer}/protocol/openid-connect/logout`,
      code_challenge_methods_supported: ["S256"],
      id_token_signing_alg_values_supported: ["RS256"],
    },
    c.clientId,
    {
      token_endpoint_auth_method: "none",
      id_token_signed_response_alg: "RS256",
    },
    oidc.None(),
  );
  if (c.issuer.startsWith("http:")) oidc.allowInsecureRequests(config);
  oidc.enableNonRepudiationChecks(config);
  config.timeout = 5;
  return config;
}
export async function checkProvider() {
  const c = authConfig();
  const response = await fetch(
    `${c.internalIssuer}/.well-known/openid-configuration`,
    { cache: "no-store", signal: AbortSignal.timeout(5000) },
  );
  if (!response.ok) throw new Error("Identity provider unavailable");
  const metadata = await response.json();
  if (metadata.issuer !== c.issuer)
    throw new Error("Identity provider boundary mismatch");
}
export { oidc };
