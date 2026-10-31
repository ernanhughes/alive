import { test, expect } from "@playwright/test";

test("captured evidence retains separate validation statuses in the Observatory", async ({ page }) => {
  const run = process.env.ALIVE_VALIDATION_RUN;
  test.skip(!run, "Run tests/test_validation_browser.py on its disposable runtime");
  const app = process.env.ALIVE_BASE_URL!;
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith(app + "/api/") && request.method() !== "GET") writes.push(request.url());
  });
  await page.goto(`${app}/#workflows?workflow=pi03c-repository&version=1&run=${run}`);
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByRole("heading", { name: `Run ${run}` })).toBeVisible();
  await page.getByRole("button", { name: "Select record", exact: true }).click();
  await page.getByRole("tab", { name: "Evidence & result", exact: true }).click();
  await page.getByRole("button", { name: "Open retained artifact", exact: true }).click();
  const report = page.getByRole("region", { name: "Evidence report" });
  await expect(report).toContainText("Semantic support: unverified");
  await expect(report).toContainText("Independent verification: none");
  await expect(report).toContainText("Task outcome: unknown");
  await expect(report).toContainText("quote_matches");
  expect(writes).toEqual([]);
});
