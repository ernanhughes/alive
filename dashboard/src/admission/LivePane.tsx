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
    code_review?: boolean;
    completion_repair?: boolean;
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
interface SelectionView {
  policy: string;
  decision: "selected" | "none" | "abstained" | "refused";
  no_lesson_reason: string | null;
  task_mechanisms: string[];
  override: string | null;
  received: string[];
  reported_used: string[];
  selected: { item_id: string; lesson_id: string; version: number; tier: string }[];
  candidates: {
    lesson_id: string;
    status: string;
    reasons: string[];
    overlap: string[];
    tier: string;
    supporting_outcomes: { experience_id: string; task_id: string; passed: boolean }[];
  }[];
  context_bytes: number;
  independent_outcome: { passed: boolean; verifier: string; semantic?: string | null } | null;
}
interface Lesson {
  id: string;
  lesson_id?: string;
  state: string;
  qualification: string;
  withdrawal?: string;
  proposal: { strategy: string };
  utility?: { state: string; paired_gains: number; paired_losses: number; applications: number };
}
interface TaskCandidate {
  candidate_id: string;
  raw_text: string;
  candidate: unknown;
  contract: { case_ids: string[] };
  transport_completed: boolean;
  response_schema_valid: boolean;
  schema_valid: boolean;
  task_complete: boolean;
  semantically_verified: boolean;
  completion: { all_cases_addressed: boolean; contains_undetermined: boolean; errors: unknown[] };
}
interface Exchange {
  task_review?: {
    original: TaskCandidate;
    effective: TaskCandidate;
    repair: unknown;
    repair_attempted: boolean;
    repair_successful: boolean;
    additional_model_calls: number;
  };
  id: string;
  selection?: SelectionView | null;
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
    lessons: Lesson[];
  };
}

const NO_LESSON: Record<string, string> = {
  no_lessons_available: "No reusable lesson has been approved yet.",
  no_applicable_lesson:
    "No stored lesson matched this task's failure mechanisms, so ALIVE reasoned from the evidence alone.",
  task_mechanisms_unavailable:
    "ALIVE could not tell which failure mechanisms apply, so it used no lesson.",
  authorization_scope:
    "A matching lesson exists but is outside this owner or model scope, so it was not used.",
  control_supplies_no_experience: "This request ran as a no-experience control.",
};
const EXCLUDED: Record<string, string> = {
  no_mechanism_overlap: "different mechanism",
  unscoped_lesson_without_mechanisms: "no declared scope",
  not_active_or_withdrawn: "withdrawn or inactive",
  empirically_demoted: "demoted on counterevidence",
  empirically_contradicted: "contradicted by measured outcomes",
  dominated_by_selected_lesson: "covered by a better lesson",
  owner_changed: "different owner",
  destination_changed: "different model destination",
};

export function standing(lesson?: Lesson) {
  if (!lesson) return "unknown";
  if (lesson.state === "rejected")
    return lesson.withdrawal ? "withdrawn by owner" : "rejected on counterevidence";
  const u = lesson.utility?.state;
  if (u === "demoted" || u === "contradicted") return "contradicted by measured outcomes";
  if (u === "useful") return "useful (measured gain)";
  return "provisional (no measured benefit yet)";
}

function reason(code: string) {
  return EXCLUDED[code] || code.replace(/^excluded_mechanism_present:/, "excluded: ");
}

