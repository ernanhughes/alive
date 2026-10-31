import type { Recording } from "./contracts";
import { totals } from "./model";
import { Facts } from "./StageInspector";
export function RunComparison({
  left,
  right,
}: {
  left: Recording;
  right: Recording;
}) {
  if (left.run.workflow.name !== right.run.workflow.name)
    return <p role="alert">Compare runs within the same workflow.</p>;
  const ids = [
    ...new Set([...left.graph.nodes, ...right.graph.nodes].map((n) => n.id)),
  ];
  const columns = [left, right];
  return (
    <section className="wf-panel" aria-label="Run comparison">
      <h3>Run comparison</h3>
      <p>
        Descriptive comparison. Speed, usage and cost do not establish quality.
      </p>
      <div className="wf-comparison">
        {columns.map((r) => {
          const t = totals(r.stages);
          return (
            <div key={r.run.id}>
              <h4>{r.run.id}</h4>
              <Facts
                values={{
                  Version: r.run.workflow.version,
                  Hash: r.run.workflow.definition_sha256,
                  Status: r.run.status,
                  Reason: r.run.terminal_reason,
                  "Model invocations": t.calls,
                  Tokens: t.tokens ?? "Unknown",
                  "Cost (USD)": t.cost ?? "Unknown",
                }}
              />
              <h4>Declared dependencies</h4>
              <ul>
                {r.graph.edges.map((e) => (
                  <li key={e.from + e.to}>
                    {e.from} → {e.to}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      <div className="wf-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Stable stage ID</th>
              <th>Selected run</th>
              <th>Comparison run</th>
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => (
              <tr key={id}>
                <th>{id}</th>
                {columns.map((r) => {
                  const s = r.stages.filter((s) => s.stage_id === id).at(-1);
                  return (
                    <td key={r.run.id}>
                      {s ? (
                        <>
                          <strong>{s.state}</strong>
                          <p>{s.operation}</p>
                          <p>
                            {s.duration_seconds ?? "Unknown"} seconds ·{" "}
                            {s.uncertainty}
                          </p>
                          <p>
                            Contract: {s.validation.contract_status}; reference
                            identity: {s.validation.reference_identity_status};
                            semantics: {s.validation.semantic_status}
                          </p>
                          <small>
                            {s.output_ref || "No artifact reference"}
                          </small>
                        </>
                      ) : (
                        "Not present"
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
