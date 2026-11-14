import { expect, test } from "@playwright/test";

test.skip(
  process.env.RUN_PORTAL_E2E !== "1" ||
    !process.env.DEV_USER_USERNAME ||
    !process.env.DEV_USER_PASSWORD,
  "Portal acceptance needs the local development identity.",
);

test("signed-in workspace uses only portal routes", async ({ page }, info) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/portals/admin");
  await expect(
    page.getByRole("heading", { name: "Your organisation, in focus." }),
  ).toBeVisible();
  await expect(page.getByText("Sample data", { exact: false })).toHaveCount(0);
  await expect(
    page.getByText("Development workspace", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Overview unavailable", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Loading workspace dashboard", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Project portfolio", { exact: true }),
  ).toBeVisible();

  const mobile = await page
    .getByRole("button", { name: "Open navigation" })
    .isVisible();
  if (mobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(
      page.getByRole("dialog", { name: "Navigation" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Open navigation" }),
    ).toBeFocused();
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("portal-overview.png"),
    fullPage: true,
  });

  await page.goto("/projects?status=ACTIVE");
  await expect
    .poll(() => new URL(page.url()).pathname)
    .toBe("/portals/admin/projects");
  expect(new URL(page.url()).searchParams.get("status")).toBe("ACTIVE");
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible();
  await page.goto("/design-system");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/portals/admin");
  await page.goto("/portals/manager");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/access-denied");
  await page.goto("/portals/admin");
  await page.getByRole("button", { name: /Local User ADMIN/ }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/signed-out");
  await page.goto("/portals/admin");
  await expect.poll(() => new URL(page.url()).pathname).toBe("/sign-in");
});
