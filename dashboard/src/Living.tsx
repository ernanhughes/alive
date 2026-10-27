import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Eye, History, Leaf, Square } from "lucide-react";
import { request } from "./api";

type Choice = { action: string; policy_version: number; policy_hash: string; reason: string;
  predictions: Record<string, { n: number; mean: number; status: string }> };
type RecalledExperience = { id: string; action: string; reward: number;
  outcome: { resolved?: boolean; safe_abstention?: boolean } };
type Outcome = { resolved: boolean; safe_abstention: boolean; measurement: string;
  factual_correct?: boolean | null; conclusion_contract_correct?: boolean;
  source_value?: string | null; feedback_confirms_source?: boolean;
  synthetic_goal_reward?: number; resource_cost?: number };
type ToolOperation = { episode: number; operation: string; at: string; session_id?: string;
  url?: string };
type Experience = { id: string; episode: number; data: {
  episode: number;
  state: { claim: string; recent_event: string; feature_hash: string };
  choice: Choice; initial_policy_counterfactual: Choice;
  observation: { text: string }; evidence: { text: string } | null; feedback: { text: string };
  sources?: { id: string; value: string; provenance: string }[];
  relevant_experience?: RecalledExperience[];
  model_output: { summary: string; recommendation: string }; reward: number;
  prediction_error: number; memory_ids: string[];
  outcome: Outcome;
  before_hash: string; after_hash: string; policy_after: { version: number };
  next_choice: Choice;
} };
type Journey = { id: string; provider: string; status: string; transitions: Experience[];
  data: { error?: string; stage: string; phases: { stage: string; at: string; data: unknown }[];
    ledger: { id: string; status: string; episode: number; model: string; latency_ms: number;
      estimated_usd: number | null; usage?: { total_tokens?: number }; error?: string }[];
    tool_log: ToolOperation[]; grant: string; max_calls?: number; max_tokens?: number;
    max_micro_usd?: number; max_tools?: number } };
type Status = { policy: { version: number }; active: boolean;
  journeys: { id: string; provider: string; status: string; episodes: number }[] };
const stages = ["observing", "remembering", "predicting", "choosing", "acting", "reasoning", "feedback", "learned"];
const labels = ["Observe", "Remember", "Predict", "Choose", "Act", "Reason", "Feedback", "Learn"];

