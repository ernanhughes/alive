import { useCallback, useEffect, useState } from "react";
import { request } from "./api";

type Score = { correct: boolean; correct_abstention: boolean; reason: string };
type Arm = { invoked: boolean; score: Score; error?: string; allocated_tokens: number;
  choice: { reason: string }; critic_call_ref?: string };
type Row = { task_id: string; category: string; family: string; eligible: boolean;
  features?: Record<string, number>; arms: Record<string, Arm> };
type Summary = { policies: Record<string, { correct: number; tasks: number;
  critic_calls: number; allocated_tokens: number; mean_end_to_end_latency_ms: number;
  estimated_usd: number | null }>;
  physical_unique_calls: number; reported_unique_tokens: number;
  estimated_unique_usd: number | null; unknown_usage_calls: number };
type Run = { id: string; phase: string; provider: string; status: string;
  completed_tasks: number; tasks: number; summary?: Summary; error?: string };
type Detail = { data: { rows: Row[]; error?: string; summary?: Summary } };
type Review = { ready_for_owner_review: boolean; full_run_executed: boolean;
  remaining_governor_budget: Record<string, number>;
  projection: null | { expected_unique_calls: number; expected_reported_tokens: number;
    expected_rate_card_usd: number; current_budget_sufficient_for_maximum_calls: boolean } };

export function Experiments({ token }: { token: string }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const [items, pack] = await Promise.all([
        request<Run[]>("/experiments", token),
        request<Review>("/experiments/review-pack", token),
      ]);
      setRuns(items); setReview(pack); setError("");
      setSelected(current => current || items[0]?.id || "");
    } catch (e) { setError(String(e)); }
  }, [token]);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 5000);
    return () => clearInterval(timer); }, [refresh]);
  useEffect(() => {
    let cancelled = false;
    if (selected) request<Detail>("/experiments/runs/" + selected, token)
      .then(value => { if (!cancelled) setDetail(value); })
      .catch(e => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [selected, runs, token]);
  const summary = detail?.data.summary;
  return <section className="panel experiment-panel" data-testid="policy-comparison">
    <div className="panel-top"><h2>Selective cognition experiment</h2>
      <span className="tag subtle">ALIVE-03-P1</span></div>
    <p className="muted">Paired evidence, one shared initial decision, separate critical reviews.
      Development pilots qualify the pipeline; they do not establish superiority.</p>
    {error && <p role="alert">{error}</p>}
    {runs.length === 0 ? <p>No experiment runs recorded.</p> : <>
      <label>Recorded run <select aria-label="Recorded experiment run" value={selected}
        onChange={e => { setDetail(null); setSelected(e.target.value); }}>
        {runs.map(run => <option key={run.id} value={run.id}>
          {run.phase} · {run.provider} · {run.status} · {run.completed_tasks}/{run.tasks} · {run.id.slice(0, 8)}
        </option>)}
      </select></label>
      {runs.find(r => r.id === selected)?.status === "running" && <button onClick={async () => {
        try { await request("/experiments/stop", token, {}); await refresh(); }
        catch (e) { setError(String(e)); }
      }}>Stop experiment</button>}
      {detail?.data.error && <p role="alert">Unresolved: {detail.data.error}</p>}
      {summary && <>
        <p>{summary.physical_unique_calls} physical calls · {summary.reported_unique_tokens.toLocaleString()} reported tokens ·
          {summary.estimated_unique_usd == null ? " unknown cost" : ` estimated $${summary.estimated_unique_usd.toFixed(5)}`}.
          {summary.unknown_usage_calls > 0 && ` ${summary.unknown_usage_calls} calls have unknown usage.`}</p>
        <div className="experiment-scroll"><table><thead><tr><th>Policy</th><th>Correct</th>
          <th>Critic calls</th><th>Path tokens</th><th>Mean path seconds</th></tr></thead><tbody>
          {Object.entries(summary.policies).filter(([, m]) => m.tasks > 0).map(([name, m]) =>
            <tr key={name}><th>{name}</th><td>{m.correct}/{m.tasks}</td><td>{m.critic_calls}</td>
              <td>{m.allocated_tokens.toLocaleString()}</td><td>{(m.mean_end_to_end_latency_ms / 1000).toFixed(2)}</td></tr>)}
        </tbody></table></div>
        <p className="muted">Path tokens share the initial call; adding paths overcounts billing.
          Times exclude other arms' queue time. Dollar figures use the published rate card, not confirmed billing.</p>
      </>}
      {detail?.data.rows.map(row => <details className="memory" key={row.task_id}>
        <summary>{row.task_id.slice(0, 12)} · {row.category} · {row.family}
          {!row.eligible && " · INELIGIBLE"}</summary>
        {Object.entries(row.arms).map(([name, arm]) => <div key={name}>
          <strong>{name}</strong> · {arm.invoked ? "Critic invoked" : "Critic skipped"} ·
          {arm.score.correct ? " correct" : " incorrect"}{arm.score.correct_abstention && " (abstained)"}
          <p>{arm.choice.reason}</p><p className="muted">{arm.score.reason} · {arm.allocated_tokens} tokens
            {arm.critic_call_ref && ` · review ${arm.critic_call_ref.slice(0, 8)}`}</p>
          {arm.error && <p role="alert">{arm.error}</p>}
        </div>)}
        {row.features && <pre>{JSON.stringify(row.features, null, 2)}</pre>}
      </details>)}
    </>}
    {review && <details className="memory"><summary>Full evaluation review ·
      {review.full_run_executed ? " execution recorded" : " not executed"}</summary>
      <p>{review.ready_for_owner_review ? "Pilot evidence ready for owner review." : "Live pilot qualification pending."}
        {review.projection && ` Projected ${review.projection.expected_unique_calls} calls, ${Math.round(review.projection.expected_reported_tokens).toLocaleString()} tokens, estimated $${review.projection.expected_rate_card_usd.toFixed(3)}.`}</p>
      <p>Full paid evaluation requires explicit owner authorization and sufficient Governor budget.</p>
      <pre>{JSON.stringify(review.remaining_governor_budget, null, 2)}</pre>
    </details>}
  </section>;
}
