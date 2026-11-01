import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

test("retained adaptation shows provisional strategies without new inference", async ({ page }) => {
  const path = process.env.ALIVE_ADAPTATION_LEDGER;
  const app = process.env.ALIVE_BASE_URL;
  test.skip(!path || !app || !process.env.ALIVE_API_TOKEN, "Requires approved disposable live ledger");
  const ledger = JSON.parse(readFileSync(path!, "utf8"));
  const proof = [...ledger.evaluation].reverse().find((r) => r.arm === "C" && r.review.answer?.lesson_ids_used?.length);
  expect(proof).toBeTruthy();
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith(app! + "/api/") && request.method() !== "GET") writes.push(request.url());
  });
  await page.goto(app! + "/#bespoke?");
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const pane = page.getByRole("region", { name: "ALIVE Live AI", exact: true });
  await pane.getByRole("combobox", { name: "Trusted workspace session", exact: true })
    .selectOption(proof.review.request.consent_ref);
  await pane.getByRole("combobox", { name: "Conversation", exact: true }).selectOption(proof.review.conversation_ref);
  await expect(pane.getByText(proof.review.answer.answer, { exact: true })).toBeVisible();
  await expect(pane.getByText("Procedure used: contextual-reasoning", { exact: true })).toBeVisible();
  await expect(pane.getByText("Strategies used: " + proof.review.answer.lesson_ids_used.join(", "), { exact: true })).toBeVisible();
  await pane.getByText(/^Reusable lessons \(/).click();
  await expect(pane.getByText(/Qualification and reusable text approval/)).toBeVisible();
  await expect(pane.getByText(/provisional; one observation is not general validity/).first()).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: path!.replace(".json", "-ui-1440.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path!.replace(".json", "-ui-390.png"), fullPage: true });
  expect(writes).toEqual([]);
  writeFileSync(path!.replace(".json", "-ui-proof.json"), JSON.stringify({
    exchange_id: proof.review.id, strategy_ids: proof.review.answer.lesson_ids_used,
    conversation_ref: proof.review.conversation_ref, writes, retained_live_output: true,
  }, null, 2));
});
