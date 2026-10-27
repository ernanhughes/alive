import { useCallback, useEffect, useState } from "react";
import {
  ArrowUpRight,
  BrainCircuit,
  Pause,
  Play,
  Square,
  RefreshCw,
} from "lucide-react";
import { base, request } from "./api";
import { Experiments } from "./Experiments";
import { Learning } from "./Learning";

interface Bid {
  id: string;
  content: string;
  status: string;
  created_at: string;
  attention: {
    score: number;
    relevance: number;
    novelty: number;
    explanation: string;
    matched_terms: string[];
  };
}
interface Investigation {
  id: string;
  goal_id: string;
  state: string;
  error: string | null;
  evaluation: { status?: string; conclusion_status?: string };
  usage: { calls: number; tokens: number; tools: number };
  snapshot: {
    observation?: string;
    environment_id?: string;
    sources?: unknown[];
    memories?: unknown[];
  };
  history: { state: string; at: string }[];
}
interface Message {
  id: string;
  sender: string;
  message_type: string;
  content: unknown;
  invocation_id: string | null;
}
interface Call {
  id: string;
  role: string;
  provider: string;
  model: string;
  status: string;
  usage: { total_tokens?: number; charged_tokens?: number };
  latency_ms: number;
  input_json: unknown;
  output_json: unknown;
  error: string | null;
}
interface Action {
  id: string;
  kind: string;
  risk_class: string;
  status: string;
  proposal: { content: string; rationale: string };
  outcome: unknown;
}
interface Experience {
  id: string;
  data: {
    outcome_state: unknown;
    reward_components: unknown;
    truncated: boolean;
    terminated: boolean;
    evaluation: unknown;
    state_snapshot: { state_hash?: string };
    usage: unknown;
  };
}
interface Mind {
  control: {
    mode: string;
    provider: string;
    configuration: Record<string, unknown>;
    spent: Record<string, number>;
    reserved: Record<string, number>;
  };
  active: Investigation | null;
  active_objective: string | null;
  current_uncertainty: string[];
  active_role: string | null;
  embedding: { available: boolean; model: string; revision: string };
  roles: {
    role: string;
    model?: string;
    deterministic?: boolean;
    tools?: string[];
  }[];
}
interface Detail extends Investigation {
  messages: Message[];
  invocations: Call[];
  actions: Action[];
  experiences: Experience[];
}

