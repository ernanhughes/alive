import { useEffect, useRef, useState } from "react";
import { request } from "../api";
import { WorkflowGraph } from "../workflows/WorkflowGraph";
import type {
  Candidate,
  CatalogueEntry,
  ContextRef,
  LinkedRuns,
  Recommendation,
} from "./contracts";
import "../workflows/workflows.css";
import "./bespoke.css";

const readable = (value: string) => value.replaceAll("_", " ");
function historyRef() {
  return new URLSearchParams(window.location.hash.split("?")[1] || "").get(
    "recommendation",
  );
}
export function BespokePane({ token }: { token: string }) {
  return <Bespoke key={token} token={token} />;
}
function Bespoke({ token }: { token: string }) {
  const [recipes, setRecipes] = useState<CatalogueEntry[]>([]);
  const [contexts, setContexts] = useState<ContextRef[]>([]);
  const [history, setHistory] = useState<{ id: string; state: string }[]>([]);
  const [source, setSource] = useState("");
  const [intent, setIntent] = useState("compare_claims");
  const [objective, setObjective] = useState("");
  const [allowModel, setAllowModel] = useState(false);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(
    null,
  );
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [stage, setStage] = useState("");
  const [tab, setTab] = useState("Rationale");
  const [runs, setRuns] = useState<LinkedRuns["runs"]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [historical, setHistorical] = useState<string | null>(historyRef);
  const generation = useRef(0);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    const change = () => setHistorical(historyRef());
    window.addEventListener("hashchange", change);
    return () => {
      window.removeEventListener("hashchange", change);
      pending.current?.abort();
      generation.current++;
    };
  }, []);
  useEffect(() => {
    const c = new AbortController();
    let active = true;
    setError("");
    Promise.all([
      request<{ recipes: CatalogueEntry[] }>(
        "/bespoke/recipes",
        token,
        undefined,
        "GET",
        c.signal,
      ),
      request<{ contexts: ContextRef[] }>(
        "/bespoke/contexts",
        token,
        undefined,
        "GET",
        c.signal,
      ),
      request<{ recommendations: { id: string; state: string }[] }>(
        "/bespoke/recommendations",
        token,
        undefined,
        "GET",
        c.signal,
      ),
    ])
      .then(([catalogue, captures, records]) => {
        if (!active) return;
        setRecipes(catalogue.recipes);
        setContexts(captures.contexts);
        setHistory(records.recommendations);
      })
      .catch((e) => {
        if (active && e.name !== "AbortError")
          setError("Bespoke unavailable. Check authentication and connection.");
      });
    return () => {
      active = false;
      c.abort();
    };
  }, [token, revision]);
  function display(record: Recommendation) {
    if (record.selection.authorization !== "unavailable")
      throw new Error("Unexpected authorization state");
    const selected = record.selection.candidates.find(
      (c) => c.recipe_sha256 === record.selection.selected_recipe_sha256,
    );
    setRecommendation(record);
    setCandidate(selected || null);
    setStage("");
    setRuns([]);
  }
  useEffect(() => {
    pending.current?.abort();
    const c = new AbortController();
    pending.current = c;
    const version = ++generation.current;
    setRecommendation(null);
    setCandidate(null);
    setRuns([]);
    setBusy(false);
    if (!historical) return;
    setBusy(true);
    setError("");
    const path = "/bespoke/recommendations/" + encodeURIComponent(historical);
    Promise.all([
      request<Recommendation>(path, token, undefined, "GET", c.signal),
      request<LinkedRuns>(path + "/runs", token, undefined, "GET", c.signal),
    ])
      .then(([record, linked]) => {
        if (generation.current !== version || c.signal.aborted) return;
        if (record.id !== historical)
          throw new Error("Recommendation identity mismatch");
        display(record);
        setRuns(linked.runs);
      })
      .catch((e) => {
        if (generation.current === version && e.name !== "AbortError")
          setError("Historical recommendation unavailable or invalid.");
      })
      .finally(() => {
        if (generation.current === version) setBusy(false);
      });
    return () => c.abort();
  }, [historical, token]);

  async function select() {
    const context = contexts.find((c) => c.approval_ref === source);
    if (!context) return;
    pending.current?.abort();
    const c = new AbortController();
    pending.current = c;
    const version = ++generation.current;
    setBusy(true);
    setError("");
    setRecommendation(null);
    setCandidate(null);
    setRuns([]);
    try {
      const result = await request<Recommendation>(
        "/bespoke/recommend",
        token,
        {
          ...context,
          objective: { kind: intent || null, requested_outcome: objective },
          constraints: {
            max_model_calls: allowModel ? 1 : 0,
            max_wall_seconds: 120,
            max_output_tokens: allowModel ? 1536 : 0,
            outbound_allowed: allowModel,
            permissions: [
              "repository.read",
              "evidence.read",
              "workflow.write",
              ...(allowModel ? ["model.infer"] : []),
            ],
          },
          idempotency_key: crypto.randomUUID(),
        },
        "POST",
        c.signal,
      );
      if (generation.current === version && !c.signal.aborted) {
        display(result);
        setRevision((r) => r + 1);
      }
    } catch (e) {
      if (generation.current === version && !c.signal.aborted)
        setError(e instanceof Error ? e.message : "Selection failed");
    } finally {
      if (generation.current === version) setBusy(false);
    }
  }
  function invalidate() {
    setHistorical(null);
    pending.current?.abort();
    generation.current++;
    setBusy(false);
    setRecommendation(null);
    setCandidate(null);
    setRuns([]);
  }
  return (
    <section className="bespoke wf-pane" aria-label="Bespoke Intelligence">
      <div className="bespoke-heading">
        <div>
          <p className="eyebrow">CONTEXT → PROCEDURE → OWNER REVIEW</p>
          <h2>Bespoke Intelligence</h2>
          <p>
            Choose a procedure from captured evidence and your explicit
            objective.
          </p>
        </div>
        <button onClick={() => setRevision((r) => r + 1)}>
          Refresh catalogue
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="bespoke-layout">
        <div className="bespoke-context">
          <h3>Current context</h3>
          {!contexts.length && (
            <p>
              No approved captured context. Source approval requires the trusted
              host flow.
            </p>
          )}
          <label>
            Approved capture
            <select
              value={source}
              onChange={(e) => {
                invalidate();
                setSource(e.target.value);
              }}
            >
              <option value="">Choose captured context</option>
              {contexts.map((c) => (
                <option key={c.approval_ref} value={c.approval_ref}>
                  {c.source_ref} · goal {c.goal_ref.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label>
            User intent
            <select
              value={intent}
              onChange={(e) => {
                invalidate();
                setIntent(e.target.value);
              }}
            >
              <option value="">Intent unclear</option>
              <option value="inspect_implementation">
                Inspect implementation
              </option>
              <option value="compare_claims">Compare controlled claims</option>
              <option value="assess_claims">Assess claims and evidence</option>
              <option value="explore_arguments">
                Explore competing arguments
              </option>
            </select>
          </label>
          <label>
            Requested outcome
            <textarea
              maxLength={1000}
              value={objective}
              onChange={(e) => {
                invalidate();
                setObjective(e.target.value);
              }}
            />
          </label>
          <label className="bespoke-check">
            <input
              type="checkbox"
              checked={allowModel}
              onChange={(e) => {
                invalidate();
                setAllowModel(e.target.checked);
              }}
            />
            Consider procedures requiring one model call
          </label>
          <p>
            Ceiling: 120 seconds,{" "}
            {allowModel
              ? "1 model call / 1,536 output tokens"
              : "0 model calls"}
            . Selection itself makes no model calls.
          </p>
          <button
            disabled={!source || !objective.trim() || busy}
            onClick={select}
          >
            Recommend procedure
          </button>
          <h3>Recommendation history</h3>
          {!history.length && <p>No recommendation history.</p>}
          <ul>
            {history.map((h) => (
              <li key={h.id}>
                <a href={"#bespoke?recommendation=" + encodeURIComponent(h.id)}>
                  {h.id.slice(0, 8)} · {h.state}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div>
          {busy && <p role="status">Evaluating candidates…</p>}
          {recommendation && (
            <>
              <p className="eyebrow">
                {historical
                  ? "HISTORICAL RECOMMENDATION"
                  : "SELECTION RECORDED"}
              </p>
              <h3>
                {recommendation.selection.state === "abstained"
                  ? "No feasible procedure"
                  : "Recommended intelligence procedure"}
              </h3>
              <p>
                Observed: {readable(recommendation.selection.context.surface)} ·
                Intent:{" "}
                {readable(
                  recommendation.selection.objective.kind || "unspecified",
                )}
              </p>
              <p>{recommendation.selection.objective.requested_outcome}</p>
              <p>
                {recommendation.selection.distinct_procedures} distinct eligible
                execution contracts. Recipes sharing a contract are
                interpretations of the same procedure.
              </p>
              <div className="bespoke-candidates">
                {recommendation.selection.candidates.map((c) => (
                  <button
                    key={c.recipe_sha256}
                    onClick={() => {
                      setCandidate(c);
                      setStage("");
                    }}
                    aria-pressed={candidate?.recipe_sha256 === c.recipe_sha256}
                  >
                    <strong>{c.recipe.name}</strong>
                    <span>
                      {c.eligible
                        ? `${c.recipe_sha256 === recommendation.selection.selected_recipe_sha256 ? "Recommended" : "Eligible alternative"} · suitability ${c.suitability}`
                        : "Unavailable"}
                    </span>
                    {!c.eligible && (
                      <small>{c.reasons.map(readable).join(" · ")}</small>
                    )}
                  </button>
                ))}
              </div>
              {candidate && (
                <>
                  <h3>{candidate.recipe.name}</h3>
                  <p>{candidate.recipe.description}</p>
                  {candidate.graph && (
                    <WorkflowGraph
                      graph={candidate.graph}
                      states={{}}
                      selected={stage}
                      onSelect={setStage}
                    />
                  )}
                  <div role="tablist" aria-label="Procedure details">
                    {[
                      "Rationale",
                      "Capabilities",
                      "Permissions and budgets",
                    ].map((t) => (
                      <button
                        role="tab"
                        aria-selected={tab === t}
                        key={t}
                        onClick={() => setTab(t)}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <div role="tabpanel">
                    {tab === "Rationale" ? (
                      <>
                        <p>
                          Suitability: {candidate.suitability}. Policy:{" "}
                          {recommendation.selection.scoring_version}.
                        </p>
                        <dl>
                          {Object.entries(candidate.factors).map(
                            ([name, value]) => (
                              <div key={name}>
                                <dt>{readable(name)}</dt>
                                <dd>{value}</dd>
                              </div>
                            ),
                          )}
                        </dl>
                        <p>
                          Validation contract:{" "}
                          {readable(candidate.recipe.validation)}. Intended
                          output: {readable(candidate.recipe.output_artifact)}.
                        </p>
                        {recommendation.selection.uncertainty.map((u) => (
                          <p key={u}>{u}</p>
                        ))}
                      </>
                    ) : tab === "Capabilities" ? (
                      <ul>
                        {candidate.recipe.capabilities.map((c) => (
                          <li key={c.stage_id}>
                            <a
                              href={`#capabilities?id=${encodeURIComponent(c.id)}&version=${c.version}&sha=${c.manifest_sha256}`}
                            >
                              {c.id} v{c.version}
                            </a>{" "}
                            · {c.stage_id}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <>
                        <p>{candidate.recipe.limits.permissions.join(", ")}</p>
                        <p>
                          {candidate.recipe.limits.max_wall_seconds}s ·{" "}
                          {candidate.recipe.limits.max_model_calls} model calls
                          · {candidate.recipe.limits.max_output_tokens} output
                          tokens
                        </p>
                        <p>
                          Outbound requested:{" "}
                          {candidate.recipe.limits.outbound_allowed
                            ? "Yes"
                            : "No"}
                          . Evidence:{" "}
                          {readable(candidate.recipe.required_evidence)}.
                        </p>
                      </>
                    )}
                  </div>
                  <p className="bespoke-identity">
                    Recipe v{candidate.recipe.version}:{" "}
                    {candidate.recipe_sha256}
                    <br />
                    Workflow: {candidate.recipe.workflow.name} v
                    {candidate.recipe.workflow.version}
                    <br />
                    {candidate.recipe.workflow.definition_sha256}
                  </p>
                </>
              )}
              <p role="note">
                Authorization unavailable. An existing trusted owner flow must
                approve the exact workflow, capabilities, sources and limits.
                This dashboard cannot execute a recommendation.
              </p>
              {runs.map((r) => (
                <p key={r.id}>
                  <a
                    href={
                      "#workflows?" +
                      new URLSearchParams({
                        workflow: r.workflow.name,
                        version: String(r.workflow.version),
                        run: r.id,
                      })
                    }
                  >
                    Inspect {r.status} run in Workflow Observatory
                  </a>{" "}
                  · semantic success unverified
                </p>
              ))}
            </>
          )}
          {!recommendation && !busy && (
            <>
              <h3>Versioned recipe catalogue</h3>
              <p>
                Select approved context and state your objective to evaluate
                suitability.
              </p>
            </>
          )}
          <details open={!recommendation}>
            <summary>Installed and future recipes ({recipes.length})</summary>
            {!recipes.length && <p>The recipe catalogue is empty.</p>}
            {recipes.map((r) => (
              <article key={r.recipe_sha256}>
                <h4>
                  {r.recipe.name} <small>v{r.recipe.version}</small>
                </h4>
                <p>{r.recipe.description}</p>
                <p>
                  {r.status === "installed"
                    ? "Installed — context and constraints must still pass eligibility"
                    : "Unavailable"}
                  {r.reasons.length
                    ? ": " + r.reasons.map(readable).join(", ")
                    : ""}
                </p>
              </article>
            ))}
          </details>
        </div>
      </div>
    </section>
  );
}
