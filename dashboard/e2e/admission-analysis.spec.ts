import { test, expect } from "@playwright/test";

test("owner-approved analysis executes and opens its real report", async ({ page }) => {
  const review = process.env.ALIVE_ANALYSIS_REVIEW_ID;
  test.skip(!review, "Run the disposable tests/test_analysis_browser.py harness");
  const app = process.env.ALIVE_BASE_URL!;
  await page.goto(`${app}/#admission?id=${review}`);
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(page.getByText("Disclosure to the model provider")).toBeVisible();
  await expect(page.getByText(/https:\/\/.+chat\/completions/)).toBeVisible();
  const start = page.getByRole("button", { name: "Start approved inspection", exact: true });
  await expect(start).toBeEnabled();
  const completed = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/admissions/${review}/start`) &&
    response.request().method() === "POST",
  );
  await start.click();
  const response = await completed;
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).run.status).toBe("COMPLETED");
  await expect(page.getByText("Analysis report", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Analysis report" }).locator("p"))
    .toContainText("Independent verification: none");
  await expect(page.locator("pre.admission-report")).toContainText("Mean divides by the wrong count");
  await page.reload();
  await expect(page.getByText("Analysis report", { exact: true })).toBeVisible();
});
