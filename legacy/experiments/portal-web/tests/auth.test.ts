import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { safeReturnPath } from "@/auth/return-path";
import { canViewEmployeeNavigation } from "@/auth/authorization";

describe("authentication boundaries", () => {
  it.each([
    ["/", "/"],
    ["/system?view=health", "/system?view=health"],
    ["https://attacker.example/path", "/"],
    ["//attacker.example/path", "/"],
    ["javascript:alert(1)", "/"],
    [undefined, "/"],
  ])("constrains the post-login return path", (input, expected) => {
    expect(safeReturnPath(input)).toBe(expected);
  });

  it("keeps tokens out of browser storage APIs", () => {
    const sourceRoot = join(process.cwd(), "src");
    const files = [
      "auth/session.ts",
      "app/auth/callback/route.ts",
      "app/graphql/route.ts",
      "components/layout/user-menu.tsx",
    ];
    const source = files
      .map((file) => readFileSync(join(sourceRoot, file), "utf8"))
      .join("\n");
    expect(source).not.toMatch(/localStorage|sessionStorage/);
  });

  it.each([
    ["ADMIN", true],
    ["MANAGER", false],
    ["MEMBER", false],
  ] as const)(
    "renders employee navigation for %s appropriately",
    (role, expected) => {
      expect(canViewEmployeeNavigation(role)).toBe(expected);
    },
  );
});
