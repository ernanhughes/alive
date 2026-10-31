import { test, expect } from "@playwright/test";

// Fault-injection tests against the built dashboard, without a database or provider.
// Start with: npm exec vite preview -- --host 127.0.0.1 --port 8021
test.use({ baseURL: process.env.ALIVE_AUTH_UI_URL || "http://127.0.0.1:8021" });
const valid = "auth-test-valid";
const caps = {
  database: { available: true, backend: "sqlite", error: null },
  pgvector: { storage: false, search: false, reason: "disabled" },
  zeromq: { available: false, received: 0 },
  pi: { configured: false },
  providers: { meta: { configured: false } },
};

for (const mobile of [false, true]) {
  test(`wrong token remains recoverable through reload, correction and change (${mobile ? "mobile" : "desktop"})`, async ({
    page,
  }) => {
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    let outage = false,
      expired = false,
      requests = 0,
      sockets = 0;
    await page.routeWebSocket("**/api/v1/events/stream", () => {
      sockets++;
    });
    await page.route("**/api/v1/**", async (route) => {
      requests++;
      if (outage) {
        await route.abort("connectionrefused");
        return;
      }
      const authorized =
        route.request().headers().authorization === `Bearer ${valid}` &&
        !expired;
      if (!authorized) {
        await route.fulfill({ status: 401, json: { detail: "unauthorized" } });
        return;
      }
      const path = new URL(route.request().url()).pathname;
      const body = path.endsWith("/capabilities")
        ? caps
        : path.endsWith("/alive")
          ? {
              identity: {
                id: "local",
                name: "ALIVE",
                lifecycle_state: "stopped",
              },
              runtime: {
                heartbeat_at: null,
                state_version: 0,
                active_goals: [],
              },
              drives: {},
            }
          : path.endsWith("/agents")
            ? { runs: [] }
            : [];
      await route.fulfill({ status: 200, json: body });
    });
    await page.goto("/");
    expect(requests).toBe(0);
    expect(sockets).toBe(0);
    await page.getByLabel("Local API token").fill("wrong");
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    await expect(page.getByRole("alert")).toHaveText(
      "Invalid token — try again.",
    );
    await expect(page.getByLabel("Local API token")).toHaveValue("wrong");
    expect(
      await page.evaluate(() => sessionStorage.getItem("alive-token")),
    ).toBeNull();
    expect(sockets).toBe(0);
    await page.reload();
    await expect(page.getByLabel("Local API token")).toBeEditable();
    // Simulate credentials persisted by the previous buggy dashboard.
    await page.evaluate(() =>
      sessionStorage.setItem("alive-token", "legacy-invalid"),
    );
    await page.reload();
    await expect(page.getByRole("alert")).toHaveText(
      "Invalid token — try again.",
    );
    expect(
      await page.evaluate(() => sessionStorage.getItem("alive-token")),
    ).toBeNull();
    await page.getByLabel("Local API token").fill(valid);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    await expect(page.locator(".connection")).toContainText(
      "Backend connected",
    );
    expect(sockets).toBeGreaterThan(0);
    outage = true;
    await page.getByRole("button", { name: "Retry authentication" }).click();
    await expect(page.getByRole("alert")).toContainText("Unable to verify");
    await expect(
      page.getByRole("button", { name: "Change token" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Retry authentication" }),
    ).toBeVisible();
    expect(
      await page.evaluate(() => sessionStorage.getItem("alive-token")),
    ).toBe(valid);
    outage = false;
    expired = true;
    await page.getByRole("button", { name: "Retry authentication" }).click();
    await expect(page.getByRole("alert")).toHaveText(
      "Invalid token — try again.",
    );
    await expect(page.getByLabel("Local API token")).toBeEditable();
    expired = false;
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    await expect(page.locator(".connection")).toContainText(
      "Backend connected",
    );
    await page.getByRole("button", { name: "Change token" }).click();
    await expect(page.getByLabel("Local API token")).toHaveValue("");
    expect(
      await page.evaluate(() => sessionStorage.getItem("alive-token")),
    ).toBeNull();
    expect(page.url()).not.toContain(valid);
  });
}
