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
          availability: "available",
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

it("reports internal follow-up failure without calling it an authorization refusal", async () => {
  mock.mockImplementation(
    backend({
      consents: [consent],
      exchanges: [
        {
          ...exchange,
          availability: "available",
          report: null,
          result_admission: null,
          followup: {
            status: "followup_failed",
            reason: "admission_integrity",
            profile: "approved-repository-analysis",
          },
        },
      ],
    }),
  );
  render(<LivePane token="token" />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Follow-up failed (admission_integrity)",
  );
  expect(screen.queryByText(/Follow-up not authorized/)).toBeNull();
  expect(screen.queryByText(/AI unavailable\./)).toBeNull();
  expect(
    screen.getByText(
      recommendation.record.interpretation.value.primary_objective,
    ),
  ).toBeTruthy();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
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

it("continues a retained conversation, displays revisions, and starts a clean conversation", async () => {
  const contextualConsent = {
    ...consent,
    terms: {
      ...consent.terms,
      profiles: { "contextual-reasoning": { disclosure: {} } },
    },
  };
  const previous = { ...exchange, conversation_ref: "conversation-1" };
  const updated = {
    ...previous,
    goal: "Why that problem?",
    report: null,
    context: { items: [], omitted: [] },
    answer: {
      answer: "The divisor adds one.",
      recalled_item_ids: ["finding-1"],
      citations: [],
      uncertainty: [],
      revision: {
        supersedes: ["finding-1"],
        changed: "Zero sums are an exception.",
        rationale: "0 divided by either divisor is 0.",
        still_supported: ["General divisor bug"],
        withdrawn_or_qualified: ["Never correct"],
      },
    },
  };
  const base = backend();
  mock.mockImplementation(async (path, token, body, method) => {
    if (path === "/admissions/live")
      return {
        consents: [contextualConsent],
        exchanges: [previous],
        conversations: [
          {
            id: "conversation-1",
            title: "Mean review",
            consent_ref: consent.id,
            admission_ids: [previous.id],
          },
        ],
      };
    if (path === "/admissions/live/ask") return updated;
    return base(path);
  });
  render(<LivePane token="token" />);
  await screen.findByDisplayValue("Mean review");
  fireEvent.change(screen.getByLabelText("Your goal"), {
    target: { value: "Why that problem?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask ALIVE" }));
  await screen.findByText("The divisor adds one.");
  expect(screen.getByText("Assessment revised")).toBeTruthy();
  expect(
    mock.mock.calls.find((c) => c[0] === "/admissions/live/ask")?.[2],
  ).toMatchObject({ conversation_ref: "conversation-1" });
  fireEvent.click(
    screen.getByRole("button", { name: "Start new conversation" }),
  );
  expect(screen.queryByText("The divisor adds one.")).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "Refresh AI and history" }),
  );
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Conversation") as HTMLSelectElement).value,
    ).toBe("new"),
  );
});

