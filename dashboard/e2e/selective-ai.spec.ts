import { test, expect } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";

// Read-only proof against a retained live ledger: no write request may be sent.
test("retained selective adaptation shows a supplied lesson and a deliberate no-lesson decision", async ({ page }) => {
  const path = process.env.ALIVE_SELECTIVE_LEDGER;
  const app = process.env.ALIVE_BASE_URL;
  test.skip(!path || !app || !process.env.ALIVE_API_TOKEN, "Requires approved disposable live ledger");
  const ledger = JSON.parse(readFileSync(path!, "utf8"));
  const turns = ledger.evaluation.filter((r: any) => r.arm === "D" && r.review.answer && r.review.selection);
  const supplied = turns.find((r: any) => r.review.selection.selected.length && r.review.answer.lesson_ids_used.length);
  const none = turns.find((r: any) => r.review.selection.decision === "none");
  expect(supplied).toBeTruthy();
  expect(none).toBeTruthy();
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith(app! + "/api/") && request.method() !== "GET") writes.push(request.url());
  });
  await page.goto(app! + "/#bespoke?");
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const pane = page.getByRole("region", { name: "ALIVE Live AI", exact: true });

  async function open(turn: any) {
    await pane
      .getByRole("combobox", { name: "Trusted workspace session", exact: true })
      .selectOption(turn.review.request.consent_ref);
    await pane
      .getByRole("combobox", { name: "Conversation", exact: true })
      .selectOption(turn.review.conversation_ref);
    await expect(pane.getByText(turn.review.answer.answer, { exact: true })).toBeVisible();
  }

  await open(supplied);
  await expect(pane.getByText(/lesson\(s\) supplied/)).toBeVisible();
  await expect(pane.getByText(/self-report, not proof/)).toBeVisible();
  await pane.getByText(/^Considered \d+ lesson/).first().click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: path!.replace(".json", "-supplied-1440.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path!.replace(".json", "-supplied-390.png"), fullPage: true });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await open(none);
  await expect(pane.getByText(/none supplied/)).toBeVisible();
  await expect(pane.getByText(/reasoned from the evidence alone|No reusable lesson|could not tell/)).toBeVisible();
  await page.screenshot({ path: path!.replace(".json", "-none-1440.png"), fullPage: true });
  expect(writes).toEqual([]);
  writeFileSync(
    path!.replace(".json", "-ui-proof.json"),
    JSON.stringify(
      {
        supplied_exchange: supplied.review.id,
        no_lesson_exchange: none.review.id,
        no_lesson_reason: none.review.selection.no_lesson_reason,
        writes,
        retained_live_output: true,
      },
      null,
      2,
    ),
  );
});