export function LivingPane({ token }: { token: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [selected, setSelected] = useState("");
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const [journey, setJourney] = useState<Journey | null>(null);
  const [provider, setProvider] = useState("meta");
  const [allowed, setAllowed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    const result = await request<Status>("/living", token);
    setStatus(result); setSelected(current => current || result.journeys[0]?.id || "");
    if (selected) {
      const detail = await request<Journey>("/living/journeys/" + selected, token);
      if (selectedRef.current === selected) setJourney(detail);
    }
  }, [token, selected]);
  useEffect(() => {
    let alive = true;
    const load = () => refresh().catch(e => { if (alive) setError(String(e)); });
    void load(); const timer = setInterval(() => void load(), 1200);
    return () => { alive = false; clearInterval(timer); };
  }, [refresh]);
  async function perform(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); await refresh(); } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }
  const experiences = journey?.transitions || [];
  const second = experiences[1]?.data;
  const changed = !!second && second.choice.action !== second.initial_policy_counterfactual.action
    && second.state.feature_hash === experiences[0].data.state.feature_hash;
  const ledger = journey?.data.ledger || [];
  const dollars = ledger.every(c => c.estimated_usd != null)
    ? ledger.reduce((n, c) => n + (c.estimated_usd || 0), 0) : null;
  const maxCalls = journey?.data.max_calls ?? 2;
  const maxTools = journey?.data.max_tools ?? 6;
  const maxDollars = (journey?.data.max_micro_usd ?? 150000) / 1e6;
  const activeStage = journey?.data.stage || "observing";
  const stageIndex = activeStage === "observed" ? 0 : stages.indexOf(activeStage);
  return <div className="living-experience">
    <section className="living-hero">
      <span className="living-eyebrow"><Leaf size={15} /> ALIVE / THE LIVING EXPERIENCE</span>
      <h1>A consequence remembered.<br /><em>A different next step.</em></h1>
      <p>A new claim appears. ALIVE draws on prior outcomes, chooses a permitted action,
        and checks what actually happened. The next encounter carries that experience forward.</p>
      <div className="living-hero-stats"><span><strong>{status?.policy.version || 0}</strong> recorded policy updates</span>
        <span><strong>{ledger.length}</strong> model calls this journey</span>
        <span><strong>{ledger.reduce((n, c) => n + (c.usage?.total_tokens || 0), 0).toLocaleString()}</strong> reported tokens</span>
        <span><strong>{dollars == null ? "Unknown" : `$${dollars.toFixed(4)}`}</strong> estimated cost</span></div>
    </section>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="panel living-controls">
      <div><h2>Two encounters. One continuing identity.</h2>
        <p className="muted">A controlled local habitat with synthetic instrument facts.
          Learned action values persist across backend restarts. A new journey reuses the existing
          policy and never resets it; a warm identity may reuse an action instead of changing it.</p></div>
      <div className="living-create">
        <label>Reasoning provider <select aria-label="Living reasoning provider" value={provider}
          onChange={e => setProvider(e.target.value)}><option value="meta">Live Meta</option>
          <option value="mock">Controlled fixture</option></select></label>
        <label className="living-consent"><input type="checkbox" checked={allowed}
          onChange={e => setAllowed(e.target.checked)} /> Allow observation and public-evidence clicks in this local habitat.</label>
        <button className="primary" disabled={!allowed || busy || !!status?.active} onClick={() => void perform(async () => {
          const created = await request<{ id: string }>("/living/journeys", token,
            { provider, allow_controlled_read: true });
          setSelected(created.id); setJourney(null);
          await request("/living/journeys/" + created.id + "/advance", token, {});
        })}>Begin a new journey <ArrowUpRight size={16} /></button>
      </div>
      {!!status?.journeys.length && <label>Recorded journey <select aria-label="Recorded living journey"
        value={selected} onChange={e => { setSelected(e.target.value); setJourney(null); }}>
        {status.journeys.map(j => <option key={j.id} value={j.id}>
          {j.provider} · {j.status} · {j.episodes}/2 · {j.id.slice(0, 8)}</option>)}
      </select></label>}
    </section>
    {journey && <>
      <div className="living-process" aria-label="Living feedback loop">
        {labels.map((label, i) => <span key={label} className={i <= stageIndex ? "reached" : ""}>
          <b>{String(i + 1).padStart(2, "0")}</b>{label}</span>)}
      </div>
      <div className="living-state-bar"><span className="tag">{journey.status.toUpperCase()}</span>
        <span>{journey.provider === "meta" ? "Live Meta reasoning" : "Controlled fixture — not live inference"}</span>
        {journey.status === "ready" && <button disabled={busy || !!status?.active} onClick={() => void perform(async () => {
          await request("/living/journeys/" + selected + "/advance", token, {});
        })}>Face the related situation <ArrowUpRight size={16} /></button>}
        {["ready", "running"].includes(journey.status) && <button disabled={busy} onClick={() => void perform(async () => {
          await request("/living/journeys/" + selected + "/stop", token, {});
        })}><Square size={13} /> Stop & revoke</button>}
      </div>
      {journey.data.error && <p className="error" role="alert">{journey.data.error}</p>}
      {changed && <div className="living-change" data-testid="behavior-change">
        <History size={22} /><div><strong>The same situation, a changed action.</strong>
          <p>The original policy would still {second!.initial_policy_counterfactual.action}.
            After observed feedback, ALIVE chose to {second!.choice.action}.
            The current claim and history features match the first encounter.</p>
          <p className="muted">Deterministic policy comparison on the same feature state,
            not a different answer selected from model sampling.</p></div></div>}
      {experiences.length === 2 && !changed && <p className="muted">No new action change was demonstrated
        within this journey. Earlier experience may already have favored this action.</p>}
      <div className="living-encounters">{[0, 1].map(index => {
        const experience = experiences[index]; const data = experience?.data;
        const operations = data ? journey.data.tool_log
          .filter(t => t.episode === data.episode).map(t => t.operation) : [];
        return <article className="panel living-encounter" key={index} data-testid={`encounter-${index + 1}`}>
          <div className="panel-top"><span className="living-eyebrow">ENCOUNTER {String(index + 1).padStart(2, "0")}</span>
            <span className="tag subtle">{data ? "RECORDED" : "AWAITING OBSERVATION"}</span></div>
          <h2>{index === 0 ? "A first consequence." : "Experience carried forward."}</h2>
          {!data ? <p className="muted">{journey.status === "running" ? "The bounded browser episode is in progress…" : "Observe the related situation to continue."}</p> : <>
            <div className="living-observation"><Eye size={17} /><div><small>OBSERVED CHROME DOM · CONTROLLED SYNTHETIC HABITAT</small>
              <p>Aster endurance claim: <strong>{data.state.claim} hours</strong></p>
              <p>Recent event: <strong>source replaced</strong></p></div></div>
            <p className="living-action">{data.choice.action === "retrieve" ? "Retrieve current evidence" : "Continue without extra evidence"}</p>
            <p className="muted living-reason">{data.choice.reason}</p>
            <p className="muted">Governor-permitted operations: {operations.length ? operations.join(" → ") : "none recorded"}.</p>
            <p>{data.memory_ids.length} relevant prior experience{data.memory_ids.length === 1 ? "" : "s"} retrieved · policy version {data.choice.policy_version}</p>
            {!!data.relevant_experience?.length && <div className="living-recall" data-testid="recalled-experience">
              <small>RECALLED EXPERIENCE</small>
              {data.relevant_experience.map(recalled => <p key={recalled.id}>
                <strong>{recalled.action}</strong> returned {recalled.reward.toFixed(2)} · {recalled.outcome?.resolved
                  ? "goal resolved" : recalled.outcome?.safe_abstention ? "safe abstention" : "unresolved"}
                {" "}<code title={recalled.id}>{recalled.id.slice(0, 8)}</code></p>)}
            </div>}
            <div className="living-predictions">{Object.entries(data.choice.predictions).map(([action, p]) =>
              <div key={action}><span>{action}</span><strong>{p.n ? p.mean.toFixed(2) : "Not learned yet"}</strong>
                <small>{p.n} observed outcome{p.n === 1 ? "" : "s"}</small></div>)}</div>
            <blockquote>{data.model_output.summary}</blockquote>
            <div className="living-outcome"><span>{data.outcome.resolved ? "Goal resolved with current evidence" : data.outcome.safe_abstention ? "Safely abstained · goal unresolved" : "Unresolved or unsupported conclusion"}</span>
              <strong>{data.reward.toFixed(2)}</strong><small>Synthetic goal utility · not money</small></div>
            <div className="living-provenance" data-testid="source-corroboration">
              <span><small>FACTUAL SUPPORT</small>{data.outcome.factual_correct == null
                ? "No claim" : data.outcome.factual_correct
                  ? "Claim matches the cited source" : "Claim does not match the cited source"}</span>
              <span><small>FEEDBACK CORROBORATION</small>{data.outcome.source_value == null
                ? data.evidence ? "Not recorded for this legacy journey" : "No current source"
                : data.outcome.feedback_confirms_source == null
                  ? "Not recorded for this legacy journey" : data.outcome.feedback_confirms_source
                    ? "Feedback matches the source" : "Feedback does not match the source"}</span>
              <span><small>CONCLUSION CONTRACT</small>{data.outcome.conclusion_contract_correct == null
                ? "Not recorded for this legacy journey" : data.outcome.conclusion_contract_correct
                  ? "Accepted" : "Not accepted"}</span>
            </div>
            <p className="muted">Policy updated to version {data.policy_after.version} after observed feedback.
              Prediction error: {data.prediction_error.toFixed(2)}.</p>
            <details><summary>Inspect the evidence and update</summary>
              <p>Retrieved instrument evidence: {data.outcome.source_value != null
                ? `${data.outcome.source_value} hours`
                : data.evidence ? "Recorded; source value not stored for this legacy journey" : "Not retrieved"}</p>
              <p>Published feedback measurement: {data.outcome.measurement} hours, read independently
                from the controlled fixture after reasoning.</p>
              <pre>{JSON.stringify({ observation: data.observation, retrieved_evidence: data.evidence,
                sources: data.sources, published_feedback: data.feedback, source_value: data.outcome.source_value,
                feedback_confirms_source: data.outcome.feedback_confirms_source,
                policy_before: data.before_hash, policy_after: data.after_hash,
                feature_hash: data.state.feature_hash,
                original_policy_action: data.initial_policy_counterfactual.action }, null, 2)}</pre>
            </details>
          </>}
        </article>;
      })}</div>
      {experiences.length > 0 && <section className="panel living-carry">
        <div><span className="living-eyebrow">WHAT CARRIES FORWARD</span>
          <h2>Experience becomes the next expectation.</h2>
          <p className="muted">Preferred next action: <strong>{experiences[experiences.length - 1].data.next_choice.action}</strong>.
            These values come from recorded outcomes, with small-sample uncertainty.</p></div>
        <div className="living-predictions">{Object.entries(experiences[experiences.length - 1].data.next_choice.predictions).map(([action, p]) =>
          <div key={action}><span>{action}</span><strong>{p.n ? p.mean.toFixed(2) : "Not learned yet"}</strong>
            <small>{p.n} observed outcome{p.n === 1 ? "" : "s"}</small></div>)}</div>
      </section>}
      <details className="panel"><summary>Live reasoning, permissions and provenance</summary>
        <p>{journey.data.grant}. At most two model calls and six bounded browser operations.</p>
        <p>Governor envelope: {journey.data.tool_log.length}/{maxTools} browser operations;
          {" "}{ledger.length}/{maxCalls} model calls; {dollars == null ? "unknown"
            : `$${dollars.toFixed(4)}`} estimated of ${maxDollars.toFixed(2)} ceiling.
          Every recorded browser operation was permitted before execution; denied operations
          are not counted as an experience.</p>
        <p>Action choice precedes Meta synthesis. Feedback and policy changes commit together.
          The reward uses the source for factual support and requires the published feedback to
          corroborate that source before the goal counts as resolved.
          A stronger fixed history rule would retrieve from the first encounter; this demonstrates
          learning from feedback, not superiority to that rule.</p>
        <p>Dollar amounts are rate-card estimates, not confirmed billing. Utility is synthetic and
          separate from real inference cost. One or two outcomes do not establish general learning performance.</p>
        <pre>{JSON.stringify({ model_calls: ledger, browser_operations: journey.data.tool_log,
          stages: journey.data.phases }, null, 2)}</pre>
      </details>
    </>}
  </div>;
}