it("reuses the same request identity after losing a first-turn response", async () => {
  const contextualConsent = {
    ...consent,
    terms: {
      ...consent.terms,
      profiles: { "contextual-reasoning": { disclosure: {} } },
    },
  };
  let attempts = 0;
  const base = backend();
  mock.mockImplementation(async (path) => {
    if (path === "/admissions/live")
      return {
        consents: [contextualConsent],
        exchanges: [],
        conversations: [],
      };
    if (path === "/admissions/live/conversations")
      return {
        id: "created-conversation",
        title: "Review",
        consent_ref: consent.id,
      };
    if (path === "/admissions/live/ask") {
      if (attempts++ === 0) throw new Error("Response lost after dispatch");
      return { ...exchange, conversation_ref: "created-conversation" };
    }
    return base(path);
  });
  render(<LivePane token="token" />);
  await screen.findByLabelText("Conversation");
  fireEvent.change(screen.getByLabelText("Your goal"), {
    target: { value: "Review" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask ALIVE" }));
  await screen.findByRole("alert");
  await waitFor(() =>
    expect(
      (screen.getByRole("button", { name: "Ask ALIVE" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "Ask ALIVE" }));
  await screen.findByText("Review my repository");
  const asks = mock.mock.calls.filter((c) => c[0] === "/admissions/live/ask");
  expect(asks).toHaveLength(2);
  expect(asks[0][2]).toEqual(asks[1][2]);
  expect(
    mock.mock.calls.filter((c) => c[0] === "/admissions/live/conversations"),
  ).toHaveLength(1);
});

function selectionHistory(selection: unknown, lessons: unknown[]) {
  const contextualConsent = {
    ...consent,
    terms: {
      ...consent.terms,
      profiles: { "contextual-reasoning": { disclosure: {} } },
    },
  };
  const retained = {
    ...exchange,
    conversation_ref: "conversation-1",
    report: null,
    context: { items: [], omitted: [] },
    answer: {
      answer: "Reviewed against the supplied source.",
      recalled_item_ids: [],
      citations: [],
      uncertainty: [],
      revision: null,
      lesson_ids_used: [],
    },
    selection,
  };
  const base = backend();
  mock.mockImplementation(async (path, token, body, method) => {
    if (path === "/admissions/live")
      return {
        consents: [contextualConsent],
        exchanges: [retained],
        conversations: [
          {
            id: "conversation-1",
            title: "Review",
            consent_ref: consent.id,
            admission_ids: [retained.id],
          },
        ],
        adaptation: { experiences: [], lessons },
      };
    return base(path);
  });
}

const lesson = {
  id: "row-1",
  lesson_id: "lesson-1",
  state: "active",
  qualification: "provisional",
  proposal: { strategy: "Check negative inputs against floor semantics." },
  utility: { state: "unproven", paired_gains: 0, paired_losses: 0, applications: 0 },
};

it("shows which lesson was supplied, why, its standing, the self-report and the independent outcome", async () => {
  selectionHistory(
    {
      policy: "selective-adaptation/v1",
      decision: "selected",
      no_lesson_reason: null,
      task_mechanisms: ["numeric.signed_values"],
      override: null,
      received: ["row-1"],
      reported_used: ["row-1"],
      selected: [{ item_id: "row-1", lesson_id: "lesson-1", version: 3, tier: "unproven" }],
      candidates: [
        {
          lesson_id: "lesson-1",
          status: "selected",
          reasons: [],
          overlap: ["numeric.signed_values"],
          tier: "unproven",
          supporting_outcomes: [],
        },
        {
          lesson_id: "lesson-2",
          status: "excluded",
          reasons: ["no_mechanism_overlap"],
          overlap: [],
          tier: "unproven",
          supporting_outcomes: [],
        },
      ],
      context_bytes: 612,
      independent_outcome: { passed: true, verifier: "frozen-executable-fixture/v2" },
    },
    [lesson],
  );
  render(<LivePane token="token" />);
  await screen.findByText(/1 lesson\(s\) supplied/);
  expect(screen.getByText(/Lesson v3 \(unproven\)/)).toBeTruthy();
  expect(screen.getByText(/now provisional \(no measured benefit yet\)/)).toBeTruthy();
  expect(screen.getByText(/self-report, not proof/)).toBeTruthy();
  expect(screen.getByText(/Independent check: passed/)).toBeTruthy();
  expect(screen.getByText(/different mechanism/)).toBeTruthy();
});

it("explains a deliberate decision to use no lesson and shows demoted standing", async () => {
  selectionHistory(
    {
      policy: "selective-adaptation/v1",
      decision: "none",
      no_lesson_reason: "no_applicable_lesson",
      task_mechanisms: ["numeric.rounding"],
      override: null,
      received: [],
      reported_used: [],
      selected: [],
      candidates: [
        {
          lesson_id: "lesson-1",
          status: "excluded",
          reasons: ["empirically_demoted"],
          overlap: ["numeric.rounding"],
          tier: "unproven",
          supporting_outcomes: [],
        },
      ],
      context_bytes: 2,
      independent_outcome: null,
    },
    [{ ...lesson, utility: { state: "demoted", paired_gains: 0, paired_losses: 1, applications: 1 } }],
  );
  render(<LivePane token="token" />);
  await screen.findByText(/none supplied/);
  expect(screen.getByText(/reasoned from the evidence alone/)).toBeTruthy();
  expect(screen.getAllByText(/contradicted by measured outcomes/).length).toBeGreaterThan(0);
  expect(screen.getByText(/demoted on counterevidence/)).toBeTruthy();
  expect(screen.queryByText(/Independent check/)).toBeNull();
});


it("keeps an incomplete task response visible and separates structure from semantic verification", async () => {
  const candidate = {
    candidate_id: "original-candidate", raw_text: "original partial JSON", candidate: { explanation: "Useful partial result" },
    contract: { case_ids: ["c1", "c2"] }, transport_completed: true, response_schema_valid: true,
    schema_valid: true, task_complete: false, semantically_verified: false,
    completion: { all_cases_addressed: false, contains_undetermined: false, errors: [{ field: "predictions", case_id: "c2" }] },
  };
  mock.mockImplementation(backend({consents:[consent], exchanges:[{
    ...exchange, report: null, task_review: { original:candidate, effective:candidate,
      repair:null, repair_attempted:false, repair_successful:false, additional_model_calls:0 },
  }]}));
  render(<LivePane token="token" />);
  await screen.findByText("Code-review contract: incomplete");
  expect(screen.getByText(/Original response schema valid: yes/)).toBeTruthy();
  expect(screen.getByText(/Every declared case addressed .*: no/)).toBeTruthy();
  expect(screen.getByText("Independent semantic verification: not performed")).toBeTruthy();
  expect(screen.getByText(/Repair: not attempted/)).toBeTruthy();
  fireEvent.click(screen.getByText("Original candidate, omissions and repair evidence"));
  expect(screen.getByText(/original partial JSON/)).toBeTruthy();
});

it("keeps code review opt-in and blocks asking through an old session", async () => {
  mock.mockImplementation(backend());
  render(<LivePane token="token" />);
  await screen.findByText(/6 calls/);
  expect((screen.getByLabelText("Response contract") as HTMLSelectElement).value).toBe("general_contextual");
  fireEvent.change(screen.getByLabelText("Response contract"), { target:{value:"code_review"} });
  fireEvent.change(screen.getByLabelText("Your goal"), { target:{value:"Review named cases"} });
  expect((screen.getByRole("button", {name:"Ask ALIVE"}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Configure and approve a session with this task contract/)).toBeTruthy();
  expect((screen.getByLabelText(/Request one completion repair/) as HTMLInputElement).checked).toBe(false);
});
