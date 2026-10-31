import type { Graph, RecordedEvent, Recording, StageRun } from "./contracts";

export const NAME = /^[a-z][a-z0-9_-]{0,63}$/;
export const STAGE = /^[a-z][a-z0-9_-]{0,31}$/;
export const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export interface Selection {
  workflow: string;
  version: number;
  run?: string;
  stage?: string;
}
export function parseLink(hash: string): Selection | null {
  if (!hash.startsWith("#workflows?") || hash.length > 350) return null;
  const p = new URLSearchParams(hash.slice(11));
  if (
    [...p.keys()].some(
      (k) => !["workflow", "version", "run", "stage"].includes(k),
    ) ||
    [...p.keys()].some((k) => p.getAll(k).length !== 1)
  )
    return null;
  const workflow = p.get("workflow") || "",
    v = p.get("version") || "";
  const run = p.get("run") || undefined,
    stage = p.get("stage") || undefined;
  if (
    !NAME.test(workflow) ||
    !/^[1-9]\d{0,6}$/.test(v) ||
    +v > 1_000_000 ||
    (run && !UUID.test(run)) ||
    (stage && !STAGE.test(stage))
  )
    return null;
  return { workflow, version: +v, run, stage };
}
export function link(s: Selection): string {
  const p = new URLSearchParams({
    workflow: s.workflow,
    version: String(s.version),
  });
  if (s.run) p.set("run", s.run);
  if (s.stage) p.set("stage", s.stage);
  const hash = "#workflows?" + p;
  if (!parseLink(hash)) throw new Error("Invalid workflow link");
  return hash;
}
export function timestamp(value: string | null | undefined): string {
  if (!value || !Number.isFinite(Date.parse(value))) return "Not recorded";
  return new Date(value).toLocaleString("en-GB");
}
export function text(value: unknown): string {
  const raw =
    typeof value === "string"
      ? value
      : (JSON.stringify(value, null, 2) ?? "Not recorded");
  return raw.length > 16000
    ? raw.slice(0, 16000) + "\n[Display truncated]"
    : raw;
}
export function layout(graph: Graph): Map<string, { x: number; y: number }> {
  if (
    graph.nodes.length > 32 ||
    new Set(graph.nodes.map((n) => n.id)).size !== graph.nodes.length
  )
    throw new Error("Invalid graph bounds");
  const result = new Map<string, { x: number; y: number }>(),
    remaining = [...graph.nodes];
  const columns = new Map<number, number>();
  while (remaining.length) {
    const i = remaining.findIndex((n) =>
      graph.edges.filter((e) => e.to === n.id).every((e) => result.has(e.from)),
    );
    if (i < 0) throw new Error("Invalid graph dependency");
    const [n] = remaining.splice(i, 1);
    const x = Math.max(
      0,
      ...graph.edges
        .filter((e) => e.to === n.id)
        .map((e) => result.get(e.from)!.x + 1),
    );
    const y = columns.get(x) || 0;
    columns.set(x, y + 1);
    result.set(n.id, { x, y });
  }
  if (graph.edges.some((e) => !result.has(e.from) || !result.has(e.to)))
    throw new Error("Missing graph node");
  return result;
}
// This is an event projection, never a reconstruction from the final snapshot.
export function replayStates(events: RecordedEvent[]): Record<string, string> {
  const states: Record<string, string> = {};
  for (const e of events)
    if (e.stage_id) {
      if (e.event_type === "workflow.stage.claimed")
        states[e.stage_id] = "RUNNING";
      if (e.event_type === "workflow.stage.result")
        states[e.stage_id] = "COMPLETED";
    }
  return states;
}
export function totals(stages: StageRun[]) {
  const models = stages.filter((s) => s.model_invocation_id);
  return {
    calls: models.length,
    completed: stages.filter((s) => s.state === "COMPLETED").length,
    tokens: models.every((s) => s.usage !== null)
      ? models.reduce((n, s) => n + s.usage!.total_tokens, 0)
      : null,
    cost: models.every((s) => s.cost_usd !== null)
      ? models.reduce((n, s) => n + s.cost_usd!, 0)
      : null,
  };
}
export function assertRecording(r: Recording): Recording {
  if (
    r.run.id !== r.timeline.run_id ||
    !r.definition.integrity.verified ||
    r.run.workflow.definition_id !== r.definition.id ||
    r.timeline.definition_id !== r.definition.id ||
    r.run.workflow.definition_sha256 !== r.definition.definition_sha256 ||
    r.graph.definition_sha256 !== r.definition.definition_sha256 ||
    r.timeline.definition_sha256 !== r.definition.definition_sha256 ||
    r.graph.name !== r.run.workflow.name ||
    r.graph.version !== r.run.workflow.version ||
    r.stages.some(
      (s) =>
        s.run_id !== r.run.id ||
        !r.graph.nodes.some((n) => n.id === s.stage_id),
    ) ||
    r.timeline.events.some(
      (e, i, a) =>
        e.run_id !== r.run.id || (i > 0 && e.sequence <= a[i - 1].sequence),
    )
  )
    throw new Error("History identity mismatch");
  layout(r.graph);
  return r;
}
