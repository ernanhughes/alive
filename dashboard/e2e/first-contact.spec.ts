import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
test("dashboard renders persisted data, errors, agent progress and browser controls", async ({
  page,
}) => {
  const token =
    process.env.ALIVE_API_TOKEN ||
    fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  await page.addInitScript(
    (token) => sessionStorage.setItem("alive-token", token),
    token,
  );
  await page.goto("/");
  await expect(page.locator(".connection")).toContainText("Backend connected");
  await expect(
    page.getByRole("heading", { name: "Something is becoming." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Live events", exact: false }).click();
  await expect(page.getByText("Persisted event timeline")).toBeVisible();
  await expect(page.locator(".events details").first()).toBeVisible();
  await page.getByRole("button", { name: "Memory", exact: true }).click();
  await page.getByLabel("Search memories").fill("green");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("postgresql_fts", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Agents", exact: true }).click();
  const runner = process.env.ALIVE_E2E_RUNNER || "mock";
  if (runner === "pi") test.setTimeout(150000);
  await page.getByLabel("Runner", { exact: true }).selectOption(runner);
  await page
    .getByLabel("Objective")
    .fill("Examine the green light from the dashboard");
  const runResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/agents/runs") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  const runId = (await (await runResponse).json()).id;
  const runRow = page.locator(`[data-run-id="${runId}"]`);
  if (runner === "mock")
    await expect(runRow.locator("pre")).toContainText("Observation examined");
  else {
    await expect(runRow.locator(".eyebrow")).toContainText("completed", {
      timeout: 120000,
    });
    await expect(runRow.locator("pre")).not.toBeEmpty();
  }
  await page.getByRole("button", { name: "Runtime", exact: true }).click();
  const goalTitle = "Dashboard acceptance " + Date.now();
  await page.getByLabel("Goal title").fill(goalTitle);
  await page.getByRole("button", { name: "Create goal", exact: true }).click();
  await expect(page.getByRole("heading", { name: goalTitle })).toBeVisible();
  await page.getByRole("button", { name: "Browser", exact: true }).click();
  await page.getByRole("button", { name: "Open managed session" }).click();
  await page.getByRole("button", { name: "Navigate", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "ALIVE · First Contact" }),
  ).toBeVisible();
  await page.getByLabel("Authorised URL").fill("https://example.com");
  await page.getByRole("button", { name: "Navigate", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "not in ALIVE_BROWSER_ORIGINS",
  );
  await page
    .getByRole("button", { name: "Close session", exact: true })
    .click();
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: "../.alive/dashboard.png", fullPage: true });
});
