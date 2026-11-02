import { useCallback, useEffect, useState } from "react";
import { request } from "./api";

type Evidence = Record<string, unknown>;
export interface TourStep {
  n: number;
  key: string;
  title: string;
  summary: string;
  status: "ok" | "failed";
  at: string;
  provenance: string[];
  evidence: Evidence;
}
interface Ordinary {
  memory_active: boolean;
  connection_ids: string[];
  analysis_ids: string[];
  retrieval_memory_ids: string[];
  retrieval_abstained: boolean;
}
interface AuditRow {
  label: string;
  id: string;
  kind: string;
  status: string;
}
export interface TourRun {
  run_id: string;
  status: "running" | "paused" | "completed" | "failed";
  number: number;
  label: string;
  consent_text: string;
  goal_id: string | null;
  error: string | null;
  steps: TourStep[];
  live: Ordinary | null;
  audit: {
    rows: AuditRow[];
    withdrawal_events: { sequence_number: number }[];
    physically_deleted: boolean;
  } | null;
  boot: { id: string; started_at: string };
}
interface TourInfo {
  enabled: boolean;
  reason: string;
  label: string;
  labels: Record<string, string>;
  consent_text: string;
  sources: { id: string; mirror_path: string; kind: string; mirror_html_sha256: string }[];
  boot: { id: string; started_at: string };
  runs: { run_id: string; number: number; status: string; steps: number }[];
}

const short = (value: unknown) =>
  typeof value === "string" && /^[0-9a-f]{40,}$/.test(value)
    ? value.slice(0, 12) + "…"
    : String(value);
const find = (run: TourRun, key: string) => run.steps.find((s) => s.key === key);

/** A result is shown only when it names exactly this run's goal, memory and source hash. */
export function isBound(run: TourRun, key: string, sourceStep: string): boolean {
  const step = find(run, key);
  const pair = step?.evidence.bound_pair as Evidence | undefined;
  const memory = find(run, "save_memory")?.evidence.memory_id;
  const source = find(run, sourceStep)?.evidence.text_sha256;
  return Boolean(
    step &&
      pair &&
      run.goal_id &&
      memory &&
      source &&
      pair.goal_id === run.goal_id &&
      pair.historical_memory_id === memory &&
      pair.current_sha256 === source,
  );
}

function Facts({ evidence }: { evidence: Evidence }) {
  const quotes = Object.entries(evidence).filter(
    ([k, v]) => /quote/.test(k) && typeof v === "string" && v,
  );
  const scalars = Object.entries(evidence).filter(
    ([k, v]) => !/quote/.test(k) && (typeof v !== "object" || v === null),
  );
  const nested = Object.entries(evidence).filter(
    ([, v]) => typeof v === "object" && v !== null,
  );
  return (
    <>
      {quotes.map(([k, v]) => (
        <blockquote key={k} className="tour-quote">
          <small>{k.replace(/_/g, " ")}</small>
          {String(v)}
        </blockquote>
      ))}
      <dl className="tour-facts">
        {scalars.map(([k, v]) => (
          <div key={k}>
            <dt>{k.replace(/_/g, " ")}</dt>
            <dd title={String(v)}>{short(v)}</dd>
          </div>
        ))}
      </dl>
      {nested.length > 0 && (
        <details>
          <summary>Full record</summary>
          <pre>{JSON.stringify(Object.fromEntries(nested), null, 2)}</pre>
        </details>
      )}
    </>
  );
}

function Step({
  step,
  labels,
  hidden,
}: {
  step: TourStep;
  labels: Record<string, string>;
  hidden?: string;
}) {
  return (
    <li className={"tour-step " + step.status} data-step={step.key}>
      <span className="tour-n">{step.n}</span>
      <div>
        <h3>{step.title}</h3>
        <p>{step.summary}</p>
        <div className="tour-chips">
          {step.provenance.map((p) => (
            <span key={p} className={"tour-chip " + p}>
              {labels[p] || p}
            </span>
          ))}
        </div>
        {hidden ? (
          <p className="error" role="alert">
            {hidden}
          </p>
        ) : (
          <Facts evidence={step.evidence} />
        )}
      </div>
    </li>
  );
}

