import { expect, test } from "@playwright/test";
import { getIsolatedRecoveryHelper } from "./isolated-recovery-helper";

test("real gateway container outage and recovery", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.RUN_DOCKER_RECOVERY !== "1" ||
      !process.env.DEV_USER_USERNAME ||
      !process.env.DEV_USER_PASSWORD ||
      testInfo.project.name !== "desktop",
    "Opt-in, isolated Docker recovery check",
  );
  test.setTimeout(90_000);

  const helper = getIsolatedRecoveryHelper();
  const baseURL = helper.getBaseUrl();
  const gatewayReadyUrl = new URL(
    "/health/ready",
    helper.getGatewayUrl(),
  ).toString();

  await page.goto("/system");
  await page.getByRole("link", { name: "Sign in" }).click();
  await page.locator("#username").fill(process.env.DEV_USER_USERNAME!);
  await page.locator("#password").fill(process.env.DEV_USER_PASSWORD!);
  await page.locator("#kc-login").click();
  await expect(page).toHaveURL(new URL("/system", baseURL).toString());
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();

  try {
    helper.stopService("gateway");
    await page.getByRole("button", { name: "Refresh status" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "Gateway unavailable",
      { timeout: 15_000 },
    );
    await expect(
      page.getByText("Gateway connected", { exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: testInfo.outputPath("gateway-outage.png"),
      fullPage: true,
    });
  } finally {
    helper.startService("gateway");
    await helper.waitForHealthy("gateway", 45_000).catch(() => undefined);
  }

  await expect
    .poll(async () => {
      try {
        return (await page.request.get(gatewayReadyUrl)).ok();
      } catch {
        return false;
      }
    })
    .toBe(true);
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { name: "Gateway is reachable" }),
  ).toBeVisible();
});
