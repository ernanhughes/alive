/* @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./api";
import { DemoTourPane, isBound } from "./DemoTour";
import type { TourRun, TourStep } from "./DemoTour";

vi.mock("./api", () => ({ request: vi.fn() }));

const LABEL = "DETERMINISTIC LOCAL FIXTURE — NOT LIVE META";
const GOAL = "goal-1";
const MEMORY = "memory-1";
const LATER_SHA = "a".repeat(64);
const NEUTRAL_SHA = "b".repeat(64);

const info = (over = {}) => ({
  enabled: true,
  reason: "",
  label: LABEL,
  labels: { fixture_provider: LABEL, backend_row: "Persisted by ALIVE's public API" },
  consent_text: "Starting authorises ONE local fixture comparison of the pinned sources.",
  sources: [
    { id: "python-3.11", mirror_path: "/demo-live-01/python-3.11.html", kind: "local_mirror", mirror_html_sha256: "c".repeat(64) },
  ],
  boot: { id: "boot-1", started_at: "2026-10-29T00:00:00Z" },
  runs: [],
  ...over,
});

const step = (n: number, key: string, evidence: Record<string, unknown>, provenance = ["backend_row"]): TourStep => ({
  n, key, title: `title ${key}`, summary: `summary ${key}`, status: "ok",
  at: "2026-10-29T00:00:00Z", provenance, evidence,
});

const run = (over: Partial<TourRun> = {}, pairs: { compare?: object; abstention?: object } = {}): TourRun => ({
  run_id: "run-1",
  status: "completed",
  number: 1,
  label: LABEL,
  consent_text: "consent",
  goal_id: GOAL,
  error: null,
  steps: [
    step(1, "save_memory", { memory_id: MEMORY }),
    step(2, "observe_later", { text_sha256: LATER_SHA }),
    step(3, "compare", {
      historical_quote: "Return the current UTC date and time, with tzinfo None.",
      supersession_basis_quote: "Deprecated since version 3.12.",
      bound_pair: { goal_id: GOAL, historical_memory_id: MEMORY, current_sha256: LATER_SHA, ...pairs.compare },
    }, ["fixture_provider", "backend_row"]),
    step(4, "abstention", {
      text_sha256: NEUTRAL_SHA,
      abstained: true,
      bound_pair: { goal_id: GOAL, historical_memory_id: MEMORY, current_sha256: NEUTRAL_SHA, ...pairs.abstention },
    }, ["fixture_provider"]),
    step(5, "before_withdrawal", { memory_active: true, connection_ids: ["c1"], analysis_ids: ["a1", "a2"], retrieval_memory_ids: [MEMORY] }),
    step(6, "after_withdrawal", { memory_active: false, connection_ids: [], analysis_ids: [], retrieval_memory_ids: [] }),
  ],
  live: { memory_active: false, connection_ids: [], analysis_ids: [], retrieval_memory_ids: [], retrieval_abstained: true },
  audit: { rows: [{ label: "memory", id: "12345678-aaaa", kind: "research_memory", status: "withdrawn" }], withdrawal_events: [{ sequence_number: 9 }], physically_deleted: false },
  boot: { id: "boot-1", started_at: "2026-10-29T00:00:00Z" },
  ...over,
});

const mocked = vi.mocked(request);
const route = (responses: Record<string, unknown>) =>
  mocked.mockImplementation(async (path: string) => {
    if (!(path in responses)) throw new Error("unexpected " + path);
    return responses[path] as never;
  });

beforeEach(() => {
  mocked.mockReset();
});
afterEach(cleanup);

describe("DemoTourPane", () => {
  it("is unavailable, and hides all fixture content, when the runtime disables it", async () => {
    route({ "/demo-tour": info({ enabled: false, reason: "Local fixture providers are disabled on this runtime." }) });
    render(<DemoTourPane token="t" revealDelayMs={0} />);
    expect(await screen.findByText("Demonstration unavailable")).toBeTruthy();
    expect(screen.getByText(/fixture providers are disabled/)).toBeTruthy();
    expect(screen.queryByText(LABEL)).toBeNull();
    expect(screen.queryByRole("button", { name: "Start demonstration" })).toBeNull();
    expect(mocked).toHaveBeenCalledTimes(1);
  });

  it("starts one run, shows each recorded step and the before/after result", async () => {
    route({ "/demo-tour": info(), "/demo-tour/runs": run() });
    render(<DemoTourPane token="tok" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    await screen.findByText("title before_withdrawal");
    expect(mocked).toHaveBeenCalledWith("/demo-tour/runs", "tok", { pause_before_withdrawal: false });
    for (const key of ["save_memory", "compare", "abstention", "after_withdrawal"]) {
      expect(screen.getByText(`title ${key}`)).toBeTruthy();
    }
    expect(screen.getAllByText(LABEL).length).toBeGreaterThan(0);
    expect(screen.getByText(/Deprecated since version 3.12/)).toBeTruthy();
    const table = screen.getByLabelText("Before and after withdrawal");
    expect(table.textContent).toContain("Findings returned10");
    expect(table.textContent).toContain("Comparisons and abstentions returned20");
    expect(screen.getByLabelText("Audit view").textContent).toContain("nothing was physically deleted");
    // The only mention of Meta is the explicit "NOT LIVE META" fixture label.
    const text = document.body.textContent || "";
    expect(text.replace(new RegExp(LABEL, "g"), "")).not.toMatch(/live meta/i);
    expect(text).not.toMatch(/model reasoned|verified (true|fact)/i);
  });

  it("sends the pause option and offers the withdrawal as a separate real call", async () => {
    const paused = run({ status: "paused", steps: run().steps.slice(0, 5), audit: null });
    route({ "/demo-tour": info(), "/demo-tour/runs": paused, "/demo-tour/runs/run-1/withdraw": run() });
    render(<DemoTourPane token="tok" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByLabelText(/Pause before withdrawal/));
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    expect(await screen.findByRole("button", { name: "Withdraw the original memory" })).toBeTruthy();
    expect(mocked).toHaveBeenCalledWith("/demo-tour/runs", "tok", { pause_before_withdrawal: true });
    expect(screen.queryByLabelText("Before and after withdrawal")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw the original memory" }));
    await waitFor(() =>
      expect(mocked).toHaveBeenCalledWith("/demo-tour/runs/run-1/withdraw", "tok", {}),
    );
    await screen.findByLabelText("Before and after withdrawal");
  });

  it("does not display a comparison bound to a different memory", async () => {
    route({ "/demo-tour": info(), "/demo-tour/runs": run({}, { compare: { historical_memory_id: "someone-else" } }) });
    render(<DemoTourPane token="t" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    await screen.findByText("title compare");
    expect(screen.getByText(/this result is not bound to this run's source pair/)).toBeTruthy();
    expect(screen.queryByText(/Deprecated since version 3.12/)).toBeNull();
  });

  it("does not display an abstention for a different source hash", async () => {
    route({ "/demo-tour": info(), "/demo-tour/runs": run({}, { abstention: { current_sha256: LATER_SHA } }) });
    render(<DemoTourPane token="t" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    await screen.findByText("title abstention");
    expect(screen.getByText(/this abstention is not bound to this run's source pair/)).toBeTruthy();
  });

  it("fails closed: shows the stop reason and no result table", async () => {
    const failed = run({
      status: "failed",
      error: "POST /research/outbound/authorize refused (403): Claim fixture provider is disabled",
      steps: [{ ...step(1, "run", {}), status: "failed", title: "Stopped (fail closed)" }],
      live: null,
      audit: null,
    });
    route({ "/demo-tour": info(), "/demo-tour/runs": failed });
    render(<DemoTourPane token="t" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    expect(await screen.findByText(/Stopped without a result/)).toBeTruthy();
    expect(screen.queryByLabelText("Before and after withdrawal")).toBeNull();
    expect(screen.queryByLabelText("Audit view")).toBeNull();
  });

  it("surfaces an API refusal instead of inventing a result", async () => {
    mocked.mockImplementation(async (path: string) => {
      if (path === "/demo-tour") return info() as never;
      throw new Error("Demonstration is disabled");
    });
    render(<DemoTourPane token="t" revealDelayMs={0} />);
    await screen.findByText(/Starting authorises/);
    fireEvent.click(screen.getByRole("button", { name: "Start demonstration" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Demonstration is disabled");
    expect(screen.queryByText("title compare")).toBeNull();
  });
});

describe("isBound", () => {
  it("requires goal, memory and source hash to agree", () => {
    expect(isBound(run(), "compare", "observe_later")).toBe(true);
    expect(isBound(run({ goal_id: null }), "compare", "observe_later")).toBe(false);
    expect(isBound(run({}, { compare: { goal_id: "other" } }), "compare", "observe_later")).toBe(false);
    expect(isBound(run({}, { compare: { current_sha256: "z" } }), "compare", "observe_later")).toBe(false);
    expect(isBound(run({ steps: [] }), "compare", "observe_later")).toBe(false);
  });
});
