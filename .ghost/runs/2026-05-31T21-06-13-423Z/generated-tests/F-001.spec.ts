import { test, expect } from "@playwright/test";

test("F-001 locator.waitFor: Error: strict mode violation: getByText('Overview') resolved to 3 elem...", async ({ page }) => {
  const baseURL = process.env.GHOST_BASE_URL ?? "http://127.0.0.1:8876";
  await page.goto(new URL("/", baseURL).toString());
  await expect(page.locator("body")).toBeVisible();
  throw new Error("Recreate F-001 with the reproduction steps before turning this into a narrower assertion.");
});

