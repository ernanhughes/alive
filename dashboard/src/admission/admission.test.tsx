/* @vitest-environment jsdom */
import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { request } from "../api";
import { AdmissionPane } from "./AdmissionPane";
import { checkedAdmission } from "./contracts";
import completed from "./fixtures/completed.json";
import pending from "./fixtures/pending.json";
import analysisCompleted from "./fixtures/analysis-completed.json";
import analysisPending from "./fixtures/analysis-pending.json";
import analysisReport from "./fixtures/analysis-report.json";

vi.mock("../api", async () => ({
  ...(await vi.importActual<object>("../api")),
  request: vi.fn(),
}));
const mock = vi.mocked(request);
// The recorded grant expires minutes after recording, so the live clock must not decide the test.
const approved = structuredClone(pending);
approved.authorization_state = "approved";
approved.state = "approved";
approved.terms.proposed_grant_data.expires_at = new Date(
  Date.now() + 300_000,
).toISOString();
function respond(row: unknown) {
  return async (path: string) => {
    if (path.startsWith("/admissions/sources")) return { sources: [] };
    if (path === "/goals") return [];
    if (path.startsWith("/admissions/profile"))
      return { recipe_sha256: "0".repeat(64), recipe: {} };
    if (path === "/admissions") return { admissions: [] };
    return structuredClone(row);
  };
}
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  window.location.hash = "";
});
it("shows a pending review with the local confirmation and no start authority", async () => {
  window.location.hash = "#admission?id=" + pending.id;
  mock.mockImplementation(respond(pending));
  render(<AdmissionPane token="token" />);
  await screen.findByText("Exact owner review");
  expect(
    screen.getByText(new RegExp("--confirm-sha256 " + pending.review_sha256)),
  ).toBeTruthy();
  expect(
    (
      screen.getByRole("button", {
        name: "Start approved inspection",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(screen.queryByRole("button", { name: /approve$/i })).toBeNull();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});
it("starts only after local approval and sends the exact review digest", async () => {
  window.location.hash = "#admission?id=" + approved.id;
  mock.mockImplementation(async (path, token, body, method) =>
    method === "POST"
      ? structuredClone(completed)
      : respond(approved)(path as string),
  );
  render(<AdmissionPane token="token" />);
  const start = (await screen.findByRole("button", {
    name: "Start approved inspection",
  })) as HTMLButtonElement;
  await waitFor(() => expect(start.disabled).toBe(false));
  fireEvent.click(start);
  await screen.findByText(/COMPLETED/);
  const writes = mock.mock.calls.filter((c) => c[3] === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toBe(`/admissions/${approved.id}/start`);
  expect(writes[0][2]).toEqual({ review_sha256: approved.review_sha256 });
});
it("rejects a review that exceeds the no-inference profile", () => {
  for (const change of [
    { max_model_calls: 1 },
    { max_output_tokens: 10 },
    { outbound_approved: true },
    { wall_seconds: 600 },
  ]) {
    const row = structuredClone(pending) as typeof pending;
    Object.assign(row.terms.proposed_grant_data, change);
    expect(() => checkedAdmission(row as never)).toThrow(/profile/);
  }
  const forged = structuredClone(pending) as typeof pending;
  forged.authorization_state = "granted";
  expect(() => checkedAdmission(forged as never)).toThrow(/invalid/);
});

const analysisApproved = structuredClone(analysisPending);
analysisApproved.authorization_state = "approved";
analysisApproved.state = "approved";
analysisApproved.terms.proposed_grant_data.expires_at = new Date(
  Date.now() + 300_000,
).toISOString();
function respondAnalysis(row: unknown, report: unknown = analysisReport) {
  return async (path: string) => {
    if (path.endsWith("/report")) return structuredClone(report);
    return respond(row)(path);
  };
}
it("shows exactly what leaves the machine and offers no way to start before local approval", async () => {
  window.location.hash = "#admission?id=" + analysisPending.id;
  mock.mockImplementation(respondAnalysis(analysisPending));
  render(<AdmissionPane token="token" />);
  await screen.findByText("Disclosure to the model provider");
  expect(screen.getByText(/model call, at most/)).toBeTruthy();
  expect(screen.getByText("Leaves this machine")).toBeTruthy();
  expect(screen.getAllByText(/calc\.py/).length).toBeGreaterThan(0);
  expect(
    (
      screen.getByRole("button", {
        name: "Start approved inspection",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});
it("fetches and shows the report as inert text after a completed analysis", async () => {
  const hostile = structuredClone(analysisReport);
  hostile.result.report_markdown =
    "# Repository analysis\n<img src=x onerror=alert(1)> [x](javascript:alert(1))";
  window.location.hash = "#admission?id=" + analysisCompleted.id;
  mock.mockImplementation(respondAnalysis(analysisCompleted, hostile));
  const { container } = render(<AdmissionPane token="token" />);
  await screen.findByText("Analysis report");
  const pre = container.querySelector("pre.admission-report")!;
  expect(pre.textContent).toContain("<img src=x onerror=alert(1)>");
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("a[href^='javascript']")).toBeNull();
  expect(screen.getByText(/Independent verification: none/)).toBeTruthy();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});
it("starts an approved analysis only with the exact review digest", async () => {
  window.location.hash = "#admission?id=" + analysisApproved.id;
  mock.mockImplementation(async (path, token, body, method) =>
    method === "POST"
      ? structuredClone(analysisCompleted)
      : respondAnalysis(analysisApproved)(path as string),
  );
  render(<AdmissionPane token="token" />);
  const start = (await screen.findByRole("button", {
    name: "Start approved inspection",
  })) as HTMLButtonElement;
  await waitFor(() => expect(start.disabled).toBe(false));
  fireEvent.click(start);
  await screen.findByText("Analysis report");
  const writes = mock.mock.calls.filter((c) => c[3] === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][2]).toEqual({
    review_sha256: analysisApproved.review_sha256,
  });
});
it("rejects reviews that widen either profile", () => {
  const changes: ((row: typeof analysisPending) => void)[] = [
    (r) => (r.terms.proposed_grant_data.max_model_calls = 2),
    (r) => (r.terms.proposed_grant_data.outbound_approved = false),
    (r) => (r.terms.proposed_grant_data.max_output_tokens = 4096),
    (r) => (r.terms.model_disclosure.leaves_host = false),
    (r) => (r.terms.model_disclosure.max_model_calls = 2),
    (r) => delete (r.terms as { model_disclosure?: unknown }).model_disclosure,
    (r) => ((r.terms as { profile: string }).profile = "approved-anything"),
  ];
  for (const change of changes) {
    const row = structuredClone(analysisPending);
    change(row);
    expect(() => checkedAdmission(row as never)).toThrow(/profiles/);
  }
  const inspection = structuredClone(pending) as Record<string, any>;
  inspection.terms.model_disclosure = analysisPending.terms.model_disclosure;
  expect(() => checkedAdmission(inspection as never)).toThrow(/profiles/);
  expect(
    checkedAdmission(structuredClone(analysisPending) as never),
  ).toBeTruthy();
});