function SelectionNote({ selection, lessons }: { selection: SelectionView; lessons: Lesson[] }) {
  const byId = new Map<string, Lesson>(
    lessons.flatMap((l) => [[l.id, l] as [string, Lesson], [l.lesson_id || l.id, l] as [string, Lesson]]),
  );
  const supplied = selection.selected;
  return (
    <section aria-label="Learned context decision">
      <p>
        <strong>Learned context:</strong>{" "}
        {supplied.length
          ? `${supplied.length} lesson(s) supplied`
          : "none supplied"}
        {selection.policy.startsWith("selective") ? "" : ` · control (${selection.policy})`}
      </p>
      {!supplied.length && (
        <p>
          {NO_LESSON[selection.no_lesson_reason || ""] ||
            selection.no_lesson_reason ||
            "No lesson was supplied."}
        </p>
      )}
      {supplied.map((s) => {
        const lesson = byId.get(s.lesson_id);
        return (
          <p key={s.item_id}>
            Lesson v{s.version} ({s.tier}): {lesson?.proposal.strategy || s.lesson_id}{" "}
            <small>now {standing(lesson)}</small>
          </p>
        );
      })}
      {!!supplied.length && (
        <p>
          {selection.reported_used.length
            ? "ALIVE reported using it (a self-report, not proof)."
            : "ALIVE did not report using it."}
        </p>
      )}
      {selection.independent_outcome && (
        <p>
          Independent check:{" "}
          {selection.independent_outcome.passed ? "passed" : "needs correction"} ·{" "}
          {selection.independent_outcome.verifier}
        </p>
      )}
      {selection.override && <p role="note">Evaluation intervention: {selection.override}</p>}
      {!!selection.candidates.length && (
        <details>
          <summary>
            Considered {selection.candidates.length} lesson(s) · {selection.context_bytes} bytes sent
          </summary>
          {selection.candidates.map((c) => (
            <p key={c.lesson_id}>
              <strong>{c.status}</strong>: {byId.get(c.lesson_id)?.proposal.strategy || c.lesson_id}
              {c.reasons.length ? ` — ${c.reasons.map(reason).join("; ")}` : ""}
              {c.overlap.length ? ` — matched ${c.overlap.join(", ")}` : ""}
            </p>
          ))}
        </details>
      )}
    </section>
  );
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
  const [taskMode, setTaskMode] = useState("general_contextual");
  const [caseIds, setCaseIds] = useState("");
  const [completionRepair, setCompletionRepair] = useState(false);
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
          code_review: taskMode === "code_review",
          completion_repair: taskMode === "code_review" && completionRepair,
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
    const signature = JSON.stringify([consentRef, conversationRef, goal, taskMode, caseIds, completionRepair]);
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
          signature: JSON.stringify([consentRef, conversation, goal, taskMode, caseIds, completionRepair]),
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
          ...(taskMode === "code_review" ? {
            task_mode: taskMode,
            task_case_ids: caseIds.trim() ? caseIds.split(",").map((v) => v.trim()) : null,
            repair_incomplete: completionRepair,
          } : {}),
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
        Response contract
        <select value={taskMode} disabled={busy} onChange={(e) => {
          setTaskMode(e.target.value); setCompletionRepair(false);
        }}>
          <option value="general_contextual">General conversation (existing)</option>
          <option value="code_review">Code review v1 (opt-in)</option>
        </select>
      </label>
      {taskMode === "code_review" && <>
        <label>Declared case IDs (optional, comma separated)
          <input value={caseIds} maxLength={320} disabled={busy} onChange={(e) => setCaseIds(e.target.value)} />
        </label>
        <label><input type="checkbox" checked={completionRepair} disabled={busy}
          onChange={(e) => setCompletionRepair(e.target.checked)} />
          Request one completion repair if authorized (one extra model call)
        </label>
        {selected && !selected.terms.code_review && <p>Configure and approve a session with this task contract before asking.</p>}
        {completionRepair && selected && !selected.terms.completion_repair && <p>This session does not authorize completion repair; configure a new session to enable it.</p>}
      </>}
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
      <button disabled={busy || !approved || !goal.trim() || (taskMode === "code_review" &&
          (!selected?.terms.code_review || (completionRepair && !selected?.terms.completion_repair)))} onClick={ask}>
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
              <strong>{standing(lesson)}</strong>: {lesson.proposal.strategy}{" "}
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
          {exchange.task_review && <section aria-label="Code-review completion">
            <p><strong>Code-review contract: {exchange.task_review.effective.task_complete ? "complete" : "incomplete"}</strong></p>
            <p>Transport returned: {exchange.task_review.original.transport_completed ? "yes" : "no"} · Original response schema valid: {exchange.task_review.original.response_schema_valid ? "yes" : "no"} · Candidate schema valid: {exchange.task_review.effective.schema_valid ? "yes" : "no"}</p>
            <p>Every declared case addressed ({exchange.task_review.effective.contract.case_ids.length} required): {exchange.task_review.effective.completion.all_cases_addressed ? "yes" : "no"}</p>
            <p>Independent semantic verification: {exchange.task_review.effective.semantically_verified ? "verified" : "not performed"}</p>
            {exchange.task_review.effective.completion.contains_undetermined && <p>Structurally complete answers can still contain undetermined outcomes.</p>}
            <p>Repair: {exchange.task_review.repair_attempted ? (exchange.task_review.repair_successful ? "completed the contract" : "did not complete the contract") : "not attempted"} · {exchange.task_review.additional_model_calls} additional model call(s)</p>
            <details><summary>Original candidate, omissions and repair evidence</summary>
              <pre>{JSON.stringify(exchange.task_review, null, 2)}</pre>
            </details>
          </section>}
          {exchange.answer && (
            <section aria-label="ALIVE contextual answer">
              <p style={{ whiteSpace: "pre-wrap" }}>{exchange.answer.answer}</p>
              <p>
                Procedure used:{" "}
                {(exchange.result_admission || exchange.admission).terms.profile ||
                  "approved-repository-inspection"}
              </p>
              {exchange.selection && (
                <SelectionNote
                  selection={exchange.selection}
                  lessons={history.adaptation?.lessons || []}
                />
              )}
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
