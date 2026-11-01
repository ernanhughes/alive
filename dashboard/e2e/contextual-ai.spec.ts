import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

const ledgerPath = process.env.ALIVE_CONTEXT_LEDGER;
const ledger = ledgerPath ? JSON.parse(readFileSync(ledgerPath, "utf8")) : null;
const app = process.env.ALIVE_BASE_URL;

test("retained live conversation answers a natural follow-up in Ask ALIVE", async ({
  page,
}) => {
  test.skip(
    !ledger || !app || !process.env.ALIVE_API_TOKEN,
    "Requires explicitly approved disposable scripts.contextual_demo runtime",
  );
  await page.goto(app + "/#bespoke?");
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const pane = page.getByRole("region", { name: "ALIVE Live AI", exact: true });
  await pane
    .getByLabel("Conversation", { exact: true })
    .selectOption(ledger.conversation.id);
  await expect(pane.locator("article")).not.toHaveCount(0);
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(app + "/api/") && r.method() !== "GET")
      writes.push(r.url());
  });
  await pane
    .getByLabel("Your goal", { exact: true })
    .fill(
      "What did the zero-value counterexample change in our earlier finding?",
    );
  const completed = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/admissions/live/ask") &&
      r.request().method() === "POST",
  );
  await pane.getByRole("button", { name: "Ask ALIVE", exact: true }).click();
  const response = await completed;
  expect(response.ok()).toBeTruthy();
  const value = await response.json();
  ledger.browser = value;
  writeFileSync(ledgerPath!, JSON.stringify(ledger, null, 2));
  expect(value.status).toBe("LIVE MODEL");
  expect(value.answer.answer).toBeTruthy();
  expect(value.answer.recalled_item_ids.length).toBeGreaterThan(0);
  await expect(
    pane.getByText(value.answer.answer, { exact: true }),
  ).toBeVisible();
  expect(writes).toEqual([app + "/api/v1/admissions/live/ask"]);
  await page.reload();
  await pane
    .getByLabel("Conversation", { exact: true })
    .selectOption(ledger.conversation.id);
  await expect(
    pane.getByText(value.answer.answer, { exact: true }),
  ).toBeVisible();
  expect(writes).toHaveLength(1);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: ledgerPath!.replace(".json", "-1440.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: ledgerPath!.replace(".json", "-390.png"),
    fullPage: true,
  });
});
