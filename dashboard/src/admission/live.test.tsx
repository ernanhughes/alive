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
import { LivePane } from "./LivePane";
import admission from "./fixtures/intent-completed.json";
import recommendation from "./fixtures/intent-recommendation.json";
import report from "./fixtures/analysis-report.json";

vi.mock("../api", async () => ({
  ...(await vi.importActual<object>("../api")),
  request: vi.fn(),
}));
const mock = vi.mocked(request);
const consent = {
  id: "consent",
  sha256: "a".repeat(64),
  state: "approved",
  terms: {
    max_calls: 6,
    max_tokens: 200000,
    expires_at: "2099-01-01T00:00:00Z",
    profiles: {},
    disclosure: "approved scope",
  },
};
const exchange = {
  id: admission.id,
  goal: "Review my repository",
  status: "MODEL RESPONSE",
  availability: "available",
  model_calls: 2,
  admission,
  result_admission: admission,
  recommendation,
  report,
  calls: [
    {
      id: "invocation",
      model: "live-model",
      provider: "meta",
      status: "validated",
      latency_ms: 123,
      endpoint: "https://provider.example/v1",
      usage: { total_tokens: 42 },
      provider_receipts: [],
      inference_provenance: "unverified",
    },
  ],
};

function backend(
  history = { consents: [consent], exchanges: [] as unknown[] },
) {
  return async (path: string) => {
    if (path === "/admissions/live") return structuredClone(history);
    if (path.startsWith("/admissions/sources")) return { sources: [] };
    if (path === "/goals") return [];
    if (path === "/admissions/live/ask") return structuredClone(exchange);
    throw new Error("Unexpected request " + path);
  };
}
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it("asks successive goals with one POST each and shows factual model usage and results", async () => {
  mock.mockImplementation(backend());
  render(<LivePane token="token" />);
  await screen.findByText(/6 calls/);
  for (const goal of ["First question", "Second question", "Third question"]) {
    fireEvent.change(screen.getByLabelText("Your goal"), {
      target: { value: goal },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask ALIVE" }));
    await waitFor(() =>
      expect(
        (screen.getByLabelText("Your goal") as HTMLTextAreaElement).value,
      ).toBe(""),
    );
  }
  expect(
    mock.mock.calls.filter((c) => c[3] === "POST").map((c) => c[0]),
  ).toEqual([
    "/admissions/live/ask",
    "/admissions/live/ask",
    "/admissions/live/ask",
  ]);
  expect(screen.getByText("MODEL RESPONSE")).toBeTruthy();
  expect(screen.queryByText("LIVE MODEL")).toBeNull();
  expect(screen.getByText(/42 actual tokens/)).toBeTruthy();
  expect(screen.getByText(/Mean divides by the wrong count/).textContent).toBe(
    report.result.report_markdown,
  );
});

it("opening retained history only uses GET and does not redispatch", async () => {
  mock.mockImplementation(
    backend({ consents: [consent], exchanges: [exchange] }),
  );
  render(<LivePane token="token" />);
  await screen.findByText("Review my repository");
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});

it("keeps AI unavailable visible when there is no consent", async () => {
  mock.mockImplementation(backend({ consents: [], exchanges: [] }));
  render(<LivePane token="token" />);
  await screen.findByText(/NO MODEL CALL/);
  fireEvent.change(screen.getByLabelText("Your goal"), {
    target: { value: "Help" },
  });
  expect(
    (screen.getByRole("button", { name: "Ask ALIVE" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});

it("failed inference is never presented as a model answer", async () => {
  mock.mockImplementation(
    backend({
      consents: [consent],
      exchanges: [
        {
          ...exchange,
          status: "NO MODEL CALL",
          availability: "AI unavailable",
          model_calls: 0,
          calls: [],
          report: null,
          recommendation: null,
          result_admission: null,
        },
      ],
    }),
  );
  render(<LivePane token="token" />);
  await screen.findByRole("alert");
  expect(screen.queryByText("LIVE MODEL")).toBeNull();
});

it("keeps partial reasoning and receipts visible when follow-up authorization is refused", async () => {
  mock.mockImplementation(
    backend({
      consents: [consent],
      exchanges: [
        {
          ...exchange,
          availability: "AI unavailable",
          report: null,
          result_admission: null,
          followup: {
            status: "analysis_not_authorized",
            reason: "budget_exhausted",
            profile: "approved-repository-analysis",
          },
        },
      ],
    }),
  );
  render(<LivePane token="token" />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Follow-up not authorized (budget_exhausted)",
  );
  expect(
    screen.getByText(
      recommendation.record.interpretation.value.primary_objective,
    ),
  ).toBeTruthy();
  expect(screen.getByText(/42 actual tokens/)).toBeTruthy();
  expect(screen.queryByText(/No automatic result:/)).toBeNull();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});

it("clearly labels injected upstream responses and separates requested from observed identity", async () => {
  mock.mockImplementation(
    backend({
      consents: [consent],
      exchanges: [
        {
          ...exchange,
          status: "TEST MODEL RESPONSE",
          calls: exchange.calls.map((c) => ({
            ...c,
            inference_provenance: "injected_transport",
          })),
        },
      ],
    }),
  );
  render(<LivePane token="token" />);
  await screen.findByText("TEST MODEL RESPONSE");
  expect(screen.queryByText("LIVE MODEL")).toBeNull();
  fireEvent.click(screen.getByText(/42 actual tokens/));
  expect(screen.getByText(/Requested model: live-model/)).toBeTruthy();
  expect(
    screen.getByText(/Inference evidence: injected_transport/),
  ).toBeTruthy();
});

it("shows captured-file evidence when the model selects read-only inspection", async () => {
  mock.mockImplementation(
    backend({
      consents: [consent],
      exchanges: [
        {
          ...exchange,
          report: null,
          inspection: {
            source_ref: "capture",
            files: [
              {
                path: "mean.py",
                content: "def mean(values): pass",
                sha256: "abc",
              },
            ],
          },
        },
      ],
    }),
  );
  render(<LivePane token="token" />);
  await screen.findByRole("region", { name: "Captured file evidence" });
  fireEvent.click(screen.getByText("mean.py"));
  expect(screen.getByText("def mean(values): pass")).toBeTruthy();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});
