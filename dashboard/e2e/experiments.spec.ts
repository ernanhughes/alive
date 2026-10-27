import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("policy comparison renders persisted outcomes and preserves the full-run gate", async ({ page, request }) => {
  const token = process.env.ALIVE_API_TOKEN || fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  const headers = { Authorization: "Bearer " + token };
  const response = await request.get("http://127.0.0.1:8000/api/v1/experiments", { headers });
  expect(response.ok()).toBeTruthy();
  const runs = await response.json();
  await page.addInitScript(token => sessionStorage.setItem("alive-token", token), token);
  await page.goto("/");
  await page.getByRole("button", { name: "Cognition", exact: true }).click();
  const panel = page.getByTestId("policy-comparison");
  await expect(panel.getByRole("heading", { name: "Selective cognition experiment" })).toBeVisible();
  if (runs.length === 0) {
    await expect(panel.getByText("No experiment runs recorded.")).toBeVisible();
    return;
  }
  const run = runs.find((r: { phase: string; status: string }) => r.phase === "pilot" && r.status === "completed") || runs[0];
  await panel.getByLabel("Recorded experiment run").selectOption(run.id);
  if (run.summary) {
    await expect(panel.getByText(new RegExp(`${run.summary.physical_unique_calls} physical calls`))).toBeVisible();
    for (const [name, value] of Object.entries(run.summary.policies) as [string, { tasks: number; correct: number }][]) {
      if (!value.tasks) continue;
      const row = panel.getByRole("row").filter({ has: page.getByRole("rowheader", { name, exact: true }) });
      await expect(row).toContainText(`${value.correct}/${value.tasks}`);
    }
  }
  await panel.getByText("Full evaluation review", { exact: false }).click();
  await expect(panel.getByText("Full paid evaluation requires explicit owner authorization and sufficient Governor budget.")).toBeVisible();
  await panel.screenshot({ path: "../.alive/alive03-acceptance.png" });
});
