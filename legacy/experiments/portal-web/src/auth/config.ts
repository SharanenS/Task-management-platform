const publicIssuer =
  process.env.OIDC_ISSUER ?? "http://localhost:8080/realms/taskspace";
const internalBaseUrl =
  process.env.OIDC_INTERNAL_BASE_URL ?? "http://localhost:8080";
const realm = new URL(publicIssuer).pathname.split("/").filter(Boolean).at(-1);

if (!realm) throw new Error("OIDC_ISSUER must identify a realm.");

export const authConfig = {
  appBaseUrl: new URL(process.env.APP_BASE_URL ?? "http://localhost:3010"),
  clientId: process.env.OIDC_CLIENT_ID ?? "taskspace-web",
  issuer: publicIssuer,
  authorizationEndpoint: `${publicIssuer}/protocol/openid-connect/auth`,
  endSessionEndpoint: `${publicIssuer}/protocol/openid-connect/logout`,
  tokenEndpoint: `${internalBaseUrl}/realms/${realm}/protocol/openid-connect/token`,
  jwksUri: `${internalBaseUrl}/realms/${realm}/protocol/openid-connect/certs`,
  discoveryEndpoint: `${internalBaseUrl}/realms/${realm}/.well-known/openid-configuration`,
  gatewayUrl: process.env.GATEWAY_URL ?? "http://127.0.0.1:8010",
  secureCookies:
    new URL(process.env.APP_BASE_URL ?? "http://localhost:3010").protocol ===
    "https:",
  allowInsecureLocalOidc:
    process.env.OIDC_ALLOW_INSECURE_LOCAL === "true" ||
    process.env.NODE_ENV === "test",
};

export const SESSION_COOKIE = "taskspace.session";
export const CSRF_COOKIE = "taskspace.csrf";
export const TRANSACTION_COOKIE = "taskspace.auth-transaction";
