import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("predictive learning displays checked simulator evidence and pre-action predictions", async ({ page, request }) => {
  const token = process.env.ALIVE_API_TOKEN || fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  const response = await request.get("http://127.0.0.1:8000/api/v1/learning", {
    headers: { Authorization: "Bearer " + token },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  test.skip(!result.available, "Completed simulator qualification required");
  expect(result.simulation_only).toBe(true);
  expect(result.meta_calls).toBe(0);
  expect(result.live_actions).toBe(0);
  await page.setViewportSize({ width: 1600, height: 1150 });
  await page.addInitScript(token => sessionStorage.setItem("alive-token", token), token);
  await page.goto("/");
  await page.getByRole("button", { name: "Cognition", exact: true }).click();
  const panel = page.locator(".learning-panel");
  await expect(panel.getByRole("heading", { name: "Predictive cognitive learning" })).toBeVisible();
  for (const [name, value] of Object.entries(result.policies) as [string, { return: number }][]) {
    const row = panel.getByRole("row").filter({ has: page.getByRole("rowheader", { name, exact: true }) });
    await expect(row).toContainText(value.return.toFixed(3));
  }
  await panel.getByText("Prediction → observation → error · fixed demonstration", { exact: true }).click();
  await expect(panel.getByRole("heading", { name: "Before training" })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "After predictive training" })).toBeVisible();
  await expect(panel.getByText("first frozen held-out scenario", { exact: false })).toBeVisible();
  await panel.evaluate(el => el.scrollIntoView({ block: "start" }));
  await page.screenshot({ path: "../.alive/p2-acceptance.png" });
});
