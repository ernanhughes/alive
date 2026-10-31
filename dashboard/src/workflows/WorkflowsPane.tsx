import { useEffect, useRef, useState } from "react";
import type {
  Definition,
  Graph,
  Recording,
  Timeline,
  WorkflowRun,
  WorkflowSummary,
} from "./contracts";
import { read } from "./client";
import {
  duration,
  link,
  parseLink,
  replayStates,
  timestamp,
  totals,
} from "./model";
import { useRecording } from "./useRecording";
import { WorkflowGraph } from "./WorkflowGraph";
import { StageInspector, Facts } from "./StageInspector";
import { RunTimeline } from "./RunTimeline";
import { RunComparison } from "./RunComparison";
import "./workflows.css";
import { WorkflowCatalogue } from "./WorkflowCatalogue";

export function WorkflowsPane({ token }: { token: string }) {
  // Remount all read state on credential changes; stale data cannot cross identities.
  return <Observatory key={token} token={token} />;
}
function Observatory({ token }: { token: string }) {
  const [operations, setOperations] = useState<
    { id: string; available: boolean; executable: boolean }[]
  >([]);
  const [section, setSection] = useState("Overview");
  const initial = parseLink(window.location.hash);
  const [catalogue, setCatalogue] = useState<WorkflowSummary[]>([]),
    [name, setName] = useState(initial?.workflow || "");
  const [version, setVersion] = useState(initial?.version || 0),
    [runId, setRunId] = useState(initial?.run || "");
  const [selected, setSelected] = useState(initial?.stage || ""),
    [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [definition, setDefinition] = useState<Definition | null>(null),
    [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState(""),
    [filter, setFilter] = useState(""),
    [comparison, setComparison] = useState("");
  const [refresh, setRefresh] = useState(0),
    [cursor, setCursor] = useState<number | null>(null),
    [frozen, setFrozen] = useState<Recording | null>(null);
  const [extra, setExtra] = useState<Timeline | null>(null),
    [moreBusy, setMoreBusy] = useState(false);
  const pageController = useRef<AbortController | null>(null);
  useEffect(() => () => pageController.current?.abort(), [runId, token]);
  const observed = useRecording(runId, token, cursor === null, refresh),
    compared = useRecording(comparison, token, false, refresh);
  const candidate = frozen || observed.data;
  const identityMismatch =
    candidate &&
    (candidate.run.id !== runId ||
      candidate.run.workflow.name !== name ||
      candidate.run.workflow.version !== version);
  const record = identityMismatch ? null : candidate;
  useEffect(() => {
    const c = new AbortController();
    let active = true;
    Promise.all([
      read<{ workflows: WorkflowSummary[] }>("/workflows", token, c.signal),
      read<{
        operations: { id: string; available: boolean; executable: boolean }[];
      }>("/workflow-operations", token, c.signal),
    ])
      .then(([v, registry]) => {
        if (!active) return;
        setOperations(registry.operations);
        setCatalogue(v.workflows);
        if (!name && v.workflows[0]) {
          setName(v.workflows[0].name);
          setVersion(v.workflows[0].latest_version);
        }
      })
      .catch(() => {
        if (active)
          setError(
            "Workflow catalogue unavailable. Check authentication and connection.",
          );
      });
    return () => {
      active = false;
      c.abort();
    };
  }, [token, refresh]);
  useEffect(() => {
    if (!name || !version) return;
    const c = new AbortController();
    let active = true;
    setDefinition(null);
    setGraph(null);
    setError("");
    setRuns([]);
    Promise.all([
      read<Definition>(
        `/workflows/${encodeURIComponent(name)}/versions/${version}`,
        token,
        c.signal,
      ),
      read<Graph>(
        `/workflows/${encodeURIComponent(name)}/versions/${version}/graph`,
        token,
        c.signal,
      ),
      read<{ runs: WorkflowRun[] }>(
        `/workflow-runs?workflow=${encodeURIComponent(name)}&limit=200`,
        token,
        c.signal,
      ),
    ])
      .then(([d, g, r]) => {
        if (!active) return;
        if (
          !d.integrity.verified ||
          d.name !== name ||
          d.version !== version ||
          g.name !== name ||
          g.version !== version ||
          d.definition_sha256 !== g.definition_sha256
        )
          throw new Error();
        setDefinition(d);
        setGraph(g);
        setRuns(r.runs);
      })
      .catch(() => {
        if (active)
          setError("Definition unavailable or integrity check failed.");
      });
    return () => {
      active = false;
      c.abort();
    };
  }, [name, version, token, refresh]);
  useEffect(() => {
    function hash() {
      const s = parseLink(location.hash);
      if (!s) return;
      pageController.current?.abort();
      setMoreBusy(false);
      setName(s.workflow);
      setVersion(s.version);
      setRunId(s.run || "");
      setSelected(s.stage || "");
      setCursor(null);
      setFrozen(null);
      setComparison("");
      setExtra(null);
    }
    window.addEventListener("hashchange", hash);
    return () => window.removeEventListener("hashchange", hash);
  }, []);
  function chooseRun(id: string) {
    pageController.current?.abort();
    const selectedRun = runs.find((r) => r.id === id);
    if (selectedRun) setVersion(selectedRun.workflow.version);
    setRunId(id);
    setCursor(null);
    setFrozen(null);
    setExtra(null);
    setComparison("");
    setMoreBusy(false);
  }
  function chooseWorkflow(n: string) {
    setName(n);
    setVersion(catalogue.find((w) => w.name === n)?.latest_version || 1);
    chooseRun("");
    setSelected("");
  }
  function replay(n: number | null) {
    pageController.current?.abort();
    setMoreBusy(false);
    if (n !== null && !frozen && record)
      setFrozen({ ...record, timeline: extra || record.timeline });
    if (n === null) {
      setFrozen(null);
      setExtra(null);
    }
    setCursor(n);
  }
  const displayedDefinition = record?.definition || definition,
    displayedGraph = record?.graph || graph;
  const timeline =
    frozen?.timeline ||
    (extra?.run_id === record?.run.id ? extra : record?.timeline);
  const visibleEvents =
    timeline?.events.slice(0, cursor === null ? undefined : cursor) || [];
  const states = record
    ? cursor === null
      ? Object.fromEntries(record.stages.map((s) => [s.stage_id, s.state]))
      : replayStates(visibleEvents)
    : {};
  const stageId = selected || displayedGraph?.nodes[0]?.id || "";
  const spec = displayedDefinition?.definition.stages.find(
    (s) => s.id === stageId,
  );
  const stage = record?.stages.filter((s) => s.stage_id === stageId).at(-1);
  async function more() {
    if (!record || !timeline || moreBusy) return;
    setMoreBusy(true);
    const c = new AbortController();
    pageController.current = c;
    try {
      const page = await read<Timeline>(
        `/workflow-runs/${record.run.id}/timeline?after=${timeline.next_after}&limit=500`,
        token,
        c.signal,
      );
      if (c.signal.aborted) return;
      if (
        page.run_id !== record.run.id ||
        page.definition_sha256 !== record.definition.definition_sha256
      )
        throw new Error();
      const merged = { ...page, events: [...timeline.events, ...page.events] };
      if (cursor === null) setExtra(merged);
      else setFrozen({ ...record, timeline: merged });
    } catch {
      if (!c.signal.aborted) setError("Event page unavailable.");
    } finally {
      if (!c.signal.aborted) setMoreBusy(false);
    }
  }
  const t = record ? totals(record.stages) : null;
  return (
    <section className="workflow-observatory" aria-label="Workflow observatory">
      <header className="wf-heading">
        <div>
          <p className="eyebrow">GOVERNED PROCEDURES / READ ONLY</p>
          <h2>Workflow observatory</h2>
          <p>Inspect definitions, execution facts and retained evidence.</p>
        </div>
        <button
          onClick={() => {
            pageController.current?.abort();
            setMoreBusy(false);
            setCursor(null);
            setFrozen(null);
            setExtra(null);
            setRefresh((v) => v + 1);
          }}
        >
          Refresh records
        </button>
      </header>
      {window.location.hash.startsWith("#workflows?") && !initial && (
        <p role="alert">Invalid workflow link. No action was taken.</p>
      )}
      {error && <p role="alert">{error}</p>}
      {identityMismatch && (
        <p role="alert">
          The linked run does not match the selected workflow version. Select
          its actual version to inspect it.
        </p>
      )}
      <WorkflowCatalogue
        catalogue={catalogue}
        name={name}
        version={version}
        filter={filter}
        error={error}
        runs={runs}
        runId={runId}
        displayedDefinition={displayedDefinition}
        displayedGraph={displayedGraph}
        operations={operations}
        onFilter={setFilter}
        onName={chooseWorkflow}
        onVersion={(v) => {
          setVersion(v);
          chooseRun("");
          setSelected("");
        }}
        onRun={chooseRun}
      />
      {observed.loading && <p role="status">Loading run records…</p>}
      {observed.error && (
        <p role="alert">
          {observed.error}{" "}
          {record ? "Showing the previous snapshot; it may be stale." : ""}
        </p>
      )}
      {record && (
        <section className="wf-panel">
          <h3>Run {record.run.id}</h3>
          {cursor !== null && (
            <p>
              Current persisted snapshot below. Graph states follow the
              recorded-event cursor.
            </p>
          )}
          <p role="status">
            {record.run.status} ·{" "}
            {record.run.terminal_reason || "No terminal reason recorded"}
            {record.run.status !== "COMPLETED"
              ? " — no successful final outcome is established."
              : ""}
          </p>
          <Facts
            values={{
              Version: record.run.workflow.version,
              "Definition hash": record.run.workflow.definition_sha256,
              Started: timestamp(record.run.started_at),
              Finished: timestamp(record.run.finished_at),
              "Duration (seconds)": duration(
                record.run.started_at,
                record.run.finished_at,
              ),
              "Completed stages": `${t!.completed}/${record.stages.length}`,
              "Model invocations": t!.calls,
              Tokens: t!.tokens ?? "Unknown",
              "Cost (USD)": t!.cost ?? "Unknown",
            }}
          />
          <a
            href={link({
              workflow: record.run.workflow.name,
              version: record.run.workflow.version,
              run: record.run.id,
              stage: stageId || undefined,
            })}
          >
            Link to this inspection
          </a>
        </section>
      )}
      {displayedGraph && (
        <WorkflowGraph
          graph={displayedGraph}
          states={states}
          selected={stageId}
          onSelect={(id) => {
            setSelected(id);
            setSection("Stage details");
          }}
        />
      )}
      <div className="wf-tabs" role="tablist" aria-label="Inspection sections">
        {[
          "Overview",
          "Stage details",
          "Evidence & result",
          "Recorded events",
          "Comparison",
        ].map((s) => (
          <button
            key={s}
            role="tab"
            aria-selected={section === s}
            aria-controls="wf-tab-content"
            id={"wf-tab-" + s.replace(/[^a-z]/gi, "")}
            onClick={() => setSection(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id="wf-tab-content"
        aria-labelledby={"wf-tab-" + section.replace(/[^a-z]/gi, "")}
      >
        {section === "Overview" && (
          <section className="wf-panel">
            <h3>Understand this execution</h3>
            <p>
              Select a stage above to inspect its operation and actual attempt.
              Evidence & result holds retained output; Recorded events provides
              effect-free historical replay. Comparison describes two executions
              without assigning a quality score.
            </p>
            <p>
              Contract validation, reference identity and independent semantic
              verification are separate facts. Claim semantics remain Unverified
              unless explicitly established.
            </p>
          </section>
        )}
        {record &&
          spec &&
          ["Stage details", "Evidence & result"].includes(section) && (
            <StageInspector
              key={token + "|" + record.run.id + "|" + stageId}
              view={section === "Evidence & result" ? "evidence" : "details"}
              record={record}
              spec={spec}
              stage={stage}
              token={token}
              replayState={
                cursor === null ? undefined : states[stageId] || "Not recorded"
              }
            />
          )}
        {!record && spec && section === "Stage details" && (
          <section className="wf-panel">
            <h3>{spec.title}</h3>
            <Facts
              values={{
                Operation: spec.operation,
                Type: spec.type,
                Dependencies: spec.depends_on.join(", ") || "None",
                "Timeout seconds": spec.limits.timeout_seconds,
              }}
            />
            <p>Select a run to inspect actual execution.</p>
          </section>
        )}
        {timeline && section === "Recorded events" && (
          <RunTimeline
            timeline={timeline}
            cursor={cursor}
            onCursor={replay}
            onMore={() => void more()}
            onStage={setSelected}
          />
        )}
        {record && cursor === null && section === "Comparison" && (
          <section className="wf-panel">
            <label>
              Compare with run
              <select
                aria-label="Compare with run"
                value={comparison}
                onChange={(e) => setComparison(e.target.value)}
              >
                <option value="">Choose a second run</option>
                {runs
                  .filter((r) => r.id !== record.run.id)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      v{r.workflow.version} · {r.status} · {r.id}
                    </option>
                  ))}
              </select>
            </label>
            {compared.loading && <p>Loading comparison…</p>}
            {compared.error && <p role="alert">{compared.error}</p>}
          </section>
        )}
        {record &&
          compared.data &&
          cursor === null &&
          section === "Comparison" && (
            <RunComparison left={record} right={compared.data} />
          )}
      </div>
    </section>
  );
}
