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
    .getByRole("combobox", { name: "Conversation", exact: true })
    .selectOption(ledger.conversation.id);
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(app + "/api/") && r.method() !== "GET")
      writes.push(r.url());
  });
  const goals = ledger.main.length
    ? ["What did the zero-value counterexample change in our earlier finding?"]
    : ledger.main_goals.slice(0, 4);
  ledger.browser = [];
  for (const goal of goals) {
    await pane.getByLabel("Your goal", { exact: true }).fill(goal);
    const completed = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/admissions/live/ask") &&
        r.request().method() === "POST",
    );
    await pane.getByRole("button", { name: "Ask ALIVE", exact: true }).click();
    const response = await completed;
    expect(response.ok()).toBeTruthy();
    const value = await response.json();
    ledger.browser.push(value);
    writeFileSync(ledgerPath!, JSON.stringify(ledger, null, 2));
    expect(value.status).toBe("LIVE MODEL");
    expect(value.answer || value.report).toBeTruthy();
    if (value.answer) {
      expect(value.answer.recalled_item_ids.length).toBeGreaterThan(0);
      await expect(
        pane.getByText(value.answer.answer, { exact: true }),
      ).toBeVisible();
    }
    await expect(pane.getByLabel("Your goal", { exact: true })).toHaveValue("");
  }
  expect(writes).toEqual(
    Array(goals.length).fill(app + "/api/v1/admissions/live/ask"),
  );
  const last = ledger.browser.at(-1);
  await page.reload();
  await pane
    .getByRole("combobox", { name: "Conversation", exact: true })
    .selectOption(ledger.conversation.id);
  await expect(
    pane.getByText(last.answer.answer, { exact: true }),
  ).toBeVisible();
  expect(writes).toHaveLength(goals.length);
  ledger.status = "LIVE_BROWSER_CONVERSATION_DEMONSTRATED";
  ledger.browser_writes = writes;
  writeFileSync(ledgerPath!, JSON.stringify(ledger, null, 2));
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
