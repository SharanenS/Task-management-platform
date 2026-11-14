export type ApplicationRole = "ADMIN" | "MANAGER" | "MEMBER";

export interface EmployeeProfile {
  id: string;
  displayName: string;
  email: string;
  role: ApplicationRole;
}

export interface SessionRecord {
  accessToken: string;
  refreshToken?: string;
  idToken?: string;
  accessTokenExpiresAt: number;
  refreshTokenExpiresAt?: number;
  csrfToken: string;
  employee: EmployeeProfile;
}

export interface AuthTransaction {
  state: string;
  nonce: string;
  codeVerifier: string;
  returnTo: string;
}
