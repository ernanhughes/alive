/* @vitest-environment jsdom */
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { request } from "../api";
import { WorkflowsPane } from "./WorkflowsPane";
import { WorkflowGraph } from "./WorkflowGraph";
import {
  ArtifactPanel,
  PiReceiptPanel,
  ValidationView,
} from "./StageInspector";
import { RunComparison } from "./RunComparison";
import { useRecording } from "./useRecording";
import {
  assertRecording,
  layout,
  link,
  parseLink,
  replayStates,
  text,
  timestamp,
  totals,
} from "./model";
import type { Artifact, Recording } from "./contracts";

it("shows a captured-evidence report as inert text with its validation distinctions", () => {
  const value = {
    artifact_id: "synthetic", sha256: "hash", run_id: "run", stage_id: "record",
    definition_sha256: "definition", workflow_completed: true, run_status: "COMPLETED",
    terminal_reason: null, source_status: "unchanged", independent_feedback: false,
    intelligence_episode_id: null, evidence_refs: [], context_provenance: {},
    result: { report_markdown: "Semantic support: unverified. Independent verification: none.\n<img src=x onerror=alert(1)>" },
    assessment: { semantic_support: "unverified", independent_verification: false, task_outcome: "unknown" },
  } as Artifact;
  const { container } = render(<ArtifactPanel value={value} />);
  const report = screen.getByRole("region", { name: "Evidence report" });
  expect(report.textContent).toContain("Semantic support: unverified");
  expect(report.textContent).toContain("<img src=x onerror=alert(1)>");
  expect(container.querySelector("img")).toBeNull();
});

vi.mock("../api", () => ({ request: vi.fn() }));
const ID = "11111111-1111-1111-1111-111111111111",
  OTHER = "22222222-2222-2222-2222-222222222222";
