import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

const ledgerPath = process.env.ALIVE_LIVE_LEDGER;
const ledger = ledgerPath ? JSON.parse(readFileSync(ledgerPath, "utf8")) : null;
const app = process.env.ALIVE_BASE_URL;

test("three live dashboard goals reuse one owner consent and retain real receipts", async ({
  page,
}) => {
  test.skip(
    !ledger || !app || !process.env.ALIVE_API_TOKEN,
    "Requires explicitly approved disposable scripts.live_bespoke_demo --setup-only runtime",
  );
  // This is intentionally one live scenario. Each goal stays within the existing consent.
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(app + "/api/") && r.method() !== "GET")
      writes.push(r.url());
  });
  await page.goto(app + "/#bespoke?");
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const pane = page.getByRole("region", { name: "ALIVE Live AI", exact: true });
  for (const item of ledger.cases) {
    await pane.getByLabel("Your goal", { exact: true }).fill(item.goal);
    const completed = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/v1/admissions/live/ask") &&
        r.request().method() === "POST",
    );
    await pane.getByRole("button", { name: "Ask ALIVE", exact: true }).click();
    const response = await completed;
    expect(response.ok()).toBeTruthy();
    const exchange = await response.json();
    ledger.exchanges.push(exchange);
    writeFileSync(ledgerPath!, JSON.stringify(ledger, null, 2));
    expect(exchange.status).toBe("LIVE MODEL");
    expect(exchange.goal).toBe(item.goal);
    expect(
      exchange.calls.every(
        (c: { status: string; provider_receipts: unknown[] }) =>
          c.status === "validated" && c.provider_receipts.length > 0,
      ),
    ).toBeTruthy();
    await expect(pane.getByLabel("Your goal", { exact: true })).toHaveValue("");
  }
  await expect(pane.locator("article")).toHaveCount(3);
  expect(
    ledger.exchanges.some((e: { report: unknown }) => e.report),
  ).toBeTruthy();
  expect(writes).toEqual(Array(3).fill(app + "/api/v1/admissions/live/ask"));
  const before = writes.length;
  await page.reload();
  await expect(pane.locator("article")).toHaveCount(3);
  expect(writes.length).toBe(before);
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
  ledger.status = "LIVE_DASHBOARD_DEMONSTRATED; restart verification pending";
  ledger.manual_approvals = 1;
  ledger.goal_submissions = 3;
  ledger.browser_writes = writes;
  writeFileSync(ledgerPath!, JSON.stringify(ledger, null, 2));
});
