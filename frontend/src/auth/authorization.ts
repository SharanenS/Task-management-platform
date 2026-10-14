import type { ApplicationRole } from "@/auth/types";

export function canViewEmployeeNavigation(role: ApplicationRole): boolean {
  return role === "ADMIN";
}
