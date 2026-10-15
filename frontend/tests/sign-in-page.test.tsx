import { render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({
    children,
    prefetch,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: ReactNode;
    prefetch?: boolean;
  }) => (
    <a {...props} data-prefetch={String(prefetch)}>
      {children}
    </a>
  ),
}));

import SignInPage from "@/app/sign-in/page";

describe("sign-in page", () => {
  it("does not prefetch the state-changing authentication initiation route", async () => {
    render(
      await SignInPage({
        searchParams: Promise.resolve({ returnTo: "/projects" }),
      }),
    );

    const link = screen.getByRole("link", { name: "Sign in" });
    expect(link).toHaveAttribute("href", "/auth/login?returnTo=%2Fprojects");
    expect(link).toHaveAttribute("data-prefetch", "false");
  });
});
