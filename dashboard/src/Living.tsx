import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Eye, History, Leaf, Square } from "lucide-react";
import { request } from "./api";

type Choice = { action: string; policy_version: number; policy_hash: string;
  predictions: Record<string, { n: number; mean: number; status: string }> };
type Experience = { id: string; episode: number; data: {
  state: { claim: string; recent_event: string; feature_hash: string };
  choice: Choice; initial_policy_counterfactual: Choice;
  observation: { text: string }; evidence: { text: string } | null; feedback: { text: string };
  model_output: { summary: string; recommendation: string }; reward: number;
  prediction_error: number; memory_ids: string[];
  outcome: { resolved: boolean; safe_abstention: boolean; measurement: string };
  before_hash: string; after_hash: string; policy_after: { version: number };
} };
type Journey = { id: string; provider: string; status: string; transitions: Experience[];
  data: { error?: string; stage: string; phases: { stage: string; at: string; data: unknown }[];
    ledger: { id: string; status: string; episode: number; model: string; latency_ms: number;
      estimated_usd: number | null; usage?: { total_tokens?: number }; error?: string }[];
    tool_log: unknown[]; grant: string } };
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
  const activeStage = journey?.data.stage || "observing";
  const stageIndex = activeStage === "observed" ? 0 : stages.indexOf(activeStage);
  return <div className="living-experience">
    <section className="living-hero">
      <span className="living-eyebrow"><Leaf size={15} /> ALIVE / THE LIVING EXPERIENCE</span>
      <h1>A consequence remembered.<br /><em>A different next step.</em></h1>
      <p>A new claim appears. ALIVE draws on prior outcomes, chooses a permitted action,
        and checks what actually happened. The next encounter carries that experience forward.</p>
      <div className="living-hero-stats"><span><strong>{status?.policy.version || 0}</strong> completed experiences</span>
        <span><strong>{ledger.length}</strong> calls this journey</span>
        <span><strong>{ledger.reduce((n, c) => n + (c.usage?.total_tokens || 0), 0).toLocaleString()}</strong> reported tokens</span>
        <span><strong>{dollars == null ? "Unknown" : `$${dollars.toFixed(4)}`}</strong> estimated cost</span></div>
    </section>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="panel living-controls">
      <div><h2>Two encounters. One continuing identity.</h2>
        <p className="muted">A controlled local habitat with synthetic instrument facts.
          Learned action values persist across backend restarts.</p></div>
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
            The current claim and history features match the first encounter.</p></div></div>}
      {experiences.length === 2 && !changed && <p className="muted">No new action change was demonstrated
        within this journey. Earlier experience may already have favored this action.</p>}
      <div className="living-encounters">{[0, 1].map(index => {
        const experience = experiences[index]; const data = experience?.data;
        return <article className="panel living-encounter" key={index} data-testid={`encounter-${index + 1}`}>
          <div className="panel-top"><span className="living-eyebrow">ENCOUNTER {String(index + 1).padStart(2, "0")}</span>
            <span className="tag subtle">{data ? "RECORDED" : "AWAITING OBSERVATION"}</span></div>
          <h2>{index === 0 ? "A first consequence." : "Experience carried forward."}</h2>
          {!data ? <p className="muted">{journey.status === "running" ? "The bounded browser episode is in progress…" : "Observe the related situation to continue."}</p> : <>
            <div className="living-observation"><Eye size={17} /><div><small>OBSERVED CHROME DOM</small>
              <p>Aster endurance claim: <strong>{data.state.claim} hours</strong></p>
              <p>Recent event: <strong>source replaced</strong></p></div></div>
            <p className="living-action">{data.choice.action === "retrieve" ? "Retrieve current evidence" : "Continue without extra evidence"}</p>
            <p>{data.memory_ids.length} relevant prior experience{data.memory_ids.length === 1 ? "" : "s"} retrieved · policy version {data.choice.policy_version}</p>
            <div className="living-predictions">{Object.entries(data.choice.predictions).map(([action, p]) =>
              <div key={action}><span>{action}</span><strong>{p.n ? p.mean.toFixed(2) : "Not learned yet"}</strong>
                <small>{p.n} observed outcome{p.n === 1 ? "" : "s"}</small></div>)}</div>
            <blockquote>{data.model_output.summary}</blockquote>
            <div className="living-outcome"><span>{data.outcome.resolved ? "Goal resolved with current evidence" : data.outcome.safe_abstention ? "Safely abstained · goal unresolved" : "Unresolved or unsupported conclusion"}</span>
              <strong>{data.reward.toFixed(2)}</strong><small>Synthetic goal utility</small></div>
            <p className="muted">Policy updated to version {data.policy_after.version} after observed feedback.
              Prediction error: {data.prediction_error.toFixed(2)}.</p>
            <details><summary>Inspect the evidence and update</summary>
              <p>Current instrument after retrieval: {data.evidence ? `${data.outcome.measurement} hours` : "Not retrieved"}</p>
              <pre>{JSON.stringify({ observation: data.observation, retrieved_evidence: data.evidence,
                published_feedback: data.feedback, policy_before: data.before_hash,
                policy_after: data.after_hash, feature_hash: data.state.feature_hash,
                original_policy_action: data.initial_policy_counterfactual.action }, null, 2)}</pre>
            </details>
          </>}
        </article>;
      })}</div>
      <details className="panel"><summary>Live reasoning, permissions and provenance</summary>
        <p>{journey.data.grant}. At most two model calls and six bounded browser operations.</p>
        <p>Action choice precedes Meta synthesis. Feedback and policy changes commit together.
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
