/* @vitest-environment jsdom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "./api";
import { LivingPane } from "./Living";

vi.mock("./api", () => ({ request: vi.fn() }));

const choice = {
  action: "retrieve",
  policy_version: 1,
  policy_hash: "before-hash",
  reason: "Highest observed mean reward; unseen actions use zero prior.",
  predictions: {
    monitor: { n: 1, mean: -0.5, status: "observed mean" },
    retrieve: { n: 0, mean: 0, status: "unknown; zero prior" },
  },
};

const journey = {
  id: "journey-1",
  provider: "mock",
  status: "completed",
  data: {
    stage: "learned",
    phases: [],
    ledger: [],
    tool_log: [
      { episode: 1, operation: "observe", at: "2026-10-27T00:00:00Z" },
      { episode: 1, operation: "retrieve", at: "2026-10-27T00:00:01Z" },
      { episode: 1, operation: "feedback", at: "2026-10-27T00:00:02Z" },
    ],
    grant: "controlled local habitat read/click only",
    max_calls: 2,
    max_tools: 6,
    max_micro_usd: 150000,
  },
  transitions: [
    {
      id: "transition-1",
      episode: 1,
      data: {
        episode: 1,
        state: {
          claim: "32",
          recent_event: "source_replaced",
          feature_hash: "feature-hash",
        },
        choice,
        initial_policy_counterfactual: choice,
        observation: { text: "Claim: Aster endurance_hours 32;" },
        evidence: { text: "Instrument reading: 20 hours;" },
        sources: [
          {
            id: "measurement:journey-1:1",
            value: "20",
            provenance: "Visible current Chrome DOM after permitted retrieval",
          },
        ],
        relevant_experience: [
          {
            id: "prior-transition-12345678",
            action: "monitor",
            reward: -0.5,
            outcome: { safe_abstention: true },
          },
        ],
        feedback: { text: "Feedback measurement: 20 hours;" },
        model_output: {
          summary: "The current measurement is 20, not 32.",
          recommendation: "proceed",
        },
        reward: 0.85,
        prediction_error: 0.85,
        memory_ids: ["prior-transition-12345678"],
        outcome: {
          resolved: true,
          safe_abstention: false,
          measurement: "20",
          factual_correct: true,
          conclusion_contract_correct: true,
          source_value: "20",
          feedback_confirms_source: true,
        },
        before_hash: "before-hash",
        after_hash: "after-hash",
        policy_after: { version: 2 },
        next_choice: choice,
      },
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Living provenance", () => {
  it("shows the reason, recalled experience, executed operations and source/feedback checks", async () => {
    vi.mocked(request).mockImplementation(async (path: string) => {
      if (path === "/living") {
        return {
          policy: { version: 1 },
          active: false,
          journeys: [
            { id: "journey-1", provider: "mock", status: "completed", episodes: 1 },
          ],
        } as never;
      }
      if (path === "/living/journeys/journey-1") return journey as never;
      throw new Error("Unexpected request: " + path);
    });

    render(<LivingPane token="test-token" />);

    await waitFor(() => expect(screen.getByTestId("source-corroboration")).toBeTruthy());
    expect(screen.getByTestId("recalled-experience").textContent).toContain("monitor");
    expect(screen.getByTestId("source-corroboration").textContent).toContain(
      "Feedback matches the source",
    );
    expect(screen.getByText(/Highest observed mean reward/)).toBeTruthy();
    expect(
      screen.getByText(/Governor-permitted operations: observe → retrieve → feedback/),
    ).toBeTruthy();
  });
});
