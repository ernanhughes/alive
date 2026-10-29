import { test, expect } from "@playwright/test";

// Production Docker journey: the real composed app serves API + UI on one origin.
// No Chrome automation here: the slim runtime image has no managed Chrome, so the
// Browser tab cannot succeed. This spec exercises the genuine UI workflow that
// works offline (goals, memory search, mock agent) plus the pinned fixture pages.
const APP = (process.env.ALIVE_BASE_URL || "http://localhost:8080").replace(
  /\/$/,
  "",
);
const TOKEN = process.env.ALIVE_API_TOKEN || "";

test.beforeEach(async ({ page }) => {
  test.skip(!TOKEN, "ALIVE_API_TOKEN is required");
  await page.addInitScript(
    (token) => sessionStorage.setItem("alive-token", token),
    TOKEN,
  );
});

test("docker production UI: overview, memory, agents and demo fixtures", async ({
  page,
}) => {
  await page.goto(APP + "/");
  await expect(page.locator(".connection")).toContainText("Backend connected");
  await expect(
    page.getByRole("heading", { name: "Something is becoming." }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Live events", exact: false }).click();
  await expect(page.getByText("Persisted event timeline")).toBeVisible();

  const marker = "docker browser observation " + Date.now();
  await page.request.post(APP + "/api/v1/events", {
    headers: { Authorization: "Bearer " + TOKEN },
    data: {
      event_type: "browser.page_opened",
      source: "user",
      payload: { url: APP + "/demo", text: marker },
    },
  });

  await page.getByRole("button", { name: "Memory", exact: true }).click();
  await page.getByLabel("Search memories").fill(marker);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("postgresql_fts", { exact: true })).toBeVisible();
  await expect(page.getByText(marker).first()).toBeVisible();

  await page.getByRole("button", { name: "Agents", exact: true }).click();
  await page.getByLabel("Objective").fill("Examine " + marker);
  const runResponse = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/agents/runs") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run agent", exact: true }).click();
  const runId = (await (await runResponse).json()).id;
  await expect(page.locator(`[data-run-id="${runId}"] pre`)).toContainText(
    "Observation examined",
  );

  await page.getByRole("button", { name: "Runtime", exact: true }).click();
  const goalTitle = "Docker browser goal " + Date.now();
  await page.getByLabel("Goal title").fill(goalTitle);
  await page.getByRole("button", { name: "Create goal", exact: true }).click();
  await expect(page.getByRole("heading", { name: goalTitle })).toBeVisible();
});

test("docker fixtures served offline by the app itself", async ({ page }) => {
  await page.goto(APP + "/demo");
  await expect(page.getByText("First Contact")).toBeVisible();
  const mirror = await page.request.get(
    APP + "/demo-live-01/python-3.12.html",
  );
  expect(mirror.status()).toBe(200);
  expect(await mirror.text()).toContain("LOCAL MIRROR");
});