export function CognitionPane({ token }: { token: string }) {
  const [mind, setMind] = useState<Mind | null>(null),
    [bids, setBids] = useState<Bid[]>([]),
    [runs, setRuns] = useState<Investigation[]>([]),
    [experiences, setExperiences] = useState<Experience[]>([]),
    [actions, setActions] = useState<Action[]>([]),
    [selected, setSelected] = useState(""),
    [detail, setDetail] = useState<Detail | null>(null);
  const [provider, setProvider] = useState("mock"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [config, setConfig] = useState(""),
    [environment, setEnvironment] = useState(""),
    [browser, setBrowser] = useState(""),
    [scenario, setScenario] = useState("relevant"),
    [health, setHealth] = useState("");
  const refresh = useCallback(async () => {
    const [m, b, r, e, a] = await Promise.all([
      request<Mind>("/cognition", token),
      request<Bid[]>("/cognition/observations", token),
      request<Investigation[]>("/cognition/investigations", token),
      request<Experience[]>("/experiences", token),
      request<Action[]>("/cognition/actions", token),
    ]);
    setMind(m);
    setBids(b);
    setRuns(r);
    setExperiences(e);
    setActions(a);
    setConfig((old) => old || JSON.stringify(m.control.configuration, null, 2));
  }, [token]);
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      2000,
    );
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const load = () =>
      request<Detail>("/cognition/investigations/" + selected, token)
        .then((d) => {
          if (!cancelled) setDetail(d);
        })
        .catch((e) => setError(e.message));
    load();
    const timer = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [selected, token]);
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  async function command(command: string) {
    await request("/cognition/control", token, { command, provider });
  }
  async function lab() {
    const env = await request<{ id: string }>("/lab", token, { scenario });
    setEnvironment(env.id);
    const b = await request<{ id: string }>("/browser/sessions", token, {});
    setBrowser(b.id);
    await request("/browser/sessions/" + b.id + "/navigate", token, {
      url: base + "/world/" + env.id,
    });
    await request("/browser/sessions/" + b.id + "/observation", token, {
      approved: true,
    });
  }
  return (
    <div className="cognitive-pane">
      <section className="panel">
        <div className="panel-top">
          <h2>
            <BrainCircuit size={18} /> Cognitive control
          </h2>
          <span className="tag" data-testid="autonomy-mode">
            {mind?.control.mode || "CONNECTING"}
          </span>
        </div>
        <div className="button-row">
          <select
            aria-label="Cognitive provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={mind?.control.mode === "running"}
          >
            <option value="mock">
              Controlled role fixtures · no inference
            </option>
            <option value="meta">Meta Model API · live inference</option>
          </select>
          <button
            className="primary"
            disabled={busy}
            onClick={() => act(() => command("start"))}
          >
            <Play size={14} />
            Start autonomy
          </button>
          <button disabled={busy} onClick={() => act(() => command("pause"))}>
            <Pause size={14} />
            Pause
          </button>
          <button disabled={busy} onClick={() => act(() => command("stop"))}>
            <Square size={14} />
            Stop autonomy
          </button>
          <button
            disabled={busy}
            onClick={() => act(() => command("new_session"))}
          >
            New budget session
          </button>
        </div>
        <p className="muted">
          Permission, state transitions and budgets are enforced by the
          deterministic Governor. Model messages are proposals. No private model
          reasoning is displayed.
        </p>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <div className="metrics">
          <div className="metric">
            <span>Active phase</span>
            <strong>{mind?.active?.state || "Idle"}</strong>
            <small>
              {mind?.active?.id.slice(0, 8) ||
                "No action warranted until evidence arrives"}
            </small>
          </div>
          <div className="metric">
            <span>Session calls / ceiling</span>
            <strong>
              {mind?.control.spent.session_calls || 0} /{" "}
              {String(mind?.control.configuration.session_calls || 0)}
            </strong>
            <small>
              {mind?.control.reserved.calls || 0} reserved before work
            </small>
          </div>
          <div className="metric">
            <span>Charged tokens / ceiling</span>
            <strong>{mind?.control.spent.session_tokens || 0}</strong>
            <small>
              Ceiling {String(mind?.control.configuration.session_tokens || 0)}{" "}
              · failed calls retain reservation
            </small>
          </div>
          <div className="metric">
            <span>Embedding inference</span>
            <strong>
              {mind?.embedding.available ? "Local ONNX" : "Unavailable"}
            </strong>
            <small>
              {mind?.embedding.available
                ? "384 dimensions · pinned MiniLM"
                : "Full-text fallback active"}
            </small>
          </div>
        </div>
        <p className="muted">
          Active objective: {mind?.active_objective || "None selected"}. Current
          uncertainty:{" "}
          {mind?.current_uncertainty?.join(" · ") ||
            "No unresolved model question recorded"}
          .
        </p>
        <div className="button-row" aria-label="Cognitive roles">
          {mind?.roles.map((role) => (
            <span className="tag subtle" key={role.role}>
              {role.role}
              {mind.active_role === role.role ? " · active" : ""}
              {role.deterministic ? " · deterministic" : ""}
            </span>
          ))}
        </div>
        <details>
          <summary>Resource budgets & permissions</summary>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              act(() =>
                request("/cognition/configuration", token, JSON.parse(config)),
              );
            }}
          >
            <label>
              Governor configuration
              <textarea
                aria-label="Governor configuration"
                className="configuration-editor"
                value={config}
                onChange={(e) => setConfig(e.target.value)}
              />
            </label>
            <button disabled={busy || mind?.control.mode === "running"}>
              Save budgets and permissions
            </button>
          </form>
          <p className="muted">
            Pause before editing. A new session resets only session accounting,
            never the experimental ceiling.
          </p>
        </details>
        <div className="button-row">
          <button
            disabled={busy}
            onClick={() =>
              act(async () => {
                const d = await request<{ status: string; models: string[] }>(
                  "/providers/meta/probe",
                  token,
                  {},
                );
                setHealth(`${d.status}: ${d.models.join(", ")}`);
              })
            }
          >
            Probe Meta access
          </button>
          <button
            disabled={busy}
            onClick={() => act(() => request("/memories/index", token, {}))}
          >
            Index authorised memory
          </button>
        </div>
        <p className="muted">{health}</p>
      </section>
      <div className="two-columns">
        <section className="panel">
          <div className="panel-top">
            <h2>ALIVE World</h2>
            <span className="tag subtle">SYNTHETIC LABORATORY</span>
          </div>
          <label>
            Scenario
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              <option value="relevant">Relevant new information</option>
              <option value="contradiction">Contradictory evidence</option>
              <option value="noise">Irrelevant noise</option>
            </select>
          </label>
          <div className="button-row">
            <button disabled={busy || !!browser} onClick={() => act(lab)}>
              Open & observe habitat
            </button>
            <button
              className="primary"
              disabled={busy || !environment}
              onClick={() =>
                act(() => request("/lab/" + environment + "/inject", token, {}))
              }
            >
              Inject environmental change
            </button>
            {environment && (
              <a
                href={base + "/world/" + environment}
                target="_blank"
                rel="noreferrer"
              >
                View habitat <ArrowUpRight size={12} />
              </a>
            )}
            {browser && (
              <button
                disabled={busy}
                onClick={() =>
                  act(async () => {
                    await request(
                      "/browser/sessions/" + browser + "/observation",
                      token,
                      { approved: false },
                    );
                    await request(
                      "/browser/sessions/" + browser,
                      token,
                      undefined,
                      "DELETE",
                    );
                    setBrowser("");
                    setEnvironment("");
                  })
                }
              >
                Revoke & close
              </button>
            )}
          </div>
          <p className="muted">
            The managed sensor observes DOM text changes. Injecting a fixture
            sends no chat prompt or cognitive command.
          </p>
        </section>
        <section className="panel">
          <div className="panel-top">
            <h2>Attention auction</h2>
            <span className="tag subtle">POLICY V1</span>
          </div>
          {bids.slice(0, 10).map((b) => (
            <details className="bid" key={b.id}>
              <summary>
                <span>{b.content.slice(0, 85)}</span>
                <b>{b.attention.score.toFixed(3)}</b>
                <span className="tag subtle">{b.status}</span>
              </summary>
              <p>{b.attention.explanation}</p>
              <pre>{JSON.stringify(b.attention, null, 2)}</pre>
            </details>
          ))}
          {!bids.length && (
            <p className="empty">
              No significant observation yet. Ignoring noise is a valid
              decision.
            </p>
          )}
        </section>
      </div>
      <section className="panel">
        <div className="panel-top">
          <h2>Investigations & cognitive society</h2>
          <button onClick={() => act(refresh)}>
            <RefreshCw size={13} />
            Refresh trace
          </button>
        </div>
        <label>
          Investigation
          <select
            aria-label="Investigation"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            <option value="">Select a persisted investigation</option>
            {runs.map((r) => (
              <option value={r.id} key={r.id}>
                {r.id.slice(0, 8)} · {r.state} ·{" "}
                {r.snapshot.observation?.slice(0, 80)}
              </option>
            ))}
          </select>
        </label>
        {!detail ? (
          <p className="empty">
            Select an investigation to inspect its actual messages, evidence and
            expenditure.
          </p>
        ) : (
          <>
            <div className="button-row">
              {detail.history.map((h, i) => (
                <span className="tag subtle" key={i}>
                  {h.state}
                </span>
              ))}
            </div>
            <div className="two-columns">
              <div>
                <h3>Structured exchanges</h3>
                {detail.messages.map((m) => (
                  <details className="memory" key={m.id}>
                    <summary>
                      <strong>{m.sender}</strong> · {m.message_type}{" "}
                      <span className="tag subtle">
                        {m.invocation_id ? "MODEL OUTPUT" : "DETERMINISTIC"}
                      </span>
                    </summary>
                    <pre>{JSON.stringify(m.content, null, 2)}</pre>
                  </details>
                ))}
              </div>
              <div>
                <h3>World state & grounded evaluation</h3>
                <p>{detail.snapshot.observation}</p>
                <pre>{JSON.stringify(detail.evaluation, null, 2)}</pre>
                <details>
                  <summary>
                    Supporting sources, memories and prior state
                  </summary>
                  <pre>{JSON.stringify(detail.snapshot, null, 2)}</pre>
                </details>
                <h3>Model invocations</h3>
                {detail.invocations.map((c) => (
                  <details key={c.id} className="memory">
                    <summary>
                      {c.role} · {c.provider}/{c.model} · {c.status}
                    </summary>
                    <p>
                      {c.latency_ms.toFixed(0)} ms ·{" "}
                      {c.usage.total_tokens ?? "unknown"} reported tokens ·{" "}
                      {c.usage.charged_tokens} charged
                    </p>
                    {c.error && <p role="alert">{c.error}</p>}
                    <pre>
                      {JSON.stringify(
                        {
                          input: c.input_json,
                          output: c.output_json,
                          usage: c.usage,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                ))}
              </div>
            </div>
            {detail.error && <p role="alert">{detail.error}</p>}
            {!["COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"].includes(
              detail.state,
            ) && (
              <button
                onClick={() =>
                  act(() =>
                    request(
                      "/cognition/investigations/" + detail.id + "/cancel",
                      token,
                      {},
                    ),
                  )
                }
              >
                Cancel investigation
              </button>
            )}
          </>
        )}
      </section>
      <div className="two-columns">
        <section className="panel">
          <div className="panel-top">
            <h2>Action authority</h2>
            <span className="tag subtle">GOVERNOR ENFORCED</span>
          </div>
          {actions.slice(0, 15).map((a) => (
            <article className="memory" key={a.id} data-action-id={a.id}>
              <span className="eyebrow">
                Class {a.risk_class} · {a.kind} · {a.status}
              </span>
              <p>{a.proposal.content}</p>
              <small>{a.proposal.rationale}</small>
              {a.status === "awaiting_approval" && (
                <div className="button-row">
                  {["approve", "reject", "cancel"].map((decision) => (
                    <button
                      disabled={
                        busy || (a.risk_class === "C" && decision === "approve")
                      }
                      key={decision}
                      onClick={() =>
                        act(() =>
                          request(
                            "/cognition/actions/" + a.id + "/decision",
                            token,
                            { decision },
                          ),
                        )
                      }
                    >
                      {decision}
                    </button>
                  ))}
                </div>
              )}
              {a.risk_class === "C" && (
                <p className="muted">
                  Consequential external actions are unsupported.
                </p>
              )}
            </article>
          ))}
        </section>
        <section className="panel">
          <div className="panel-top">
            <h2>Experience timeline</h2>
            <span className="tag subtle">{experiences.length} RECORDS</span>
          </div>
          {experiences.slice(0, 10).map((e) => (
            <details className="memory" key={e.id}>
              <summary>
                {e.id.slice(0, 8)} ·{" "}
                {e.data.truncated ? "TRUNCATED" : "RECORDED"} · environment
                terminated: {String(e.data.terminated)}
              </summary>
              <pre>{JSON.stringify(e.data, null, 2)}</pre>
              <button
                onClick={() =>
                  act(async () => {
                    const result = await request(
                      "/experiences/" + e.id + "/replay",
                      token,
                      {},
                    );
                    setHealth(JSON.stringify(result));
                  })
                }
              >
                Replay recorded evidence checks
              </button>
            </details>
          ))}
        </section>
      </div>
      <Experiments token={token} />
      <Learning token={token} />
    </div>
  );
}
