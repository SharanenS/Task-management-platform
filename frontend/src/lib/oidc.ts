import * as client from "openid-client";
import { getSession } from "./session";

let configPromise: Promise<client.Configuration> | null = null;

export function setOidcConfigForTesting(config: client.Configuration | null) {
  configPromise = config ? Promise.resolve(config) : null;
}

export async function getOidcConfig(): Promise<client.Configuration> {
  if (!configPromise) {
    const issuer =
      process.env.KEYCLOAK_ISSUER || "http://localhost:8080/realms/enterprise";
    const clientId = process.env.KEYCLOAK_CLIENT_ID || "task-platform";
    const clientSecret = process.env.KEYCLOAK_CLIENT_SECRET;

    if (!clientSecret || !clientSecret.trim()) {
      throw new Error(
        "KEYCLOAK_CLIENT_SECRET environment variable is missing. It must be configured for server-side OIDC authentication."
      );
    }

    const issuerUrl = new URL(issuer);
    const isHttp = issuerUrl.protocol === "http:";

    configPromise = (async () => {
      const discovered = await client.discovery(
        issuerUrl,
        clientId,
        clientSecret.trim(),
        undefined,
        isHttp ? { execute: [client.allowInsecureRequests] } : undefined
      );

      if (process.env.KEYCLOAK_BROWSER_URL) {
        const browserBase = process.env.KEYCLOAK_BROWSER_URL.replace(/\/$/, "");
        const meta = { ...discovered.serverMetadata() };
        meta.issuer = `${browserBase}/realms/enterprise`;
        if (meta.authorization_endpoint) {
          const u = new URL(meta.authorization_endpoint);
          const b = new URL(browserBase);
          u.protocol = b.protocol;
          u.hostname = b.hostname;
          u.port = b.port;
          meta.authorization_endpoint = u.toString();
        }
        if (meta.end_session_endpoint) {
          const u = new URL(meta.end_session_endpoint);
          const b = new URL(browserBase);
          u.protocol = b.protocol;
          u.hostname = b.hostname;
          u.port = b.port;
          meta.end_session_endpoint = u.toString();
        }
        const config = new client.Configuration(meta, clientId, clientSecret.trim());
        if (isHttp) {
          client.allowInsecureRequests(config);
        }
        return config;
      }

      return discovered;
    })();
  }
  return configPromise;
}

interface InFlightRefreshResult {
  accessToken: string;
  refreshToken?: string;
  expiresIn?: number;
}

// In-flight refresh deduplication map.
// Keyed by the current session's refresh token so concurrent requests from the
// SAME user session await the same single Keycloak token refresh grant call.
// Different users have different refresh tokens, preventing cross-user token leaks.
// Entries are cleared as soon as the refresh promise settles.
const inFlightRefreshes = new Map<string, Promise<InFlightRefreshResult | null>>();

export function getInFlightRefreshesCount(): number {
  return inFlightRefreshes.size;
}

/**
 * Returns a valid access token for the current session.
 * If the current access token is expired or within 30 seconds of expiry,
 * attempts to refresh it using the refresh token.
 * Returns null if unauthenticated or refresh fails.
 */
export async function getValidAccessToken(): Promise<string | null> {
  const session = await getSession();

  if (!session.accessToken) {
    return null;
  }

  const now = Math.floor(Date.now() / 1000);
  const expiresAt = session.expiresAt || 0;

  // If token is still valid with a 30-second buffer, return it
  if (expiresAt > now + 30) {
    return session.accessToken;
  }

  // If expired or expiring soon, try refreshing
  if (!session.refreshToken) {
    return null;
  }

  const currentRefreshToken = session.refreshToken;

  let refreshPromise = inFlightRefreshes.get(currentRefreshToken);
  if (!refreshPromise) {
    refreshPromise = (async (): Promise<InFlightRefreshResult | null> => {
      try {
        const config = await getOidcConfig();
        const tokenResponse = await client.refreshTokenGrant(
          config,
          currentRefreshToken
        );
        return {
          accessToken: tokenResponse.access_token,
          refreshToken: tokenResponse.refresh_token,
          expiresIn: tokenResponse.expires_in,
        };
      } catch (error) {
        console.error("Failed to refresh access token:", error);
        return null;
      }
    })().finally(() => {
      inFlightRefreshes.delete(currentRefreshToken);
    });

    inFlightRefreshes.set(currentRefreshToken, refreshPromise);
  }

  const result = await refreshPromise;

  if (!result) {
    try {
      session.destroy();
    } catch {
      // Ignore destroy errors if response is already streaming
    }
    return null;
  }

  session.accessToken = result.accessToken;
  if (result.refreshToken) {
    session.refreshToken = result.refreshToken;
  }
  if (result.expiresIn) {
    session.expiresAt = now + result.expiresIn;
  }
  // Note: idToken is intentionally NOT stored — see callback/route.ts comment

  await session.save();
  return session.accessToken;
}
