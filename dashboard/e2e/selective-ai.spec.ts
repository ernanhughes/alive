import { test, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";

// Read-only proof against a retained live ledger: no write request may be sent.
test("retained selective adaptation shows a supplied lesson and a deliberate no-lesson decision", async ({ page }) => {
  const path = process.env.ALIVE_SELECTIVE_LEDGER; // only names the output files
  const app = process.env.ALIVE_BASE_URL;
  test.skip(!path || !app || !process.env.ALIVE_API_TOKEN, "Requires approved disposable live ledger");
  // Pick turns the dashboard actually lists (latest 20 exchanges), read-only.
  const history = await (
    await page.request.get(app! + "/api/v1/admissions/live", {
      headers: { Authorization: "Bearer " + process.env.ALIVE_API_TOKEN! },
    })
  ).json();
  const consentOf = (e: any) =>
    history.conversations.find((c: any) => c.id === e.conversation_ref)?.consent_ref;
  const writes: string[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith(app! + "/api/") && request.method() !== "GET") writes.push(request.url());
  });
  await page.goto(app! + "/#bespoke?");
  await page.getByLabel("Local API token").fill(process.env.ALIVE_API_TOKEN!);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  const pane = page.getByRole("region", { name: "ALIVE Live AI", exact: true });
  // Only turns whose trusted session the dropdown actually offers can be opened.
  await expect(
    pane.getByRole("combobox", { name: "Trusted workspace session", exact: true }).locator("option"),
  ).not.toHaveCount(1);
  const offered: string[] = await pane
    .getByRole("combobox", { name: "Trusted workspace session", exact: true })
    .locator("option")
    .evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
  const listed = history.exchanges.filter(
    (e: any) => e.answer && e.selection && e.conversation_ref && offered.includes(consentOf(e)),
  );
  const supplied = listed.find((e: any) => e.selection.selected.length && e.answer.lesson_ids_used.length);
  const none = listed.find((e: any) => e.selection.decision === "none");
  expect(supplied).toBeTruthy();
  expect(none).toBeTruthy();

  async function open(turn: any) {
    await pane
      .getByRole("combobox", { name: "Trusted workspace session", exact: true })
      .selectOption(consentOf(turn));
    await pane
      .getByRole("combobox", { name: "Conversation", exact: true })
      .selectOption(turn.conversation_ref);
    await expect(pane.getByText(turn.answer.answer, { exact: true })).toBeVisible();
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
        supplied_exchange: supplied.id,
        no_lesson_exchange: none.id,
        supplied_override: supplied.selection.override,
        no_lesson_reason: none.selection.no_lesson_reason,
        no_lesson_override: none.selection.override,
        writes,
        retained_live_output: true,
      },
      null,
      2,
    ),
  );
});
