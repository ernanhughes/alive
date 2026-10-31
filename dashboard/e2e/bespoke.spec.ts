import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const manifestPath = process.env.ALIVE_BESPOKE_MANIFEST;
const manifest = manifestPath
  ? JSON.parse(readFileSync(manifestPath, "utf8"))
  : null;
const app = process.env.ALIVE_BASE_URL || "http://127.0.0.1:8026";
const token = process.env.ALIVE_API_TOKEN || "";

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
]) {
  test(`Bespoke history preserves identity without execution at ${viewport.width}px`, async ({
    page,
  }, info) => {
    test.skip(
      !manifest || !token,
      "Seed a disposable runtime with scripts.bespoke_check --serve",
    );
    await page.setViewportSize(viewport);
    const writes: string[] = [];
    page.on("request", (r) => {
      if (r.url().startsWith(app + "/api/") && r.method() !== "GET")
        writes.push(r.url());
    });
    const record = manifest.source_comparison.recommendation;
    await page.goto(app + "/#bespoke?recommendation=" + record.id);
    await page.getByLabel("Local API token").fill(token);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    await expect(page.getByText("HISTORICAL RECOMMENDATION")).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Workflow graph" }),
    ).toBeVisible();
    await expect(page.getByText(/Authorization unavailable/)).toBeVisible();
    await expect(
      page.getByText(/1 distinct eligible execution contracts/),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Capabilities", exact: true }).click();
    await expect(
      page.getByRole("link", { name: "evidence.evaluate v1.0.0" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`bespoke-${viewport.width}.png`),
      fullPage: true,
    });
    await page.getByRole("link", { name: /Inspect COMPLETED run/ }).click();
    await expect(
      page.getByRole("heading", {
        name: "Run " + manifest.source_comparison.run.id,
      }),
    ).toBeVisible();
    expect(writes).toEqual([]);
  });
}
