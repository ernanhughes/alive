/* @vitest-environment jsdom */
import React from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { request } from "../api";
import { BespokePane } from "./BespokePane";
import type { Recommendation } from "./contracts";
import recorded from "./fixtures/recommendation.json";

vi.mock("../api", () => ({ request: vi.fn() }));
const mock = vi.mocked(request);
const context = {
  approval_ref: "approved",
  goal_ref: "goal",
  investigation_ref: "inquiry",
  source_ref: "capture",
  source_sha256: "0".repeat(64),
};
function respond(path: string): unknown {
  if (path === "/bespoke/recipes") return { recipes: [] };
  if (path === "/bespoke/contexts") return { contexts: [context] };
  if (path === "/bespoke/recommendations") return { recommendations: [] };
  if (path.endsWith("/runs")) return { runs: [] };
  return structuredClone(recorded);
}
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  window.location.hash = "";
});
it("handles empty context and catalogue without an authorization control", async () => {
  mock.mockImplementation(async (path) =>
    path === "/bespoke/contexts" ? { contexts: [] } : respond(path),
  );
  render(<BespokePane token="token" />);
  await screen.findByText("The recipe catalogue is empty.");
  expect(screen.getByText(/No approved captured context/)).toBeTruthy();
  expect(
    (
      screen.getByRole("button", {
        name: "Recommend procedure",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(
    screen.queryByRole("button", { name: /Authorize|Execute/ }),
  ).toBeNull();
});
it("shows recorded rationale and the existing graph with no writes on history reads", async () => {
  window.location.hash = "#bespoke?recommendation=" + recorded.id;
  mock.mockImplementation(async (path) => respond(path));
  render(<BespokePane token="token" />);
  await screen.findByText("HISTORICAL RECOMMENDATION");
  expect(
    await screen.findByRole("region", { name: "Workflow graph" }),
  ).toBeTruthy();
  expect(
    screen.getByText(/1 distinct eligible execution contracts/),
  ).toBeTruthy();
  expect(screen.getByText(/Authorization unavailable/)).toBeTruthy();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});
it("posts explicit objective and constraints without accepting a recipe or granting authority", async () => {
  mock.mockImplementation(async (path) => respond(path));
  render(<BespokePane token="token" />);
  await waitFor(() =>
    expect(screen.getByRole("option", { name: /capture/ })).toBeTruthy(),
  );
  fireEvent.change(screen.getByLabelText("Approved capture"), {
    target: { value: "approved" },
  });
  fireEvent.change(screen.getByLabelText("Requested outcome"), {
    target: { value: "Compare these claims" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Recommend procedure" }));
  await screen.findByText("SELECTION RECORDED");
  const writes = mock.mock.calls.filter((c) => c[3] === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toBe("/bespoke/recommend");
  expect(writes[0][2]).toMatchObject({
    objective: {
      kind: "compare_claims",
      requested_outcome: "Compare these claims",
    },
    constraints: { max_model_calls: 0, outbound_allowed: false },
  });
});
it("discards late selection responses when the objective changes", async () => {
  let resolve!: (value: unknown) => void;
  mock.mockImplementation(async (path) =>
    path === "/bespoke/recommend"
      ? await new Promise((r) => {
          resolve = r;
        })
      : respond(path),
  );
  render(<BespokePane token="token" />);
  await screen.findByRole("option", { name: /capture/ });
  fireEvent.change(screen.getByLabelText("Approved capture"), {
    target: { value: "approved" },
  });
  fireEvent.change(screen.getByLabelText("Requested outcome"), {
    target: { value: "First" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Recommend procedure" }));
  await waitFor(() => expect(resolve).toBeDefined());
  fireEvent.change(screen.getByLabelText("Requested outcome"), {
    target: { value: "Second" },
  });
  await act(async () => resolve(recorded));
  expect(screen.queryByText("SELECTION RECORDED")).toBeNull();
});
it("renders malicious descriptions as text and displays honest abstention", async () => {
  const hostile = structuredClone(recorded) as Recommendation;
  hostile.selection.state = "abstained";
  hostile.selection.selected_recipe_sha256 = null;
  hostile.selection.candidates[0].recipe.name = "<img src=x onerror=alert(1)>";
  window.location.hash = "#bespoke?recommendation=" + recorded.id;
  mock.mockImplementation(async (path) =>
    path.startsWith("/bespoke/recommendations/") && !path.endsWith("/runs")
      ? hostile
      : respond(path),
  );
  const view = render(<BespokePane token="token" />);
  await screen.findByText("No feasible procedure");
  expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy();
  expect(view.container.querySelector("img")).toBeNull();
});
it("reports backend outages and forgets prior credentials and data", async () => {
  mock.mockRejectedValue(new Error("offline"));
  const view = render(<BespokePane token="old" />);
  await screen.findByRole("alert");
  mock.mockImplementation(async (path) => respond(path));
  view.rerender(<BespokePane token="new" />);
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(mock.mock.calls.slice(-3).every((c) => c[1] === "new")).toBe(true);
});
