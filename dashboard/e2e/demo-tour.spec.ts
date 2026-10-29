import { test, expect, type Page } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

// ALIVE-DEMO-INTEGRATION-01 acceptance against the COMPOSED app in real Chrome.
// Not part of the default e2e run: set DEMO_E2E=1 and a DEMO_PHASE (see scripts/demo-acceptance.ps1).
//   journey        click Start, check every step, reload, second run, owner data untouched
//   after-restart  after `docker compose restart app`: persisted state, new process id
//   disabled       ALIVE_DEMO_MODE=false: the tab refuses and the API says 403
//   record         slow walkthrough with a RECORDED banner, saved as video (never "live")
const APP = (process.env.ALIVE_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN = process.env.ALIVE_API_TOKEN || "";
const PHASE = process.env.DEMO_PHASE || "journey";
const STATE = process.env.DEMO_STATE_FILE || "../.alive/demo-acceptance/state.json";
const SHOTS = process.env.DEMO_SHOTS || "../docs/demo/evidence";
const LABEL = "DETERMINISTIC LOCAL FIXTURE — NOT LIVE META";
const KEYS = [
  "observe_original",
  "save_memory",
  "anchor",
  "observe_later",
  "compare_consent",
  "compare",
  "abstention_consent",
  "abstention",
  "before_withdrawal",
  "withdraw",
  "after_withdrawal",
  "audit",
];
const headers = { Authorization: "Bearer " + TOKEN };
const BX = "/api/v1/browser-experience";

test.skip(!process.env.DEMO_E2E || !TOKEN, "DEMO_E2E=1 and ALIVE_API_TOKEN are required");
test.use({ baseURL: APP });

async function open(page: Page) {
  await page.addInitScript((t) => sessionStorage.setItem("alive-token", t), TOKEN);
  await page.goto(APP + "/");
  await expect(page.locator(".connection")).toContainText("Backend connected");
  await page.getByRole("button", { name: "Demonstration", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Pinned sources" })).toBeVisible();
}
const shot = (page: Page, name: string) =>
  page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
const steps = (page: Page) =>
  page.locator("[data-step]").evaluateAll((els) => els.map((e) => e.getAttribute("data-step")));

async function runOnce(page: Page, label: string) {
  await page.getByRole("button", { name: "Start demonstration" }).click();
  await expect(page.getByRole("heading", { name: new RegExp(`Run #${label} · completed`) })).toBeVisible({
    timeout: 45000,
  });
  await expect(page.locator('[data-step="audit"]')).toBeVisible({ timeout: 45000 });
}

test("journey: one click, every step, reload, second run, owner data untouched", async ({ page }) => {
  test.skip(PHASE !== "journey");
  mkdirSync(SHOTS, { recursive: true });
  mkdirSync(dirname(STATE), { recursive: true });
  const owner = await (
    await page.request.post(APP + BX + "/goals", {
      headers,
      data: { instruction: "Owner goal that the demonstration must not touch" },
    })
  ).json();

  await open(page);
  await expect(page.getByText(LABEL).first()).toBeVisible();
  await shot(page, "01-ready");

  await runOnce(page, "1");
  expect(await steps(page)).toEqual(KEYS);
  await expect(page.getByText(LABEL).first()).toBeVisible();
  const table = page.getByLabel("Before and after withdrawal");
  await expect(table).toContainText(/Findings returned\s*1\s*0/);
  await expect(table).toContainText(/Comparisons and abstentions returned\s*2\s*0/);
  await expect(table).toContainText(/Retrieval can surface the source\s*yes\s*no/);
  await expect(page.getByLabel("Audit view")).toContainText("nothing was physically deleted");
  await expect(page.locator('[data-step="compare"]')).toContainText("Deprecated since version 3.12");
  await expect(page.locator('[data-step="abstention"]')).toContainText("insufficient_evidence");
  await shot(page, "02-journey-completed");

  // Refresh: state comes back from the database, not from browser memory.
  await page.reload();
  await page.getByRole("button", { name: "Demonstration", exact: true }).click();
  await page.getByRole("button", { name: /#1 \(completed\)/ }).click();
  await expect(page.getByLabel("Current backend state")).toContainText("Source active: no");
  await expect(page.getByLabel("Current backend state")).toContainText("findings: 0");
  await shot(page, "03-after-reload");

  // A second run is separate and idempotent for owner data.
  await runOnce(page, "2");
  const goals = (await (await page.request.get(APP + BX, { headers })).json()).goals as { id: string }[];
  expect(goals.map((g) => g.id)).toContain(owner.id);
  await page.getByRole("button", { name: /#1 \(completed\)/ }).click();
  await expect(page.getByRole("heading", { name: /Run #1 · completed/ })).toBeVisible();
  await shot(page, "04-second-run");

  const info = await (await page.request.get(APP + "/api/v1/demo-tour", { headers })).json();
  writeFileSync(
    STATE,
    JSON.stringify({ ownerGoalId: owner.id, runs: info.runs, bootId: info.boot.id }, null, 2),
  );
});

test("after restart: persisted state is unchanged and the process is new", async ({ page }) => {
  test.skip(PHASE !== "after-restart");
  mkdirSync(SHOTS, { recursive: true });
  const saved = JSON.parse(readFileSync(STATE, "utf-8"));
  const info = await (await page.request.get(APP + "/api/v1/demo-tour", { headers })).json();
  expect(info.boot.id).not.toBe(saved.bootId);
  expect(info.runs.map((r: { run_id: string }) => r.run_id).sort()).toEqual(
    saved.runs.map((r: { run_id: string }) => r.run_id).sort(),
  );
  const goals = (await (await page.request.get(APP + BX, { headers })).json()).goals as { id: string }[];
  expect(goals.map((g) => g.id)).toContain(saved.ownerGoalId);
  for (const run of info.runs) {
    const state = await (await page.request.get(`${APP}/api/v1/demo-tour/runs/${run.run_id}`, { headers })).json();
    expect(state.status).toBe("completed");
    expect(state.live.memory_active).toBe(false);
    expect(state.live.connection_ids).toEqual([]);
    const listed = await (
      await page.request.get(`${APP}${BX}/research/relationships?goal_id=${state.goal_id}`, { headers })
    ).json();
    expect(listed.connections).toEqual([]);
    expect(listed.analyses).toEqual([]);
    expect(state.audit.rows.map((r: { status: string }) => r.status)).toContain("withdrawn");
  }
  await open(page);
  await page.getByRole("button", { name: /#1 \(completed\)/ }).click();
  await expect(page.getByLabel("Current backend state")).toContainText("Source active: no");
  await expect(page.getByLabel("Current backend state")).toContainText(info.boot.id);
  await shot(page, "05-after-restart");
});

test("disabled: the tab refuses and the API says no", async ({ page }) => {
  test.skip(PHASE !== "disabled");
  mkdirSync(SHOTS, { recursive: true });
  await open(page);
  await expect(page.getByText("Demonstration unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start demonstration" })).toBeDisabled();
  // Earlier runs persist on the same volumes by design; a refused request must add nothing.
  const demoGoals = async () =>
    ((await (await page.request.get(APP + BX, { headers })).json()).goals as any[]).filter((g) =>
      /Demonstration \d/.test(g.data?.instruction || ""),
    ).length;
  const before = await demoGoals();
  const refused = await page.request.post(APP + "/api/v1/demo-tour/runs", { headers, data: {} });
  expect(refused.status()).toBe(403);
  expect(await demoGoals()).toBe(before);
  await shot(page, "06-disabled");
});

test("record: a RECORDED storyboard, never presented as live", async ({ browser }) => {
  test.skip(PHASE !== "record");
  mkdirSync(SHOTS + "/recorded", { recursive: true });
  // Video needs Playwright's ffmpeg (`npx playwright install ffmpeg`, installed by the driver script
  // into the user cache, never the repo); the storyboard does not. Video is paced for a viewer.
  const video = Boolean(process.env.DEMO_VIDEO);
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    ...(video
      ? { recordVideo: { dir: "test-results/recorded-video", size: { width: 1280, height: 800 } } }
      : {}),
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.addEventListener("DOMContentLoaded", () => {
      const banner = document.createElement("div");
      banner.textContent = "RECORDED WALKTHROUGH — NOT LIVE — replay of a real local run";
      banner.style.cssText =
        "position:fixed;top:0;left:0;right:0;z-index:99999;background:#7a1f1f;color:#fff;" +
        "font:700 14px system-ui;text-align:center;padding:6px";
      document.body.appendChild(banner);
    });
  });
  await open(page);
  if (video) await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "Start demonstration" }).click();
  for (const [i, key] of KEYS.entries()) {
    const step = page.locator(`[data-step="${key}"]`);
    await expect(step).toBeVisible({ timeout: 45000 });
    await step.scrollIntoViewIfNeeded();
    const n = String(i + 1).padStart(2, "0");
    await page.screenshot({ path: `${SHOTS}/recorded/RECORDED-${n}-${key}.png` });
    if (video) await page.waitForTimeout(2200);
  }
  await expect(page.getByRole("heading", { name: /Run #\d+ · completed/ })).toBeVisible();
  if (video) await page.waitForTimeout(3000);
  await context.close();
  if (video) await page.video()?.saveAs(`${SHOTS}/recorded/RECORDED-walkthrough.webm`);
});
