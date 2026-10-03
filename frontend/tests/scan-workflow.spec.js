import { expect, test } from "@playwright/test";
import { fileURLToPath, URL } from "node:url";

const healthyLeaf = fileURLToPath(new URL("../../demo_images/2_healthy_maize.jpg", import.meta.url));
const diseasedLeaf = fileURLToPath(new URL("../../demo_images/1_diseased_tomato.jpg", import.meta.url));

test("scan upload controls reset safely and analyze twice after refresh", async ({ page }) => {
  test.setTimeout(180_000);
  const pageErrors = [];
  const consoleErrors = [];
  const predictionStatuses = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (/\/api\/v1\/predict$/.test(response.url())) predictionStatuses.push(response.status());
  });

  await page.goto("/#/scan");
  await page.reload();
  const analyze = page.locator("#analyze-photo");
  const fileInput = page.locator("#leaf-file");
  const currentImageUrl = () =>
    page.evaluate(async () => (await import("/js/state.js")).state.currentImageUrl);
  await expect(analyze).toBeDisabled();
  await expect(fileInput).toHaveValue("");

  await page.locator("#crop-choice").selectOption("Maize");
  await page.locator("#plant-id").fill("North plot, plant 4");
  await page.locator("#zoom-range").evaluate((element) => {
    element.value = "1.5";
    element.dispatchEvent(new element.ownerDocument.defaultView.Event("input", { bubbles: true }));
  });
  await expect(page.locator("#zoom-range")).toHaveValue("1.5");
  await fileInput.setInputFiles(healthyLeaf);
  await expect(page.locator("#selected-preview")).toBeVisible();
  await expect.poll(currentImageUrl).not.toBeNull();
  await expect(analyze).toBeEnabled();
  await expect(page.locator("#crop-choice")).toHaveValue("Maize");
  await expect(page.locator("#plant-id")).toHaveValue("North plot, plant 4");
  await expect(page.locator("#zoom-range")).toHaveValue("1");

  await page.locator("#rotate-photo").click();
  await expect(page.locator("#selected-preview")).toHaveAttribute("style", /rotate\(90deg\)/);
  await page.locator("#clear-photo").click();
  await expect(fileInput).toHaveValue("");
  await expect(page.locator("#selected-preview")).toBeHidden();
  await expect.poll(currentImageUrl).toBeNull();
  await expect(page.locator("#zoom-range")).toHaveValue("1");
  await expect(analyze).toBeDisabled();

  const scanAndVerify = async (imagePath, crop, plantLabel) => {
    await page.locator("#crop-choice").selectOption(crop);
    await page.locator("#plant-id").fill(plantLabel);
    await fileInput.setInputFiles(imagePath);
    await expect(page.locator("#selected-preview")).toBeVisible();
    const prediction = page.waitForResponse(
      (response) => response.url().endsWith("/api/v1/predict") && response.request().method() === "POST",
    );
    await analyze.click();
    const response = await prediction;
    expect(response.status()).toBe(200);
    const payload = await response.json();
    expect(Array.isArray(payload.top3)).toBe(true);
    await expect(page).toHaveURL(/#\/results$/, { timeout: 90_000 });
    await expect(page.locator("#main-content h1").first()).toBeVisible();
    expect(predictionStatuses.at(-1)).toBe(200);
    await page.goto("/#/scan");
  };

  await scanAndVerify(diseasedLeaf, "Tomato", "South plot, plant 9");
  await scanAndVerify(healthyLeaf, "Maize", "North plot, plant 4");

  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test("clear invalidates an in-flight file read", async ({ page }) => {
  await page.addInitScript(`
    const readAsDataURL = globalThis.FileReader.prototype.readAsDataURL;
    globalThis.FileReader.prototype.readAsDataURL = function (file) {
      globalThis.setTimeout(() => readAsDataURL.call(this, file), 1200);
    };
  `);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/#/scan");
  await page.locator("#leaf-file").setInputFiles(diseasedLeaf);
  await expect(page.locator("#selected-preview")).toBeVisible();
  await page.locator("#clear-photo").click();
  await expect(page.locator("#selected-preview")).toBeHidden();
  await page.waitForTimeout(1300);
  const currentImageUrl = await page.evaluate(
    async () => (await import("/js/state.js")).state.currentImageUrl,
  );
  expect(currentImageUrl).toBeNull();
  expect(pageErrors).toEqual([]);
});
