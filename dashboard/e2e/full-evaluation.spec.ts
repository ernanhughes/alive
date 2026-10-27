import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("authorized full evaluation displays persisted paired results", async ({ page, request }) => {
  const token = process.env.ALIVE_API_TOKEN || fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  const headers = { Authorization: "Bearer " + token };
  const response = await request.get("http://127.0.0.1:8000/api/v1/experiments", { headers });
  expect(response.ok()).toBeTruthy();
  const runs = await response.json();
  const full = runs.find((r: { phase: string }) => r.phase === "full");
  test.skip(!full || full.status === "running", "Completed authorized full-run evidence required");
  const detail = await (await request.get(
    "http://127.0.0.1:8000/api/v1/experiments/runs/" + full.id, { headers })).json();
  const frozen = JSON.parse(fs.readFileSync(path.resolve("../archives/ALIVE-03-P1/freeze-final.json"), "utf8"));
  expect(detail.data.freeze_id).toBe(frozen.freeze_id);
  expect(detail.data.physical_calls).toBeLessThanOrEqual(350);
  expect(detail.data.charged_tokens).toBeLessThanOrEqual(500000);
  await page.setViewportSize({ width: 1500, height: 1100 });
  await page.addInitScript(token => sessionStorage.setItem("alive-token", token), token);
  await page.goto("/");
  await page.getByRole("button", { name: "Cognition", exact: true }).click();
  const panel = page.locator(".experiment-panel");
  await panel.getByLabel("Recorded experiment run").selectOption(full.id);
  for (const [name, value] of Object.entries(full.summary.policies) as [string, { correct: number; tasks: number }][]) {
    const row = panel.getByRole("row").filter({ has: page.getByRole("rowheader", { name, exact: true }) });
    await expect(row).toContainText(`${value.correct}/${value.tasks}`);
  }
  await expect(panel.getByText(new RegExp(`${full.summary.physical_unique_calls} physical calls`))).toBeVisible();
  const taskDetails = panel.locator("details").first();
  await taskDetails.locator("summary").click();
  await expect(taskDetails).toContainText("Critic invoked");
  await expect(taskDetails).toContainText("Critic skipped");
  await taskDetails.locator("summary").click();
  await panel.evaluate(el => el.scrollIntoView({ block: "start" }));
  await page.screenshot({ path: "../.alive/full-evaluation-acceptance.png" });
});
