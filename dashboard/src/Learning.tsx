import { useEffect, useState } from "react";
import { request } from "./api";

type Metrics = { return: number; cost: number; factual_correct: number; decision_correct: number;
  state_prediction_mse: number | null; actions: Record<string, number> };
type LearningResult = { available: boolean; freeze_id?: string; reason?: string;
  simulation_only: boolean; meta_calls?: number; policies?: Record<string, Metrics>;
  learning_curves?: (Metrics & { seed: number; policy: string; updates: number })[];
  paired_intervals?: Record<string, { mean_return_difference: number; hierarchical_paired_bootstrap_95: number[] }>;
  limitation?: string };
type Transition = { action: number; reward: number; state: number[]; next_state: number[];
  prediction?: { reward: number; next_state: number[] }; state_prediction_mse?: number;
  observation: Record<string, unknown> };
type Demo = { available: boolean; selection: string; scenario_id: string;
  before: { transitions: Transition[]; return: number };
  after: { transitions: Transition[]; return: number } };
const actions = ["retrieve", "investigate", "critic", "accept", "reject", "monitor"];

export function Learning({ token }: { token: string }) {
  const [result, setResult] = useState<LearningResult | null>(null);
  const [demo, setDemo] = useState<Demo | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    Promise.all([request<LearningResult>("/learning", token),
      request<Demo>("/learning/demonstration", token)])
      .then(([r, d]) => { if (!cancelled) { setResult(r); setDemo(d); } })
      .catch(e => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [token]);
  return <section className="panel experiment-panel learning-panel">
    <div className="panel-top"><h2>Predictive cognitive learning</h2>
      <span className="tag subtle">P2 · SIMULATOR</span></div>
    <p className="muted">Completed state–action transitions, matched training experience and held-out worlds.
      These policies have no authority over live browsing. Critic remains an optional experimental action.</p>
    {error && <p role="alert">{error}</p>}
    {!result?.available && <p>{result?.reason || "Loading simulator evidence…"}</p>}
    {result?.available && <>
      <p>2,000 training scenarios · 400 unique held-out scenarios · 5 learner seeds ·
        {result.meta_calls} Meta calls</p>
      <div className="experiment-scroll"><table><thead><tr><th>Policy</th><th>Net return</th>
        <th>Resource cost</th><th>Factual belief accuracy</th><th>Decision correctness</th></tr></thead><tbody>
        {Object.entries(result.policies || {}).map(([name, m]) => <tr key={name}>
          <th>{name}</th><td>{m.return.toFixed(3)}</td><td>{m.cost.toFixed(3)}</td>
          <td>{(m.factual_correct * 100).toFixed(1)}%</td><td>{(m.decision_correct * 100).toFixed(1)}%</td>
        </tr>)}
      </tbody></table></div>
      <p className="muted">Costs are synthetic resource units. Decision correctness uses a privileged
        full-information reference; net return measures realized benefits, errors and costs.</p>
      <details className="memory"><summary>Experience-driven policy changes and held-out uncertainty</summary>
        {Object.entries(result.policies || {}).map(([name, m]) => <p key={name}>
          <strong>{name}</strong> · {Object.entries(m.actions).map(([a, n]) => `${a}: ${n}`).join(" · ")}
        </p>)}
        <pre>{JSON.stringify(result.paired_intervals, null, 2)}</pre>
        <div className="experiment-scroll"><table><thead><tr><th>Training updates</th>
          <th>Value only · dev return</th><th>Predictive · dev return</th>
          <th>Reward only · dev return</th></tr></thead><tbody>
          {[0, 250, 1000, 2500].map(updates => <tr key={updates}><th>{updates}</th>
            {["value_only", "predictive", "reward_only_ablation"].map(policy => {
              const rows = (result.learning_curves || []).filter(r => r.updates === updates && r.policy === policy);
              return <td key={policy}>{rows.length ? (rows.reduce((n, r) => n + r.return, 0) / rows.length).toFixed(3) : "—"}</td>;
            })}</tr>)}
        </tbody></table></div>
      </details>
      {demo?.available && <details className="memory"><summary>Prediction → observation → error · fixed demonstration</summary>
        <p>{demo.selection} · {demo.scenario_id}</p>
        {(["before", "after"] as const).map(stage => <div key={stage}>
          <h3>{stage === "before" ? "Before training" : "After predictive training"}</h3>
          <p>Realized return: {demo[stage].return.toFixed(3)}</p>
          {demo[stage].transitions.map((t, i) => <details className="memory" key={i}>
            <summary>{i + 1}. {actions[t.action]} · predicted reward {t.prediction?.reward.toFixed(3)}
              {" → "}observed {t.reward.toFixed(3)} · state MSE {t.state_prediction_mse?.toFixed(4)}</summary>
            <p>Belief: {t.state[0].toFixed(3)} → {t.next_state[0].toFixed(3)} ·
              remaining budget: {t.next_state[8].toFixed(3)}</p>
            <pre>{JSON.stringify({ prediction: t.prediction, observed_next_state: t.next_state,
              observed_evidence: t.observation }, null, 2)}</pre>
          </details>)}
        </div>)}
        <p className="muted">This scenario was fixed before evaluation; it was not chosen for a favorable outcome.</p>
      </details>}
      <p className="muted">{result.limitation}</p>
      <p className="muted">Frozen design: {result.freeze_id}</p>
    </>}
  </section>;
}
