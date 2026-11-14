import type { ApplicationRole } from "@/auth/types";

export type PortalKind = "admin" | "manager" | "employee";

export function portalForRole(role: ApplicationRole): PortalKind {
  switch (role) {
    case "ADMIN":
      return "admin";
    case "MANAGER":
      return "manager";
    case "MEMBER":
      return "employee";
    default:
      throw new Error("Unsupported application role.");
  }
}

export function portalHome(role: ApplicationRole) {
  return `/portals/${portalForRole(role)}`;
}

export function canOpenPortal(role: ApplicationRole, portal: string) {
  return portalForRole(role) === portal;
}
