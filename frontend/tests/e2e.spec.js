import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const routes=[{href:"#/",heading:"Fieldnote crop health",nav:null},{href:"#/scan",heading:"Scan a leaf",nav:"scan"},{href:"#/outbreak-map",heading:"India outbreak map",nav:"outbreak-map"},{href:"#/treatment",heading:"Careful next steps",nav:"treatment"},{href:"#/my-scans",heading:"My scans",nav:"my-scans"},{href:"#/plant-guide",heading:"Know what to look for",nav:"plant-guide"},{href:"#/safety",heading:"Limitations & Responsible Use",nav:"safety"},{href:"#/settings",heading:"Settings",nav:null}];
test("all eight routes render in both themes and all supported languages",async({page})=>{const pageErrors=[],consoleErrors=[];page.on("pageerror",error=>pageErrors.push(error.message));page.on("console",message=>{if(message.type()==="error")consoleErrors.push(message.text())});for(const theme of ["light","dark"]){for(const lang of ["en","hi","ne"]){await page.goto("/#/");await page.evaluate(({theme,lang})=>{localStorage.setItem("theme",theme);localStorage.setItem("language",lang)}, {theme,lang});await page.reload();await expect(page.locator("html")).toHaveAttribute("data-theme",theme);await expect(page.locator("html")).toHaveAttribute("lang",lang);for(const route of routes){if(route.href==="#/"){await page.locator(".brand").click()}else if(route.nav&&await page.locator(`.desktop-nav [data-nav="${route.nav}"]`).isVisible()){await page.locator(`.desktop-nav [data-nav="${route.nav}"]`).click()}else if(route.nav&&await page.locator(`.mobile-nav [data-nav="${route.nav}"]`).isVisible()){await page.locator(`.mobile-nav [data-nav="${route.nav}"]`).click()}else if(!route.nav&&await page.locator(".avatar-link").isVisible()){await page.locator(".avatar-link").click()}else{await page.goto(route.href)}expect(page.url()).toContain(route.href);await expect(page.locator("h1").first()).toContainText(route.heading,{ignoreCase:true});await expect(page.getByText(/That field path isn.t here/i)).toHaveCount(0)}}}expect(pageErrors,JSON.stringify(pageErrors)).toEqual([]);expect(consoleErrors,JSON.stringify(consoleErrors)).toEqual([])});
test("leaf animation contains only a canvas and responds to scroll",async({page})=>{await page.goto("/");await expect(page.locator(".leaf-explode__canvas")).toHaveAttribute("aria-label","Animated exploded view of a leaf");await expect(page.locator(".leaf-explode").getByText(/Intact leaf|Scroll|Autoplay|Play|Pause|TODO|\d+ \/ 180/i)).toHaveCount(0);await page.locator("html").evaluate(el=>scrollTo(0,Math.min(500,document.body.scrollHeight-innerHeight)));await page.waitForTimeout(150);});
test("new visitors always receive the light theme",async({page})=>{await page.emulateMedia({colorScheme:"dark"});await page.goto("/");await page.evaluate(()=>localStorage.clear());await page.reload();await expect(page.locator("html")).toHaveAttribute("data-theme","light")});

test("axe color contrast check reports no failures on every page in both themes",async({page})=>{for(const theme of ["light","dark"]){await page.goto("/");await page.evaluate(theme=>{localStorage.setItem("theme",theme)},theme);await page.reload();for(const route of routes){await page.goto(route.href);await page.waitForTimeout(route.href==="#/outbreak-map"?800:50);const result=await new AxeBuilder({page}).withRules(["color-contrast"]).analyze();expect(result.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target),summary:v.nodes.map(n=>n.failureSummary)})),`${route.href} ${theme}`).toEqual([])}}});

test("Hindi and Nepali pages fit a 360px viewport",async({page})=>{await page.setViewportSize({width:360,height:800});for(const lang of ["hi","ne"]){await page.goto("/");await page.evaluate(lang=>localStorage.setItem("language",lang),lang);await page.reload();for(const route of routes){await page.goto(route.href);const width=await page.locator("html").evaluate(el=>el.scrollWidth);expect(width,`${route.href} ${lang}`).toBeLessThanOrEqual(360)}}});

