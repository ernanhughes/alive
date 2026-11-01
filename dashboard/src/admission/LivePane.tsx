import { useEffect, useRef, useState } from "react";
import { request } from "../api";
import type { Goal } from "../api";
import type { Admission, Recommendation, Report, Source } from "./contracts";
import "./admission.css";

interface Consent {
  id: string;
  sha256: string;
  state: string;
  terms: {
    goal_ref: string;
    max_calls: number;
    max_tokens: number;
    expires_at: string;
    disclosure: string;
    profiles: Record<
      string,
      {
        disclosure: {
          destination: { provider: string; model: string; endpoint: string };
        };
      }
    >;
  };
}
interface Exchange {
  id: string;
  goal: string;
  status: string;
  availability: string;
  model_calls: number;
  admission: Admission;
  result_admission: Admission | null;
  recommendation: Recommendation | null;
  report: Report | null;
  calls: {
    id: string;
    status: string;
    provider: string;
    model: string;
    endpoint: string;
    usage: Record<string, unknown>;
    latency_ms: number;
    provider_receipts: unknown[];
  }[];
}
interface History {
  consents: Consent[];
  exchanges: Exchange[];
}

export function LivePane({ token }: { token: string }) {
  return <LiveAI key={token} token={token} />;
}

function LiveAI({ token }: { token: string }) {
  const [history, setHistory] = useState<History>({
    consents: [],
    exchanges: [],
  });
  const [sources, setSources] = useState<Source[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [source, setSource] = useState("");
  const [goalRef, setGoalRef] = useState("");
  const [consentRef, setConsentRef] = useState("");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const alive = useRef(true);
  const retry = useRef<{ signature: string; key: string } | null>(null);
  const selected = history.consents.find((c) => c.id === consentRef);
  const approved =
    selected?.state === "approved" &&
    Date.parse(selected.terms.expires_at) > Date.now();

  useEffect(() => {
    alive.current = true;
    const controller = new AbortController();
    Promise.all([
      request<History>(
        "/admissions/live",
        token,
        undefined,
        "GET",
        controller.signal,
      ),
      request<{ sources: Source[] }>(
        "/admissions/sources?profile=approved-repository-analysis",
        token,
        undefined,
        "GET",
        controller.signal,
      ),
      request<Goal[]>("/goals", token, undefined, "GET", controller.signal),
    ])
      .then(([h, s, g]) => {
        if (controller.signal.aborted) return;
        setHistory(h);
        setSources(s.sources);
        setGoals(g.filter((v) => ["accepted", "active"].includes(v.status)));
        setConsentRef(
          (ref) =>
            ref ||
            h.consents.find((v) => v.state === "approved")?.id ||
            h.consents[0]?.id ||
            "",
        );
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => {
      alive.current = false;
      controller.abort();
    };
  }, [token, revision]);

  useEffect(() => {
    if (!busy) return;
    const controller = new AbortController();
    const timer = setInterval(() => {
      request<History>(
        "/admissions/live",
        token,
        undefined,
        "GET",
        controller.signal,
      )
        .then((h) => {
          if (!controller.signal.aborted) setHistory(h);
        })
        .catch(() => {
          /* The foreground request reports errors. */
        });
    }, 1000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [busy, token]);

  async function cancel(id: string) {
    try {
      await request(`/admissions/${id}/cancel`, token, {}, "POST");
      if (alive.current) setRevision((r) => r + 1);
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    }
  }

  async function setup() {
    const capture = sources.find((s) => s.approval_ref === source);
    if (!capture || !goalRef) return;
    setBusy(true);
    setError("");
    try {
      await request(
        "/cognition/control",
        token,
        { command: "enable_model", provider: "meta" },
        "POST",
      );
      const value = await request<Consent>(
        "/admissions/live/setup",
        token,
        {
          goal_ref: goalRef,
          approval_ref: source,
          paths: capture.inventory.items.map((i) => i.item),
          max_calls: 6,
          max_tokens: 200000,
          ttl_seconds: 3600,
        },
        "POST",
      );
      if (!alive.current) return;
      setHistory((h) => ({ ...h, consents: [value, ...h.consents] }));
      setConsentRef(value.id);
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  async function ask() {
    if (!approved || !goal.trim()) return;
    const signature = JSON.stringify([consentRef, goal]);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      const value = await request<Exchange>(
        "/admissions/live/ask",
        token,
        {
          consent_ref: consentRef,
          goal,
          idempotency_key: retry.current.key,
        },
        "POST",
      );
      if (!alive.current) return;
      setHistory((h) => ({
        ...h,
        exchanges: [value, ...h.exchanges.filter((v) => v.id !== value.id)],
      }));
      setGoal("");
      retry.current = null;
    } catch (e) {
      if (alive.current) {
        setError((e as Error).message);
        setRevision((r) => r + 1);
      }
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  return (
    <section className="owner-admission" aria-label="ALIVE Live AI">
      <div className="admission-heading">
        <div>
          <p className="eyebrow">ALIVE — LIVE AI</p>
          <h2>Ask ALIVE</h2>
          <p>
            Give ALIVE a goal. It interprets your request with the configured
            model and runs useful, approved read-only analysis.
          </p>
        </div>
        <button
          disabled={busy}
          onClick={() => {
            setError("");
            setRevision((r) => r + 1);
          }}
        >
          Refresh AI and history
        </button>
      </div>
      {error && <p role="alert">AI unavailable / consent required. {error}</p>}
      <label>
        Trusted workspace session
        <select
          value={consentRef}
          disabled={busy}
          onChange={(e) => setConsentRef(e.target.value)}
        >
          <option value="">Choose a configured session</option>
          {history.consents.map((c) => (
            <option key={c.id} value={c.id}>
              {c.state} · {c.id.slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      {!approved && (
        <p role="status">
          NO MODEL CALL · AI unavailable / consent required. Configure and
          approve a bounded session below, then refresh.
        </p>
      )}
      {selected && (
        <p>
          {selected.terms.max_calls} calls · {selected.terms.max_tokens}{" "}
          conservative token budget · expires {selected.terms.expires_at}
        </p>
      )}
      <label>
        Your goal
        <textarea
          value={goal}
          maxLength={1000}
          disabled={busy}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Review my repository and tell me what's preventing us from shipping."
        />
      </label>
      <button disabled={busy || !approved || !goal.trim()} onClick={ask}>
        {busy ? "ALIVE is examining the evidence…" : "Ask ALIVE"}
      </button>
      <details open={!approved}>
        <summary>Initial model and source consent</summary>
        <p>
          Install the shipped procedures with{" "}
          <code>python -m alive.admission install</code>. Capture a nonsecret
          repository scope and approve <code>intent.interpret</code>,{" "}
          <code>repository.inspect</code> and <code>repository.analyze</code>{" "}
          using <code>python -m alive.sources</code>. Review connects the
          configured Meta model with autonomy paused and preserves the existing
          Governor budget.
        </p>
        <label>
          Accepted owner goal
          <select value={goalRef} onChange={(e) => setGoalRef(e.target.value)}>
            <option value="">Choose goal</option>
            {goals.map((g) => (
              <option key={g.id} value={g.id}>
                {g.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Approved source
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">Choose source</option>
            {sources.map((s) => (
              <option key={s.approval_ref} value={s.approval_ref}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy || !source || !goalRef} onClick={setup}>
          Review one-hour session (6 calls)
        </button>
        {selected && (
          <>
            <p>{selected.terms.disclosure}</p>
            {Object.entries(selected.terms.profiles).map(([name, p]) => (
              <p key={name}>
                {name}: {p.disclosure.destination.model} ·{" "}
                {p.disclosure.destination.provider} ·{" "}
                {p.disclosure.destination.endpoint}
              </p>
            ))}
            <p>
              Inspect these terms and approve once on the owner machine. Routine
              questions need no further CLI approvals.
            </p>
            <pre>{`python -m alive.admission inspect-trust ${selected.id}\npython -m alive.admission trust ${selected.id} --confirm-sha256 ${selected.sha256}`}</pre>
            <p>
              Revoke with{" "}
              <code>python -m alive.admission untrust {selected.id}</code>.
            </p>
          </>
        )}
      </details>
      <h3>Conversation and evidence</h3>
      {history.exchanges.length === 0 && (
        <p>No retained model responses yet.</p>
      )}
      {history.exchanges.map((exchange) => (
        <article key={exchange.id}>
          <h4>{exchange.goal}</h4>
          <p>
            <strong>{exchange.status}</strong> · {exchange.model_calls} model
            invocation(s) ·{" "}
            {exchange.result_admission?.run?.status ||
              exchange.admission.run?.status ||
              exchange.admission.state}
          </p>
          {exchange.availability === "AI unavailable" && (
            <p role="alert">
              AI unavailable. The request failed or was cancelled; retained
              results are shown below.
            </p>
          )}
          {[exchange.admission, exchange.result_admission].map(
            (a) =>
              a?.run &&
              !a.run.terminal && (
                <button key={a.id} onClick={() => cancel(a.id)}>
                  Cancel this request
                </button>
              ),
          )}
          {exchange.calls.map((c) => (
            <details key={c.id}>
              <summary>
                {c.model} · {c.provider} · {c.status} ·{" "}
                {Math.round(c.latency_ms)} ms ·{" "}
                {typeof c.usage.total_tokens === "number"
                  ? c.usage.total_tokens
                  : "unknown"}{" "}
                actual tokens
              </summary>
              <p>
                Invocation {c.id} · {c.endpoint}
              </p>
              <pre>
                {JSON.stringify(
                  { usage: c.usage, provider_receipts: c.provider_receipts },
                  null,
                  2,
                )}
              </pre>
            </details>
          ))}
          {exchange.recommendation && (
            <>
              <p>
                {
                  exchange.recommendation.record.interpretation.value
                    ?.primary_objective
                }
              </p>
              <p>
                Selected procedure:{" "}
                {exchange.recommendation.record.recommendation?.recipe_id ||
                  "None useful for this goal"}
              </p>
              {exchange.recommendation.record.uncertainty
                ?.clarification_question && (
                <p>
                  {
                    exchange.recommendation.record.uncertainty
                      .clarification_question
                  }
                </p>
              )}
              <p>
                {exchange.recommendation.record.uncertainty?.limits_of_available_procedures.join(
                  " ",
                )}
              </p>
              {!exchange.result_admission && (
                <p>
                  No automatic result: the model requested clarification, or its
                  selected procedure is outside this session's approved analysis
                  scope.
                </p>
              )}
            </>
          )}
          {exchange.report && (
            <>
              <pre className="admission-report">
                {exchange.report.result.report_markdown}
              </pre>
              <p>
                {exchange.report.assessment.findings_with_valid_references} of{" "}
                {exchange.report.assessment.findings_total} findings have
                matching source references. Model assessments; semantic truth
                and release readiness remain unverified.
              </p>
            </>
          )}
          <details>
            <summary>Goal, source and result receipts</summary>
            <pre>
              {JSON.stringify(
                {
                  admission: exchange.admission.id,
                  source: exchange.admission.terms.source,
                  result: exchange.result_admission?.id,
                  artifact: exchange.report?.artifact_sha256,
                },
                null,
                2,
              )}
            </pre>
          </details>
        </article>
      ))}
    </section>
  );
}
