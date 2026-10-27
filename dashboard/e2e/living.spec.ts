import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("living experience links changed browser action to saved feedback, not model sampling", async ({ page, request }) => {
  const token = process.env.ALIVE_API_TOKEN || fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  const headers = { Authorization: "Bearer " + token };
  const base = "http://127.0.0.1:8000/api/v1";
  const status = await (await request.get(base + "/living", { headers })).json();
  const meta = status.journeys.find((j: { provider: string }) => j.provider === "meta");
  test.skip(!meta, "Separate native Chrome/Meta qualification required");
  const journey = await (await request.get(base + "/living/journeys/" + meta.id, { headers })).json();
  expect(journey.status).toBe("completed");
  expect(journey.transitions).toHaveLength(2);
  const [a, b] = journey.transitions.map((t: { data: unknown }) => t.data);
  expect(a.choice.action).toBe("monitor");
  expect(b.choice.action).toBe("retrieve");
  expect(a.state.feature_hash).toBe(b.state.feature_hash);
  expect(a.after_hash).toBe(b.before_hash);
  expect(b.memory_ids).toEqual([journey.transitions[0].id]);
  expect(b.initial_policy_counterfactual.action).toBe("monitor");
  expect(journey.data.ledger).toHaveLength(2);
  expect(journey.data.ledger[0].input.sources).toHaveLength(0);
  expect(journey.data.ledger[0].input.observation).not.toContain("Instrument reading: 20");
  expect(journey.data.ledger[0].input.observation).not.toContain("Feedback measurement: 20");
  expect(journey.data.ledger[1].input.sources[0].value).toBe("20");
  for (const call of journey.data.ledger) {
    expect(call.provider).toBe("meta"); expect(call.status).toBe("validated");
    expect(call.usage.total_tokens).toBeGreaterThan(0);
    const choice = journey.data.phases.filter((p: { stage: string }) => p.stage === "choosing")[call.episode - 1];
    expect(new Date(choice.at).getTime()).toBeLessThanOrEqual(new Date(call.started_at).getTime());
  }
  // Inspect the actual controlled page visibility and permitted DOM interaction.
  await page.goto(`http://127.0.0.1:8000/living/world/${meta.id}/1`);
  await expect(page.locator("#instrument")).toBeHidden();
  await expect(page.locator("#feedback")).toBeHidden();
  await page.locator("#retrieve").click();
  await expect(page.locator("#instrument")).toContainText("20 hours");
  await expect(page.locator("#feedback")).toBeHidden();
  await page.locator("#feedback-button").click();
  await expect(page.locator("#feedback")).toBeVisible();
  await page.addInitScript(token => sessionStorage.setItem("alive-token", token), token);
  await page.setViewportSize({ width: 1600, height: 1200 });
  await page.goto("/");
  await page.getByRole("button", { name: "Living", exact: true }).click();
  await page.getByLabel("Recorded living journey").selectOption(meta.id);
  await expect(page.getByTestId("behavior-change")).toBeVisible();
  await expect(page.getByTestId("encounter-1")).toContainText("Safely abstained");
  await expect(page.getByTestId("encounter-2")).toContainText("Goal resolved with current evidence");
  await expect(page.getByTestId("encounter-2")).toContainText("1 relevant prior experience");
  await expect(page.getByText("Live Meta reasoning", { exact: true })).toBeVisible();
  await page.screenshot({ path: "../.alive/alive04-acceptance.png", fullPage: true });
  await page.locator(".living-encounters").screenshot({ path: "../.alive/alive04-encounters.png" });
});
