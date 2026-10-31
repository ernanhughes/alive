import type {
  Definition,
  Graph,
  WorkflowRun,
  WorkflowSummary,
} from "./contracts";
import { timestamp } from "./model";
interface Props {
  catalogue: WorkflowSummary[];
  name: string;
  version: number;
  filter: string;
  error: string;
  runs: WorkflowRun[];
  runId: string;
  displayedDefinition: Definition | null;
  displayedGraph: Graph | null;
  operations: { id: string; available: boolean; executable: boolean }[];
  onFilter: (s: string) => void;
  onName: (s: string) => void;
  onVersion: (n: number) => void;
  onRun: (s: string) => void;
}
export function WorkflowCatalogue({
  catalogue,
  name,
  version,
  filter,
  error,
  runs,
  runId,
  displayedDefinition,
  displayedGraph,
  operations,
  onFilter,
  onName,
  onVersion,
  onRun,
}: Props) {
  return (
    <>
      <div className="wf-controls">
        <label>
          Filter workflows
          <input value={filter} onChange={(e) => onFilter(e.target.value)} />
        </label>
        <label>
          Workflow
          <select
            aria-label="Workflow"
            value={name}
            onChange={(e) => onName(e.target.value)}
          >
            <option value="">Select workflow</option>
            {catalogue
              .filter((w) =>
                (w.name + " " + w.title)
                  .toLowerCase()
                  .includes(filter.toLowerCase()),
              )
              .map((w) => (
                <option key={w.name} value={w.name}>
                  {w.title} · {w.name}
                </option>
              ))}
          </select>
        </label>
        <label>
          Definition version
          <select
            aria-label="Definition version"
            value={version}
            onChange={(e) => {
              onVersion(+e.target.value);
            }}
          >
            {catalogue
              .find((w) => w.name === name)
              ?.versions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} · {v.status}
                </option>
              ))}
          </select>
        </label>
      </div>
      {!catalogue.length && !error && <p>No registered workflows loaded.</p>}
      {displayedDefinition && (
        <section className="wf-panel">
          <h3>
            {displayedDefinition.title}{" "}
            <small>
              v{displayedDefinition.version} · {displayedDefinition.status}
            </small>
          </h3>
          <p>{displayedDefinition.description}</p>
          <code>{displayedDefinition.definition_sha256}</code>
          <p>
            Definition integrity checked. Availability is not execution
            authorization.
          </p>
          {displayedGraph?.nodes.some(
            (n) =>
              !n.available ||
              !operations.some(
                (o) => o.id === n.operation && o.available && o.executable,
              ),
          ) && (
            <p>
              Contains unavailable operations. This definition is not
              executable.
            </p>
          )}
        </section>
      )}
      <section className="wf-panel">
        <h3>Execution history</h3>
        <p>
          Latest 200 runs for this workflow. Runs retain their own version and
          hash.
        </p>
        <label>
          Execution run
          <select
            aria-label="Execution run"
            value={runId}
            onChange={(e) => onRun(e.target.value)}
          >
            <option value="">Definition only</option>
            {runs.map((r) => (
              <option key={r.id} value={r.id}>
                {r.status} · v{r.workflow.version} · {timestamp(r.created_at)} ·{" "}
                {r.id}
              </option>
            ))}
          </select>
        </label>
        {!runs.length && <p>No recorded runs.</p>}
      </section>
    </>
  );
}
