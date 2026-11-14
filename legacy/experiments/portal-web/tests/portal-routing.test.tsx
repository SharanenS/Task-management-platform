import { render, screen } from "@testing-library/react";
import PortalLink, {
  PortalPathContext,
} from "@/components/portal-ui/portal-link";
import { describe, expect, it } from "vitest";
import {
  canOpenPortal,
  portalForRole,
  portalHome,
} from "@/features/portals/portal-policy";

describe("Portal access policy", () => {
  it.each([
    ["ADMIN", "admin"],
    ["MANAGER", "manager"],
    ["MEMBER", "employee"],
  ] as const)("maps %s to its own portal", (role, portal) => {
    expect(portalForRole(role)).toBe(portal);
    expect(portalHome(role)).toBe(`/portals/${portal}`);
    expect(canOpenPortal(role, portal)).toBe(true);
    for (const other of ["admin", "manager", "employee", "hr"])
      if (other !== portal) expect(canOpenPortal(role, other)).toBe(false);
  });
});

it("keeps domain navigation inside the selected portal", () => {
  render(
    <PortalPathContext.Provider value="/portals/employee">
      <PortalLink href="/projects/example?status=ACTIVE">Project</PortalLink>
      <PortalLink href="/auth/logout">Sign out</PortalLink>
      <PortalLink href="https://example.test">External</PortalLink>
    </PortalPathContext.Provider>,
  );
  expect(screen.getByText("Project")).toHaveAttribute(
    "href",
    "/portals/employee/projects/example?status=ACTIVE",
  );
  expect(screen.getByText("Sign out")).toHaveAttribute("href", "/auth/logout");
  expect(screen.getByText("External")).toHaveAttribute(
    "href",
    "https://example.test",
  );
});