const validation = {
  contract_status: "passed",
  structural_status: "passed",
  reference_identity_status: "passed",
  semantic_status: "unverified",
  independent_verification: false,
};
function fixture(id = ID): Recording {
  return {
    run: {
      id,
      workflow: {
        name: "example",
        version: 2,
        definition_id: "def",
        definition_sha256: "hash",
      },
      status: "COMPLETED",
      terminal: true,
      terminal_reason: "required_stages_completed",
      created_at: "2026-10-31T01:00:00Z",
      started_at: null,
      finished_at: null,
      goal_id: null,
      input_ref: "event:approved",
      input_sha256: "input",
      authorization_ref: "event:grant",
      budget: {},
    },
    definition: {
      id: "def",
      name: "example",
      version: 2,
      title: "Example workflow",
      description: "A bounded recipe",
      status: "active",
      definition_sha256: "hash",
      integrity: { verified: true },
      definition: {
        stages: [
          {
            id: "prepare",
            title: "Prepare",
            type: "deterministic",
            operation: "context.prepare",
            depends_on: [],
            inputs: {},
            output_schema: {},
            limits: { timeout_seconds: 2 },
          },
        ],
        limits: {},
      },
    },
    graph: {
      name: "example",
      version: 2,
      definition_sha256: "hash",
      nodes: [
        {
          id: "prepare",
          title: "Prepare",
          type: "deterministic",
          operation: "context.prepare",
          available: true,
        },
      ],
      edges: [],
    },
    stages: [
      {
        id: "attempt-" + id,
        run_id: id,
        stage_id: "prepare",
        attempt: 1,
        type: "deterministic",
        operation: "context.prepare",
        state: "COMPLETED",
        terminal: true,
        uncertainty: "none",
        error_category: null,
        input_ref: null,
        input_sha256: null,
        output_ref: "event:output",
        output_sha256: "outputhash",
        pi_run_id: null,
        model_invocation_id: null,
        evidence_refs: ["source"],
        validation,
        model_requested: null,
        usage: null,
        cost_usd: null,
        started_at: null,
        finished_at: null,
        duration_seconds: null,
      },
    ],
    timeline: {
      run_id: id,
      definition_id: "def",
      definition_sha256: "hash",
      events: [
        {
          sequence: 1,
          event_type: "workflow.stage.claimed",
          occurred_at: "2026-10-31T01:00:00Z",
          run_id: id,
          stage_id: "prepare",
          attempt_id: "attempt-" + id,
          pi_run_id: null,
          output_ref: null,
          status: null,
        },
      ],
      next_after: 1,
      has_more: false,
      complete_transition_history: false,
      history_note:
        "Recorded events only; interrupted transitions not retained.",
    },
  };
}
function install(records = [fixture()]) {
  vi.mocked(request).mockImplementation(async (path) => {
    if (path === "/workflow-operations")
      return {
        operations: [
          { id: "context.prepare", available: true, executable: true },
        ],
      };
    if (path === "/workflows")
      return {
        workflows: [
          {
            name: "example",
            title: "Example workflow",
            latest_version: 2,
            latest_status: "active",
            versions: [
              {
                version: 2,
                status: "active",
                definition_sha256: "hash",
                stage_count: 1,
              },
              {
                version: 1,
                status: "superseded",
                definition_sha256: "older",
                stage_count: 1,
              },
            ],
          },
        ],
      };
    const r = records.find((r) => path.includes(r.run.id)) || records[0];
    if (path.endsWith("/inspection"))
      return {
        run: r.run,
        definition: r.definition,
        graph: r.graph,
        pi_links: r.pi_links,
      };
    if (path.endsWith("/stages")) return { run_id: r.run.id, stages: r.stages };
    if (path.includes("/timeline")) return r.timeline;
    if (path.startsWith("/workflow-runs?"))
      return { runs: records.map((r) => r.run) };
    if (path.endsWith("/graph")) return r.graph;
    if (path.startsWith("/workflows/")) return r.definition;
    throw new Error("Unexpected API path " + path);
  });
}
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
  window.location.hash = "";
});
describe("bounded identifiers and truthful projections", () => {
  it("roundtrips deep links without credentials or action parameters", () => {
    const s = {
      workflow: "research-review",
      version: 2,
      run: ID,
      stage: "analyze",
    };
    expect(parseLink(link(s))).toEqual(s);
    for (const h of [
      "#workflows?workflow=x&version=1&token=secret",
      "#workflows?workflow=x&version=0",
      "#workflows?workflow=x&version=1000001",
      "#workflows?workflow=javascript:alert(1)&version=1",
      "#workflows?workflow=x&version=1&run=bad",
      "#workflows?workflow=x&version=1&stage=<script>",
      "#workflows?workflow=x&version=1&version=2",
    ])
      expect(parseLink(h)).toBeNull();
  });
  it("lays out real branches and refuses cycles/missing nodes", () => {
    const g = fixture().graph;
    g.nodes.push(
      { ...g.nodes[0], id: "branch" },
      { ...g.nodes[0], id: "join" },
    );
    g.edges = [
      { from: "prepare", to: "join" },
      { from: "branch", to: "join" },
    ];
    expect(layout(g).get("join")?.x).toBe(1);
    g.edges.push({ from: "join", to: "prepare" });
    expect(() => layout(g)).toThrow();
    g.edges = [{ from: "missing", to: "join" }];
    expect(() => layout(g)).toThrow();
  });
  it("rejects mismatched definition identities and event ordering", () => {
    const r = fixture();
    expect(assertRecording(r)).toBe(r);
    r.timeline.definition_sha256 = "wrong";
    expect(() => assertRecording(r)).toThrow();
  });
  it("never backfills final snapshot state into replay", () => {
    const r = fixture();
    expect(replayStates([])).toEqual({});
    expect(replayStates(r.timeline.events)).toEqual({ prepare: "RUNNING" });
    expect(r.stages[0].state).toBe("COMPLETED");
  });
  it("keeps unknown usage/cost unknown and bounds display", () => {
    const r = fixture();
    r.stages[0].model_invocation_id = "call";
    expect(totals(r.stages)).toMatchObject({
      calls: 1,
      tokens: null,
      cost: null,
    });
    expect(timestamp("nonsense")).toBe("Not recorded");
    expect(text("x".repeat(20000))).toContain("[Display truncated]");
  });
});
describe("inspection UI", () => {
  it("escapes graph labels and permits keyboard stage selection", () => {
    const graph = fixture().graph;
    graph.nodes[0].title = "<img src=x onerror=alert(1)>";
    const select = vi.fn();
    const { container } = render(
      <WorkflowGraph
        graph={graph}
        states={{ prepare: "UNKNOWN" }}
        selected=""
        onSelect={select}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    fireEvent.keyDown(
      screen.getByRole("button", {
        name: "Select <img src=x onerror=alert(1)>",
      }),
      { key: "Enter" },
    );
    expect(select).toHaveBeenCalledWith("prepare");
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });
  it("separates contract checks from semantics and independent feedback", () => {
    render(<ValidationView value={validation} />);
    expect(screen.getByText("Unverified")).toBeTruthy();
    expect(screen.getByText("Not performed")).toBeTruthy();
  });
  it("marks an artifact from UNKNOWN as partial and escapes model output", () => {
    const a = {
      artifact_id: "a",
      sha256: "hash",
      run_id: ID,
      stage_id: "record",
      definition_sha256: "hash",
      workflow_completed: false,
      run_status: "UNKNOWN",
      terminal_reason: "timeout",
      result: { claim: "<script>alert(1)</script>" },
      assessment: {},
      evidence_refs: [],
      context_provenance: {},
      independent_feedback: false,
      intelligence_episode_id: null,
      source_status: "unchanged",
    } as Artifact;
    const { container } = render(<ArtifactPanel value={a} />);
    expect(screen.getByText("Partial / historical artifact")).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("UNKNOWN");
  });
  it("renders feedback and learning fields instead of assuming absent values", () => {
    const value = {
      artifact_id: "a",
      sha256: "hash",
      run_id: ID,
      stage_id: "record",
      definition_sha256: "hash",
      workflow_completed: true,
      run_status: "COMPLETED",
      terminal_reason: null,
      result: {},
      assessment: {},
      evidence_refs: [],
      context_provenance: {},
      source_status: "unchanged",
      independent_feedback: false,
      intelligence_episode_id: null,
    } as Artifact;
    const view = render(<ArtifactPanel value={value} />);
    expect(screen.getByText("Not recorded")).toBeTruthy();
    expect(screen.getByText("No linked episode recorded")).toBeTruthy();
    // Deliberately probe a future response outside today's false/null contract.
    const linked = {
      ...value,
      independent_feedback: true,
      intelligence_episode_id: "episode-123",
    } as unknown as Artifact;
    view.rerender(<ArtifactPanel value={linked} />);
    expect(screen.getByText("Recorded", { exact: true })).toBeTruthy();
    expect(screen.getByText("episode-123", { exact: true })).toBeTruthy();
    expect(screen.queryByText("No linked episode recorded")).toBeNull();
  });
  it("compares each version and hash without invented quality scores", () => {
    const a = fixture(),
      b = fixture(OTHER);
    b.run.workflow.version = 3;
    b.run.workflow.definition_sha256 = "newhash";
    b.stages[0].state = "UNKNOWN";
    render(<RunComparison left={a} right={b} />);
    expect(screen.getByText("newhash")).toBeTruthy();
    expect(screen.getByText("UNKNOWN")).toBeTruthy();
    expect(screen.getByText(/do not establish quality/)).toBeTruthy();
  });
  it("loads catalogue, selects a run/stage and replays only recorded events", async () => {
    install();
    render(<WorkflowsPane token="test" />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "Execution run" }).children.length,
      ).toBe(2),
    );
    fireEvent.change(screen.getByRole("combobox", { name: "Execution run" }), {
      target: { value: ID },
    });
    await screen.findByRole("heading", { name: "Run " + ID });
    fireEvent.click(screen.getByRole("button", { name: "Select Prepare" }));
    expect(
      await screen.findByText(
        "Deterministic stage — no model invocation recorded.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Recorded events" }));
    fireEvent.click(screen.getByText("Replay recorded events"));
    fireEvent.click(screen.getByText("Next event"));
    fireEvent.click(screen.getByRole("tab", { name: "Stage details" }));
    expect(screen.getByText(/Recorded state at cursor: RUNNING/)).toBeTruthy();
    expect(
      vi
        .mocked(request)
        .mock.calls.every((c) => c[2] === undefined && c[3] === "GET"),
    ).toBe(true);
  });
  it("suppresses an older run response after selection changes", async () => {
    const a = fixture(),
      b = fixture(OTHER);
    install([a, b]);
    const normal = vi.mocked(request).getMockImplementation()!;
    let release!: (v: unknown) => void;
    vi.mocked(request).mockImplementation((path, ...args) =>
      path.includes(ID + "/inspection")
        ? new Promise((r) => {
            release = r;
          })
        : normal(path, ...args),
    );
    function Probe({ id }: { id: string }) {
      const s = useRecording(id, "test", false);
      return <div>{s.data?.run.id || "loading"}</div>;
    }
    const view = render(<Probe id={ID} />);
    await waitFor(() => expect(release).toBeTruthy());
    view.rerender(<Probe id={OTHER} />);
    await screen.findByText(OTHER);
    release({ run: a.run, definition: a.definition, graph: a.graph });
    await Promise.resolve();
    expect(screen.queryByText(ID)).toBeNull();
  });
  it("cancels an in-flight replay page before switching runs and ignores its late result", async () => {
    const a = fixture(),
      b = fixture(OTHER);
    a.timeline.has_more = true;
    install([a, b]);
    const normal = vi.mocked(request).getMockImplementation()!;
    let release!: (v: unknown) => void, signal: AbortSignal | undefined;
    vi.mocked(request).mockImplementation((path, ...args) => {
      if (path.includes("/timeline?after=")) {
        signal = args[3];
        return new Promise((r) => {
          release = r;
        });
      }
      return normal(path, ...args);
    });
    window.location.hash = link({ workflow: "example", version: 2, run: ID });
    render(<WorkflowsPane token="test" />);
    await screen.findByRole("heading", { name: "Run " + ID });
    fireEvent.click(screen.getByRole("tab", { name: "Recorded events" }));
    fireEvent.click(screen.getByText("Replay recorded events"));
    fireEvent.click(screen.getByText("Load next event page"));
    await waitFor(() => expect(release).toBeTruthy());
    fireEvent.change(screen.getByRole("combobox", { name: "Execution run" }), {
      target: { value: OTHER },
    });
    expect(signal?.aborted).toBe(true);
    await screen.findByRole("heading", { name: "Run " + OTHER });
    await act(async () => {
      release({ ...a.timeline, has_more: false });
      await Promise.resolve();
    });
    expect(screen.queryByRole("heading", { name: "Run " + ID })).toBeNull();
    expect(screen.getByRole("heading", { name: "Run " + OTHER })).toBeTruthy();
  });
  it("aborts reads on unmount and does not poll terminal history", async () => {
    install();
    function Probe() {
      const s = useRecording(ID, "test");
      return <div>{s.data?.run.id}</div>;
    }
    const view = render(<Probe />);
    await screen.findByText(ID);
    const signal = vi.mocked(request).mock.calls[0][4]!;
    expect(signal.aborted).toBe(false);
    view.unmount();
    expect(signal.aborted).toBe(true);
  });
  it("uses the server-validated reservation attachment while the final stage Pi pointer is absent", async () => {
    const r = fixture();
    r.stages[0].model_invocation_id = "call";
    r.pi_links = { [r.stages[0].id]: "actual-pi" };
    install([r]);
    function Probe() {
      const s = useRecording(ID, "test", false);
      return <div>{s.data?.stages[0].pi_run_id}</div>;
    }
    render(<Probe />);
    expect(await screen.findByText("actual-pi")).toBeTruthy();
  });
  it("backs off repeated failures and stops after five attempts", async () => {
    vi.useFakeTimers();
    vi.mocked(request).mockRejectedValue(new Error("private backend detail"));
    function Probe() {
      const s = useRecording(ID, "test");
      return <div>{s.error}</div>;
    }
    render(<Probe />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(150000);
    });
    expect(vi.mocked(request).mock.calls).toHaveLength(15);
    expect(screen.getByText(/History unavailable/).textContent).not.toContain(
      "private backend detail",
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(150000);
    });
    expect(vi.mocked(request).mock.calls).toHaveLength(15);
  });
  it("polls a live snapshot and stops when the run becomes terminal", async () => {
    vi.useFakeTimers();
    const r = fixture();
    r.run.status = "RUNNING";
    r.run.terminal = false;
    install([r]);
    function Probe() {
      const s = useRecording(ID, "test");
      return <div>{s.data?.run.status}</div>;
    }
    render(<Probe />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(vi.mocked(request).mock.calls).toHaveLength(3);
    r.run.terminal = true;
    r.run.status = "COMPLETED";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(vi.mocked(request).mock.calls).toHaveLength(6);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });
    expect(vi.mocked(request).mock.calls).toHaveLength(6);
  });
});
