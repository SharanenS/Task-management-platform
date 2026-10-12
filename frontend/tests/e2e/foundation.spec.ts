import { test, expect } from "@playwright/test";
test("real GraphQL connection and responsive navigation", async ({
  page,
  isMobile,
}, testInfo) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Make room for great work." }),
  ).toBeVisible();
  await expect(
    page.getByText("Gateway connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("The overview below uses sample data", { exact: false }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("overview.png"),
    fullPage: true,
  });
  if (isMobile) {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(
      page.getByRole("dialog", { name: "Navigation" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Open navigation" }),
    ).toBeFocused();
    await page.getByRole("button", { name: "Open navigation" }).click();
  }
  await page.getByRole("link", { name: "System status", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
  await expect(
    page.getByText("Enterprise Task Platform Gateway", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("system.png"),
    fullPage: true,
  });
});
test("connection failure and recovery", async ({ page }) => {
  await page.goto("/system");
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
  await page.route("**/graphql", (route) => route.abort("failed"));
  await page.getByRole("button", { name: "Refresh status" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Gateway unavailable",
  );
  await expect(
    page.getByText("Gateway connected", { exact: true }),
  ).toHaveCount(0);
  await page.unroute("**/graphql");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
});
test("component state previews work", async ({ page }) => {
  await page.goto("/design-system");
  await page.getByRole("button", { name: "error", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "simulated error",
  );
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Ready to continue" }),
  ).toBeVisible();
});
