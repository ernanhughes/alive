import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const FILE = process.env.ALIVE_OBSERVATORY_MANIFEST;
const APP = (process.env.ALIVE_BASE_URL || "http://127.0.0.1:8018").replace(
  /\/$/,
  "",
);
const TOKEN = process.env.ALIVE_API_TOKEN || "";
const manifest = FILE ? JSON.parse(readFileSync(FILE, "utf8")) : null;

test("persisted observatory: real Pi, distinct graphs, replay, comparison and uncertainty", async ({
  page,
}, testInfo) => {
  test.skip(
    !manifest || !TOKEN,
    "Seed the disposable observatory and set manifest/token",
  );
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.url().startsWith(APP + "/api/") && r.method() !== "GET")
      writes.push(r.method() + " " + r.url());
  });
  const run = (label: string) =>
    manifest.runs.find((r: { label: string }) => r.label === label);
  const hash = (r: any, stage = "") =>
    "#workflows?" +
    new URLSearchParams({
      workflow: r.workflow.name,
      version: String(r.workflow.version),
      run: r.id,
      ...(stage ? { stage } : {}),
    });
  await page.goto(APP + "/" + hash(run("research"), "analyze"));
  await page.getByLabel("Local API token").fill(TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Run " + run("research").id }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /research-review version 2/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Select a stage" }).getByRole("listitem"),
  ).toHaveCount(4);
  await page.getByRole("tab", { name: "Stage details", exact: true }).click();
  await page.getByRole("button", { name: "Open actual Pi receipt" }).click();
  await expect(
    page.getByRole("heading", { name: "Actual Pi receipt" }),
  ).toBeVisible();
  await expect(page.getByText("Unverified", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Pi receipt")).toContainText("SETTLED");
  await page.screenshot({
    path: testInfo.outputPath("research-pi.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Select Record", exact: true })
    .click();
  await page.getByRole("tab", { name: "Evidence & result" }).click();
  await page.getByRole("button", { name: "Open retained artifact" }).click();
  await expect(
    page.getByRole("heading", { name: "Retained result", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Retained artifact")).toContainText(
    "Not recorded",
  );
  await page.getByRole("tab", { name: "Recorded events", exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Recorded events", exact: true }),
  ).toContainText("pi.provider_request.dispatched");
  await page.getByRole("button", { name: "Replay recorded events" }).click();
  await page.getByRole("button", { name: "Next event" }).click();
  await expect(
    page.getByText("Read-only local replay.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Return to current snapshot" })
    .click();
  await page.getByRole("tab", { name: "Comparison" }).click();
  await page.getByLabel("Compare with run").selectOption(run("research_v3").id);
  await expect(
    page.getByRole("heading", { name: "Run comparison", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Run comparison")).toContainText(
    run("research_v3").workflow.definition_sha256,
  );
  await page.screenshot({
    path: testInfo.outputPath("comparison.png"),
    fullPage: true,
  });
  await page.goto(APP + "/" + hash(run("deterministic"), "compare"));
  await expect(
    page.getByRole("list", { name: "Select a stage" }).getByRole("listitem"),
  ).toHaveCount(3);
  await page.getByRole("tab", { name: "Stage details", exact: true }).click();
  await expect(
    page.getByText("Deterministic stage — no model invocation recorded."),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath("deterministic.png"),
    fullPage: true,
  });
  for (const label of ["goal_cancel", "ambiguous", "partial"]) {
    await page.goto(
      APP +
        "/" +
        hash(
          run(label),
          label === "partial"
            ? "record"
            : label === "ambiguous"
              ? "analyze"
              : "prepare",
        ),
    );
    await expect(
      page.getByRole("heading", { name: "Run " + run(label).id }),
    ).toBeVisible();
    await expect(page.locator(".workflow-observatory")).toContainText(
      run(label).status,
    );
    if (label === "partial") {
      await page.getByRole("tab", { name: "Evidence & result" }).click();
      await page
        .getByRole("button", { name: "Open retained artifact" })
        .click();
      await expect(
        page.getByRole("heading", { name: "Partial / historical artifact" }),
      ).toBeVisible();
      await expect(page.getByLabel("Retained artifact")).toContainText(
        "FAILED",
      );
    }
    await page.screenshot({
      path: testInfo.outputPath(label + ".png"),
      fullPage: true,
    });
  }
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Run " + run("partial").id }),
  ).toBeVisible();
  expect(writes).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: testInfo.outputPath("mobile.png"),
    fullPage: true,
  });
  expect(
    await page
      .locator("body")
      .evaluate((e) => e.scrollWidth <= window.innerWidth + 1),
  ).toBe(true);
});