export function DemoTourPane({
  token,
  revealDelayMs = 450,
}: {
  token: string;
  revealDelayMs?: number;
}) {
  const [info, setInfo] = useState<TourInfo | null>(null);
  const [run, setRun] = useState<TourRun | null>(null);
  const [shown, setShown] = useState(0);
  const [pause, setPause] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      setInfo(await request<TourInfo>("/demo-tour", token));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [token]);
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Cosmetic pacing only: every step below is already persisted by the backend.
  useEffect(() => {
    if (!run || shown >= run.steps.length) return;
    if (revealDelayMs <= 0) return setShown(run.steps.length);
    const timer = setTimeout(() => setShown((n) => n + 1), revealDelayMs);
    return () => clearTimeout(timer);
  }, [run, shown, revealDelayMs]);

  const perform = async (work: () => Promise<TourRun>, reveal: boolean) => {
    setBusy(true);
    setError("");
    try {
      const next = await work();
      setShown(reveal ? 0 : next.steps.length);
      setRun(next);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const labels = info?.labels || {};
  const visible = run ? run.steps.slice(0, shown) : [];
  const before = run && find(run, "before_withdrawal")?.evidence;
  const after = run && find(run, "after_withdrawal")?.evidence;
  const count = (e: Evidence | null | undefined, k: string) =>
    Array.isArray(e?.[k]) ? (e?.[k] as unknown[]).length : 0;

  return (
    <div className="tour">
      {info?.enabled && (
        <section className="panel tour-hero">
          <p>
            ALIVE remembers a sentence from one source, notices a later source that
            changes its standing, explains the change or declines to infer one, and
            lets you withdraw the original and everything that depended on it.
          </p>
          <p className="tour-banner" role="note">
            {info.label}
          </p>
          <p className="muted">
            It does not show that either document is true, that a model reasoned about
            them, or that ALIVE improves research. Matching pinned bytes identifies a
            document; it is not a judgement about its claims.
          </p>
        </section>
      )}

      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {info && !info.enabled && (
        <div className="panel" role="status">
          <h2>Demonstration unavailable</h2>
          <p>{info.reason}</p>
        </div>
      )}

      {info?.enabled && (
        <section className="panel tour-controls">
          <h2>Start</h2>
          <p className="tour-consent">{info?.consent_text}</p>
          <label className="living-consent">
            <input
              type="checkbox"
              checked={pause}
              onChange={(e) => setPause(e.target.checked)}
            />{" "}
            Pause before withdrawal so I can withdraw manually.
          </label>
          <button
            className="primary"
            disabled={!info?.enabled || busy}
            onClick={() =>
              void perform(
                () =>
                  request<TourRun>("/demo-tour/runs", token, {
                    pause_before_withdrawal: pause,
                  }),
                true,
              )
            }
          >
            {busy ? "Working…" : "Start demonstration"}
          </button>
          {info && info.runs.length > 0 && (
            <p className="muted">
              Earlier runs:{" "}
              {info.runs.map((r) => (
                <button
                  key={r.run_id}
                  className="link"
                  onClick={() =>
                    void perform(
                      () => request<TourRun>("/demo-tour/runs/" + r.run_id, token),
                      false,
                    )
                  }
                >
                  #{r.number} ({r.status})
                </button>
              ))}
            </p>
          )}
        </section>
      )}

      {run && (
        <section className="panel" aria-label="Demonstration journey">
          <h2>
            Run #{run.number} · {run.status}
          </h2>
          <p className="muted">
            The steps below are the backend's recorded log for this run, revealed
            progressively. Each cites rows ALIVE actually persisted.
          </p>
          <ol className="tour-steps">
            {visible.map((s) => {
              const hidden =
                s.key === "compare" && !isBound(run, "compare", "observe_later")
                  ? "Not shown: this result is not bound to this run's source pair."
                  : s.key === "abstention" && !isBound(run, "abstention", "abstention")
                    ? "Not shown: this abstention is not bound to this run's source pair."
                    : undefined;
              return <Step key={s.n} step={s} labels={labels} hidden={hidden} />;
            })}
          </ol>
          {run.status === "failed" && (
            <p className="error" role="alert">
              Stopped without a result: {run.error}
            </p>
          )}
          {run.status === "paused" && shown >= run.steps.length && (
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                void perform(
                  () =>
                    request<TourRun>(
                      "/demo-tour/runs/" + run.run_id + "/withdraw",
                      token,
                      {},
                    ),
                  true,
                )
              }
            >
              Withdraw the original memory
            </button>
          )}
        </section>
      )}

      {run && before && after && shown >= run.steps.length && (
        <section className="panel tour-compare" aria-label="Before and after withdrawal">
          <h2>Before and after withdrawal</h2>
          <table>
            <thead>
              <tr>
                <th>Ordinary read</th>
                <th>Before</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Saved source is active</td>
                <td>{before.memory_active ? "yes" : "no"}</td>
                <td>{after.memory_active ? "yes" : "no"}</td>
              </tr>
              <tr>
                <td>Findings returned</td>
                <td>{count(before, "connection_ids")}</td>
                <td>{count(after, "connection_ids")}</td>
              </tr>
              <tr>
                <td>Comparisons and abstentions returned</td>
                <td>{count(before, "analysis_ids")}</td>
                <td>{count(after, "analysis_ids")}</td>
              </tr>
              <tr>
                <td>Retrieval can surface the source</td>
                <td>{count(before, "retrieval_memory_ids") ? "yes" : "no"}</td>
                <td>{count(after, "retrieval_memory_ids") ? "yes" : "no"}</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {run?.live && (
        <section className="panel" aria-label="Current backend state">
          <h2>What the backend returns right now</h2>
          <p>
            Source active: <strong>{run.live.memory_active ? "yes" : "no"}</strong> ·
            findings: <strong>{run.live.connection_ids.length}</strong> ·
            comparisons: <strong>{run.live.analysis_ids.length}</strong>
          </p>
          <p className="muted">
            Read from the database by server process <code>{run.boot.id}</code>{" "}
            (started {run.boot.started_at}). After restarting the app the process id
            changes and this answer must not.
          </p>
          <button
            onClick={() =>
              void perform(
                () => request<TourRun>("/demo-tour/runs/" + run.run_id, token),
                false,
              )
            }
          >
            Check again
          </button>
        </section>
      )}

      {run?.audit && run.status === "completed" && (
        <section className="panel" aria-label="Audit view">
          <h2>Audit view (separate from ordinary reads)</h2>
          <p className="muted">
            Originals are retained for audit as retired rows. They are hidden from
            ordinary reads, not erased
            {run.audit.physically_deleted ? "" : " — nothing was physically deleted"},
            and no source text appears here.
          </p>
          <table>
            <tbody>
              {run.audit.rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.label}</td>
                  <td title={r.id}>{r.id.slice(0, 8)}…</td>
                  <td>{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            Withdrawal events recorded: {run.audit.withdrawal_events.length}
          </p>
        </section>
      )}

      {info && (
        <section className="panel">
          <h2>Pinned sources</h2>
          <ul>
            {info.sources.map((s) => (
              <li key={s.id}>
                <a href={s.mirror_path} target="_blank" rel="noreferrer">
                  {s.id}
                </a>{" "}
                · {s.kind === "synthetic" ? "synthetic page" : "local mirror"} · bytes{" "}
                <code title={s.mirror_html_sha256}>{s.mirror_html_sha256.slice(0, 12)}…</code>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
