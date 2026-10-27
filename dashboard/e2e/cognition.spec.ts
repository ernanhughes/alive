import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("autonomous DOM observation, role exchange, approval and hard budget controls", async ({
  page,
  request: api,
}) => {
  test.setTimeout(90000);
  const token =
    process.env.ALIVE_API_TOKEN ||
    fs.readFileSync(path.resolve("../.alive/token"), "utf8").trim();
  const headers = { Authorization: "Bearer " + token };
  const base = "http://127.0.0.1:8000/api/v1";
  await api.post(base + "/cognition/control", {
    headers,
    data: { command: "pause" },
  });
  await api.post(base + "/cognition/control", {
    headers,
    data: { command: "new_session" },
  });
  await api.post(base + "/cognition/configuration", {
    headers,
    data: { preferred_action: "lab_draft" },
  });
  await page.addInitScript(
    (t) => sessionStorage.setItem("alive-token", t),
    token,
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Cognition", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cognitive control" }),
  ).toBeVisible();
  await page.getByLabel("Cognitive provider").selectOption("mock");
  await page
    .getByRole("button", { name: "Start autonomy", exact: true })
    .click();
  await expect(page.getByTestId("autonomy-mode")).toHaveText("running");
  const created = page.waitForResponse(
    (r) => r.url() === base + "/lab" && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Open & observe habitat" }).click();
  const environment = (await (await created).json()).id;
  await page
    .getByRole("button", { name: "Inject environmental change" })
    .click();
  let investigation = "";
  await expect
    .poll(
      async () => {
        const rows = await (
          await api.get(base + "/cognition/investigations", { headers })
        ).json();
        const row = rows.find(
          (r: { snapshot: { environment_id: string } }) =>
            r.snapshot.environment_id === environment,
        );
        investigation = row?.id || "";
        return row?.state;
      },
      { timeout: 30000 },
    )
    .toBe("AWAITING_APPROVAL");
  await page
    .getByLabel("Investigation", { exact: true })
    .selectOption(investigation);
  await expect(
    page.getByRole("heading", { name: "Structured exchanges" }),
  ).toBeVisible();
  const detail = await (
    await api.get(base + "/cognition/investigations/" + investigation, {
      headers,
    })
  ).json();
  const action = detail.actions[0];
  expect(action.risk_class).toBe("B");
  expect(
    (await (await api.get(base + "/lab/world/" + environment)).json()).draft,
  ).toBe("");
  const permissionCard = page.locator(`[data-action-id="${action.id}"]`);
  await expect(
    permissionCard.getByRole("button", { name: "approve", exact: true }),
  ).toBeVisible();
  await permissionCard
    .getByRole("button", { name: "approve", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (
          await (
            await api.get(base + "/cognition/investigations/" + investigation, {
              headers,
            })
          ).json()
        ).state,
    )
    .toBe("COMPLETED");
  const after = await (
    await api.get(base + "/lab/world/" + environment)
  ).json();
  expect(after.draft.length).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Revoke & close" }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByTestId("autonomy-mode")).toHaveText("paused");
  await page
    .getByText("Resource budgets & permissions", { exact: true })
    .click();
  const config = JSON.parse(
    await page.getByLabel("Governor configuration").inputValue(),
  );
  config.session_calls = 0;
  config.preferred_action = "record_analysis";
  await page
    .getByLabel("Governor configuration")
    .fill(JSON.stringify(config, null, 2));
  await page
    .getByRole("button", { name: "Save budgets and permissions" })
    .click();
  await expect
    .poll(
      async () =>
        (await (await api.get(base + "/cognition", { headers })).json()).control
          .configuration.session_calls,
    )
    .toBe(0);
  await page
    .getByRole("button", { name: "Start autonomy", exact: true })
    .click();
  const createdAgain = page.waitForResponse(
    (r) => r.url() === base + "/lab" && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Open & observe habitat" }).click();
  const second = (await (await createdAgain).json()).id;
  await page
    .getByRole("button", { name: "Inject environmental change" })
    .click();
  await expect
    .poll(async () => {
      const rows = await (
        await api.get(base + "/cognition/observations", { headers })
      ).json();
      return rows.find((o: { provenance: { url: string } }) =>
        o.provenance.url.endsWith(second),
      )?.status;
    })
    .toBe("BUDGET_REJECTED");
  await page
    .getByRole("button", { name: "Stop autonomy", exact: true })
    .click();
  await page.getByRole("button", { name: "Revoke & close" }).click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../.alive/cognition-e2e.png",
    fullPage: true,
  });
  await api.post(base + "/cognition/configuration", { headers, data: {} });
});