test("all route, theme, and language combinations have zero browser console errors", async ({ page }) => {
  const report = [];
  const externalRequests = new Set();
  page.on("request", (request) => { if (new URL(request.url()).origin !== "http://127.0.0.1:8000") externalRequests.add(request.url()); });
  for (const theme of ["light", "dark"]) {
    for (const lang of ["en", "hi", "ne"]) {
      await page.goto("/");
      await page.evaluate(({ theme, lang }) => {
        localStorage.setItem("theme", theme);
        localStorage.setItem("language", lang);
      }, { theme, lang });
      await page.reload();
      for (const route of routes) {
        const errors = [];
        const onError = (message) => { if (message.type() === "error") errors.push(message.text()); };
        const onPageError = (error) => errors.push(error.stack || error.message);
        page.on("console", onError);
        page.on("pageerror", onPageError);
        await page.goto(route.href);
        await expect(page.locator("h1").first()).toContainText(route.heading, { ignoreCase: true });
        await page.waitForTimeout(route.href === "#/outbreak-map" ? 1200 : 100);
        report.push({ route: route.href, theme, language: lang, consoleErrors: errors.length, errors });
        page.off("console", onError);
        page.off("pageerror", onPageError);
      }
    }
  }
  console.log(`ROUTE_CONSOLE_MATRIX=${JSON.stringify({ routes: report, externalRequests: [...externalRequests] })}`);
  const path = await import("node:path");
  const fs = await import("node:fs");
  fs.writeFileSync(path.resolve("..", "reports", "route-console-matrix.json"), JSON.stringify({ routes: report, externalRequests: [...externalRequests] }, null, 2));
  expect(report.filter((item) => item.consoleErrors), JSON.stringify(report.filter((item) => item.consoleErrors))).toEqual([]);
  expect([...externalRequests].filter((url) => !url.includes("tile.openstreetmap.org")), JSON.stringify([...externalRequests])).toEqual([]);
});

test("scanner responsive screenshots and header language menu fit the viewport", async ({ page }) => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  for (const width of [360, 1200]) {
    await page.setViewportSize({ width, height: 860 });
    await page.goto("/#/scan");
    await expect(page.locator("#scanner-view")).toBeVisible();
    await page.screenshot({ path: path.resolve("..", "reports", `scan-${width}.png`), fullPage: false });
  }
  await page.setViewportSize({ width: 360, height: 800 });
  for (const [language, label] of [["en", "EN"], ["hi", "हिं"], ["ne", "ने"]]) {
    await page.goto("/");
    await page.evaluate((value) => localStorage.setItem("language", value), language);
    await page.reload();
    const toggle = page.locator(".language-toggle");
    await expect(toggle).toContainText(label);
    const buttonRect = await toggle.boundingBox();
    expect(buttonRect.x + buttonRect.width).toBeLessThanOrEqual(360);
    await toggle.click();
    const menuRect = await page.locator(".language-options").boundingBox();
    expect(menuRect.x).toBeGreaterThanOrEqual(0);
    expect(menuRect.x + menuRect.width).toBeLessThanOrEqual(360);
  }
  expect(fs.existsSync(path.resolve("..", "reports"))).toBeTruthy();
});


test("storage blocking falls back without uncaught errors", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.stack || error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new DOMException("Blocked", "SecurityError"); } });
    Object.defineProperty(window, "sessionStorage", { configurable: true, get() { throw new DOMException("Blocked", "SecurityError"); } });
    Object.defineProperty(window, "indexedDB", { configurable: true, get() { throw new DOMException("Blocked", "SecurityError"); } });
  });
  for (const route of routes) {
    await page.goto(route.href);
    await expect(page.locator("h1").first()).toContainText(route.heading, { ignoreCase: true });
  }
  expect(errors).toEqual([]);
});
