import { expect, test } from "@playwright/test";

test("a failed page import shows a retry view and can recover", async ({ page }) => {
  const moduleUrl = /\/js\/pages\/limitations\.js/;
  await page.route(moduleUrl, (route) => route.abort());
  await page.goto("/#/safety");

  const retry = page.locator("[data-route-retry]");
  await expect(retry).toBeVisible();
  await expect(page.locator("#main-content")).toContainText("./pages/limitations.js");

  await page.unroute(moduleUrl);
  await retry.click();
  await expect(page.locator("h1").first()).toContainText("Limitations & Responsible Use");
});
