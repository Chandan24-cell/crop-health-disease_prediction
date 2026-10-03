import { expect, test } from "@playwright/test";

test.use({
  launchOptions: {
    args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
  },
});

test("camera stream can capture, preview, rotate, and clear a leaf", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/#/scan");
  await page.locator("#start-camera").click();
  await expect(page.locator("#capture-photo")).toBeVisible({ timeout: 15_000 });

  await page.locator("#capture-photo").click();
  await expect(page.locator("#selected-preview")).toBeVisible();
  await expect(page.locator("#analyze-photo")).toBeEnabled();
  await page.locator("#rotate-photo").click();
  await expect(page.locator("#selected-preview")).toHaveAttribute("style", /rotate\(90deg\)/);

  await page.locator("#clear-photo").click();
  await expect(page.locator("#selected-preview")).toBeHidden();
  await expect(page.locator("#capture-photo")).toBeHidden();
  await expect(page.locator("#analyze-photo")).toBeDisabled();
  expect(pageErrors).toEqual([]);
});
