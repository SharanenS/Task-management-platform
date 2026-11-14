import * as oidc from "openid-client";

import { authConfig } from "@/auth/config";

let configuration: oidc.Configuration | undefined;

export class OidcUnavailableError extends Error {
  constructor() {
    super("Identity service unavailable");
    this.name = "OidcUnavailableError";
  }
}

export async function assertOidcAvailable(): Promise<void> {
  try {
    const response = await fetch(authConfig.discoveryEndpoint, {
      cache: "no-store",
      signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) throw new OidcUnavailableError();
  } catch (error) {
    if (error instanceof OidcUnavailableError) throw error;
    if (error instanceof TypeError || error instanceof DOMException)
      throw new OidcUnavailableError();
    throw error;
  }
}

export function getOidcConfiguration(): oidc.Configuration {
  if (!configuration) {
    configuration = new oidc.Configuration(
      {
        issuer: authConfig.issuer,
        authorization_endpoint: authConfig.authorizationEndpoint,
        token_endpoint: authConfig.tokenEndpoint,
        jwks_uri: authConfig.jwksUri,
        end_session_endpoint: authConfig.endSessionEndpoint,
        code_challenge_methods_supported: ["S256"],
        id_token_signing_alg_values_supported: ["RS256"],
      },
      authConfig.clientId,
      {
        redirect_uris: [
          new URL("/auth/callback", authConfig.appBaseUrl).toString(),
        ],
        response_types: ["code"],
        token_endpoint_auth_method: "none",
      },
      oidc.None(),
    );
    if (authConfig.allowInsecureLocalOidc) {
      const issuer = new URL(authConfig.issuer);
      if (
        issuer.protocol !== "http:" ||
        !["localhost", "127.0.0.1"].includes(issuer.hostname)
      )
        throw new Error(
          "Insecure OIDC is restricted to loopback development issuers.",
        );
      oidc.allowInsecureRequests(configuration);
    }
    configuration.timeout = 8;
  }
  return configuration;
}

export { oidc };
