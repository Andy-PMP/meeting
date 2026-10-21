// The privacy promise, enforced: pages make no requests to any other origin, and the CSP blocks
// nothing that ships (a violation shows up as a console error). P5 extends this to paste + rate.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PAGES = ["/", "/missing-page"];

function watch(page: Page, origin: string) {
  const foreign: string[] = [];
  const errors: string[] = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (url.protocol !== "data:" && url.protocol !== "blob:" && url.origin !== origin) foreign.push(req.url());
  });
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return { foreign, errors };
}

for (const path of PAGES) {
  test(`${path}: same-origin only, no CSP violations, no axe violations`, async ({ page, baseURL }) => {
    const { foreign, errors } = watch(page, new URL(baseURL!).origin);
    await page.goto(path);
    await page.waitForLoadState("networkidle");

    expect(foreign, "requests to other origins").toEqual([]);
    // The 404 page's own document request logs a "404" console error in Chromium; ignore only that.
    expect(errors.filter((e) => !/status of 404/.test(e)), "console errors").toEqual([]);

    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
}

test("theme toggle cycles and survives a reload", async ({ page }) => {
  await page.goto("/");
  const toggle = page.locator("#theme-toggle");
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
