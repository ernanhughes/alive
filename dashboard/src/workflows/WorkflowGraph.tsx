import { useId } from "react";
import type { Graph } from "./contracts";
import { layout } from "./model";

export function WorkflowGraph({
  graph,
  states,
  selected,
  onSelect,
}: {
  graph: Graph;
  states: Record<string, string>;
  selected: string;
  onSelect: (id: string) => void;
}) {
  const marker = useId().replace(/:/g, "");
  let positions: ReturnType<typeof layout>;
  try {
    positions = layout(graph);
  } catch {
    return (
      <p role="alert">Graph unavailable: invalid dependencies or bounds.</p>
    );
  }
  const width =
    Math.max(1, ...[...positions.values()].map((p) => p.x + 1)) * 220;
  const height =
    Math.max(1, ...[...positions.values()].map((p) => p.y + 1)) * 110;
  return (
    <section aria-label="Workflow graph" className="wf-graph">
      <div className="wf-canvas">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${graph.name} version ${graph.version} dependency graph`}
        >
          <defs>
            <marker
              id={marker}
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
            >
              <path d="M0,0 L8,4 L0,8" fill="currentColor" />
            </marker>
          </defs>
          {graph.edges.map((e) => {
            const a = positions.get(e.from)!,
              b = positions.get(e.to)!;
            return (
              <path
                key={e.from + "-" + e.to}
                d={`M${a.x * 220 + 200},${a.y * 110 + 45} L${b.x * 220 + 10},${b.y * 110 + 45}`}
                stroke="currentColor"
                fill="none"
                markerEnd={`url(#${marker})`}
              />
            );
          })}
          {graph.nodes.map((n) => {
            const p = positions.get(n.id)!;
            return (
              <g
                role="button"
                tabIndex={0}
                aria-label={`Select ${n.title}`}
                onClick={() => onSelect(n.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(n.id);
                  }
                }}
                key={n.id}
                transform={`translate(${p.x * 220 + 10},${p.y * 110 + 10})`}
              >
                <rect
                  width="190"
                  height="76"
                  rx="10"
                  className={selected === n.id ? "wf-node selected" : "wf-node"}
                />
                <text x="12" y="25">
                  {n.title.slice(0, 23)}
                </text>
                <text x="12" y="48" className="wf-node-state">
                  {states[n.id] || "Not recorded"}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <ol className="wf-stage-list" aria-label="Select a stage">
        {graph.nodes.map((n) => (
          <li key={n.id}>
            <button
              aria-pressed={selected === n.id}
              onClick={() => onSelect(n.id)}
            >
              <strong>{n.title}</strong>
              <span>{states[n.id] || "Not recorded"}</span>
              <small>
                {n.operation} ·{" "}
                {graph.edges
                  .filter((e) => e.to === n.id)
                  .map((e) => e.from)
                  .join(", ") || "No dependencies"}
              </small>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
