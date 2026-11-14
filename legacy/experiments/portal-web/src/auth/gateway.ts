import { authConfig } from "@/auth/config";
import type { EmployeeProfile } from "@/auth/types";

const ME_QUERY = `query Me { me { id displayName email role } }`;

export class ProfileAccessDeniedError extends Error {}
export class ProfileUnavailableError extends Error {}

export async function fetchEmployeeProfile(
  accessToken: string,
): Promise<EmployeeProfile> {
  let response: Response;
  try {
    response = await fetch(`${authConfig.gatewayUrl}/graphql`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: ME_QUERY, operationName: "Me" }),
      cache: "no-store",
      signal: AbortSignal.timeout(8_000),
    });
  } catch (error) {
    throw new ProfileUnavailableError("Profile service unavailable", {
      cause: error,
    });
  }
  if (!response.ok) throw new ProfileUnavailableError();
  const result = (await response.json()) as {
    data?: { me?: EmployeeProfile };
    errors?: Array<{ extensions?: { code?: string } }>;
  };
  const code = result.errors?.[0]?.extensions?.code;
  if (code === "FORBIDDEN") throw new ProfileAccessDeniedError();
  if (!result.data?.me) throw new ProfileUnavailableError();
  return result.data.me;
}
