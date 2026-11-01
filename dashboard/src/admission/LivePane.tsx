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
          destination?: { provider: string; model: string; endpoint: string };
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
  followup?: { status: string; reason: string; profile: string } | null;
  conversation_ref?: string | null;
  context?: {
    items: {
      id: string;
      source_type: string;
      content: unknown;
      verification: string;
    }[];
    omitted: unknown[];
    omitted_count?: number;
  } | null;
  answer?: {
    answer: string;
    recalled_item_ids: string[];
    citations: unknown[];
    uncertainty: string[];
    lesson_ids_used?: string[];
    lesson_proposal?: { strategy: string; applies_when: string; not_when: string } | null;
    revision: {
      supersedes: string[];
      changed: string;
      rationale: string;
      still_supported: string[];
      withdrawn_or_qualified: string[];
    } | null;
  } | null;
  model_calls: number;
  admission: Admission;
  result_admission: Admission | null;
  recommendation: Recommendation | null;
  report: Report | null;
  inspection?: {
    files: { path: string; content: string; sha256: string }[];
    source_ref: string;
  } | null;
  calls: {
    id: string;
    status: string;
    provider: string;
    model: string;
    endpoint: string;
    usage: Record<string, unknown>;
    latency_ms: number;
    provider_receipts: unknown[];
    inference_provenance?: string;
  }[];
}
interface Conversation {
  id: string;
  title: string;
  consent_ref: string;
  admission_ids: string[];
}
interface History {
  consents: Consent[];
  exchanges: Exchange[];
  conversations?: Conversation[];
  adaptation?: {
    experiences: { id: string; admission_id: string; passed: boolean; verifier: string }[];
    lessons: { id: string; state: string; qualification: string; proposal: { strategy: string } }[];
  };
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
  const [conversationRef, setConversationRef] = useState("");
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
  const contextual = !!selected?.terms.profiles["contextual-reasoning"];
  const visibleExchanges = contextual
    ? history.exchanges.filter((e) =>
        conversationRef === "legacy"
          ? !e.conversation_ref
          : e.conversation_ref === conversationRef,
      )
    : history.exchanges;

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
        const activeConsent = h.consents.find(
          (v) => v.state === "approved",
        )?.id;
        setConversationRef(
          (ref) =>
            ref ||
            h.conversations?.find((c) => c.consent_ref === activeConsent)?.id ||
            "new",
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
          max_calls: 12,
          max_tokens: 200000,
          ttl_seconds: 3600,
          contextual: true,
          adaptive: true,
        },
        "POST",
      );
      if (!alive.current) return;
      setHistory((h) => ({ ...h, consents: [value, ...h.consents] }));
      setConsentRef(value.id);
      setConversationRef("new");
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  async function ask() {
    if (!approved || !goal.trim()) return;
    const signature = JSON.stringify([consentRef, conversationRef, goal]);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      let conversation = conversationRef;
      if (
        contextual &&
        (!conversation || conversation === "new" || conversation === "legacy")
      ) {
        const created = await request<Conversation>(
          "/admissions/live/conversations",
          token,
          { consent_ref: consentRef, title: goal.slice(0, 100) },
          "POST",
        );
        conversation = created.id;
        retry.current = {
          signature: JSON.stringify([consentRef, conversation, goal]),
          key: retry.current!.key,
        };
        if (!alive.current) return;
        setConversationRef(conversation);
        setHistory((h) => ({
          ...h,
          conversations: [created, ...(h.conversations || [])],
        }));
      }
      const value = await request<Exchange>(
        "/admissions/live/ask",
        token,
        {
          consent_ref: consentRef,
          goal,
          idempotency_key: retry.current.key,
          ...(contextual ? { conversation_ref: conversation } : {}),
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
          onChange={(e) => {
            setConsentRef(e.target.value);
            setConversationRef("new");
          }}
        >
          <option value="">Choose a configured session</option>
          {history.consents.map((c) => (
            <option key={c.id} value={c.id}>
              {c.state} · {c.id.slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      {contextual && (
        <div>
          <label>
            Conversation
            <select
              value={conversationRef}
              disabled={busy}
              onChange={(e) => setConversationRef(e.target.value)}
            >
              <option value="new">New conversation</option>
              {(history.conversations || [])
                .filter((c) => c.consent_ref === consentRef)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              <option value="legacy">Earlier unlinked exchanges</option>
            </select>
          </label>
          <button
            disabled={busy}
            onClick={() => {
              setConversationRef("new");
              retry.current = null;
              setGoal("");
            }}
          >
            Start new conversation
          </button>
        </div>
      )}
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
          <code>repository.inspect</code>, <code>repository.analyze</code>,{" "}
          <code>context.reason</code> and <code>context.validate</code> using{" "}
          <code>python -m alive.sources</code>. Review connects the configured
          Meta model with autonomy paused and preserves the existing Governor
          budget.
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
          Review one-hour contextual session (12 calls)
        </button>
        {selected && (
          <>
            <p>{selected.terms.disclosure}</p>
            {Object.entries(selected.terms.profiles).map(([name, p]) => (
              <p key={name}>
                {name}:{" "}
                {p.disclosure.destination ? (
                  <>
                    {p.disclosure.destination.model} ·{" "}
                    {p.disclosure.destination.provider} ·{" "}
                    {p.disclosure.destination.endpoint}
                  </>
                ) : (
                  "Local captured-file read; no model call"
                )}
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
      {!!history.adaptation?.lessons.length && (
        <details>
          <summary>Reusable lessons ({history.adaptation.lessons.length})</summary>
          {history.adaptation.lessons.map((lesson) => (
            <p key={lesson.id}>
              <strong>{lesson.state}</strong>: {lesson.proposal.strategy}{" "}
              <small>{lesson.qualification} · {lesson.id}</small>
            </p>
          ))}
          <p>Qualification and reusable text approval are owner-local actions. Model claims alone do not qualify a lesson.</p>
        </details>
      )}
      {visibleExchanges.length === 0 && <p>No retained model responses yet.</p>}
      {visibleExchanges.map((exchange) => (
        <article key={exchange.id}>
          <h4>{exchange.goal}</h4>
          {exchange.answer && (
            <section aria-label="ALIVE contextual answer">
              <p style={{ whiteSpace: "pre-wrap" }}>{exchange.answer.answer}</p>
              <p>
                Procedure used:{" "}
                {(exchange.result_admission || exchange.admission).terms.profile ||
                  "approved-repository-inspection"}
              </p>
              {!!exchange.answer.lesson_ids_used?.length && (
                <p>Strategies used: {exchange.answer.lesson_ids_used.join(", ")}</p>
              )}
              {exchange.answer.lesson_proposal && (
                <p>Proposed lesson: {exchange.answer.lesson_proposal.strategy} (provisional)</p>
              )}
              {history.adaptation?.experiences.filter((e) => e.admission_id === (exchange.result_admission?.id || exchange.id)).map((e) => (
                <p key={e.id}>Executable fixture feedback: {e.passed ? "passed" : "needs correction"} · {e.verifier}. Explanatory prose remains unverified.</p>
              ))}
              {exchange.answer.revision && (
                <div>
                  <h4>Assessment revised</h4>
                  <p>{exchange.answer.revision.changed}</p>
                  <p>{exchange.answer.revision.rationale}</p>
                  <p>
                    Still supported:{" "}
                    {exchange.answer.revision.still_supported.join(" ")}
                  </p>
                  <p>
                    Withdrawn or qualified:{" "}
                    {exchange.answer.revision.withdrawn_or_qualified.join(" ")}
                  </p>
                </div>
              )}
              {exchange.answer.uncertainty.map((u) => (
                <p key={u}>{u}</p>
              ))}
              <details>
                <summary>
                  Prior evidence used:{" "}
                  {exchange.answer.recalled_item_ids.length} item(s)
                </summary>
                <pre>
                  {JSON.stringify(
                    {
                      recalled: exchange.answer.recalled_item_ids,
                      context: exchange.context,
                      citations: exchange.answer.citations,
                      revision: exchange.answer.revision,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </section>
          )}
          <p>
            <strong>{exchange.status}</strong> · {exchange.model_calls} model
            invocation(s) ·{" "}
            {exchange.result_admission?.run?.status ||
              exchange.admission.run?.status ||
              exchange.admission.state}
          </p>
          {(exchange.followup ||
            exchange.availability === "AI unavailable") && (
            <p role="alert">
              {exchange.followup
                ? `Follow-up ${exchange.followup.status === "followup_failed" ? "failed" : "not authorized"} (${exchange.followup.reason}). Your interpretation and model receipt are retained below; no automatic retry will run.`
                : "AI unavailable. The request failed or was cancelled; retained results are shown below."}
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
                Requested model: {c.model}. Invocation {c.id} · {c.endpoint}
              </p>
              <p>
                Inference evidence: {c.inference_provenance || "unverified"}.
                Provider-observed model is recorded separately in the receipt
                and may be unknown. Network receipts establish transport
                completion, not independent provider identity or semantic truth.
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
                Intent recommendation:{" "}
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
              {!exchange.result_admission && !exchange.followup && (
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
          {exchange.inspection && (
            <section aria-label="Captured file evidence">
              <p>
                Read-only evidence from approved capture{" "}
                {exchange.inspection.source_ref}. File contents are shown as
                data. This procedure does not establish whether the code is
                correct.
              </p>
              {exchange.inspection.files.map((file) => (
                <details key={file.path}>
                  <summary>{file.path}</summary>
                  <pre className="admission-report">{file.content}</pre>
                  <p>SHA-256 {file.sha256}</p>
                </details>
              ))}
            </section>
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
