import { useEffect, useState } from "react";
import type {
  Artifact,
  PiReceipt,
  Recording,
  StageSpec,
  StageRun,
  Validation,
} from "./contracts";
import { artifact, receipt } from "./client";
import { text, timestamp } from "./model";
import { StructuredRecord } from "./StructuredRecord";
import { capabilityLink } from "../capabilities/contracts";

export function Facts({ values }: { values: Record<string, unknown> }) {
  return (
    <dl className="wf-facts">
      {Object.entries(values).map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v === null || v === undefined ? "Not recorded" : text(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
export function ValidationView({ value }: { value: Validation }) {
  return (
    <section>
      <h4>Validation</h4>
      <Facts
        values={{
          Contract: value.contract_status,
          Structure: value.structural_status,
          "Reference identity": value.reference_identity_status,
          "Claim semantics":
            value.semantic_status === "unverified"
              ? "Unverified"
              : value.semantic_status,
          "Independent verification": value.independent_verification
            ? "Recorded"
            : "Not performed",
        }}
      />
      <p>
        Execution and structural checks do not establish that claims are true.
      </p>
    </section>
  );
}
export function PiReceiptPanel({ value }: { value: PiReceipt }) {
  return (
    <section aria-label="Pi receipt">
      <h4>Actual Pi receipt</h4>
      <Facts
        values={{
          "Pi run": value.run_id,
          Reservation: value.reservation_ref,
          "Settlement state": value.state,
          Reason: value.terminal_reason,
          "Requested upstream model": value.identity.requested_upstream_model,
          "Reported local provider alias": value.identity.pi_observed.provider,
          "Reported local model alias": value.identity.pi_observed.model,
          "Admitted requests": value.requests.admitted,
          "Request ceiling": value.requests.ceiling,
          "Cost (USD)": value.cost.usd ?? "Unknown",
        }}
      />
      <p>{value.cost.note}</p>
      <Facts values={value.settlement} />
      <ul>
        {value.requests.items.map((r) => (
          <li key={r.seq}>
            Request {r.seq}: {r.state} ·{" "}
            {r.error_category || "No error recorded"}
            <Facts values={{ Usage: r.usage }} />
          </li>
        ))}
      </ul>
    </section>
  );
}
export function ArtifactPanel({ value }: { value: Artifact }) {
  return (
    <section aria-label="Retained artifact">
      <h4>
        {value.workflow_completed
          ? "Retained result"
          : "Partial / historical artifact"}
      </h4>
      <p role="status">
        Parent workflow: {value.run_status} ·{" "}
        {value.terminal_reason || "No terminal reason"}
        {!value.workflow_completed
          ? " — this artifact is not a successful final outcome."
          : ""}
      </p>
      <Facts
        values={{
          Artifact: value.artifact_id,
          "SHA-256": value.sha256,
          "Source status": value.source_status,
          "Independent feedback": value.independent_feedback
            ? "Recorded"
            : "Not recorded",
          "Intelligence learning":
            value.intelligence_episode_id ?? "No linked episode recorded",
        }}
      />
      <h4>Result</h4>
      <StructuredRecord value={value.result} />
      <h4>Assessment</h4>
      <StructuredRecord value={value.assessment} />
      <h4>Evidence and provenance</h4>
      <ul>
        {value.evidence_refs.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <StructuredRecord value={value.context_provenance} />
      <details>
        <summary>Bounded raw artifact record</summary>
        <pre>{text(value)}</pre>
      </details>
    </section>
  );
}

export function StageInspector({
  record,
  spec,
  stage,
  replayState,
  token,
  view,
}: {
  record: Recording;
  spec: StageSpec;
  stage?: StageRun;
  replayState?: string;
  token: string;
  view: "details" | "evidence";
}) {
  return (
    <section className="wf-panel" aria-label="Stage inspector">
      <h3>{spec.title}</h3>
      <Facts
        values={{
          "Stage ID": spec.id,
          "Run ID": record.run.id,
          Definition: `${record.definition.name} v${record.definition.version}`,
          "Definition hash": record.definition.definition_sha256,
          Operation: spec.operation,
          Type: spec.type,
          Dependencies: spec.depends_on.join(", ") || "None",
          "Stage timeout (seconds)": spec.limits.timeout_seconds,
        }}
      />
      {stage?.capability && (
        <p>
          Retained capability: {stage.capability.id} v{stage.capability.version}{" "}
          <a
            href={capabilityLink({
              id: stage.capability.id,
              version: stage.capability.version,
              sha: stage.capability.manifest_sha256,
            })}
          >
            Open catalogue entry
          </a>
        </p>
      )}
      {replayState !== undefined ? (
        <p>
          Recorded state at cursor: {replayState}. Later snapshot details are
          withheld during replay.
        </p>
      ) : stage ? (
        <StageDetails
          key={stage.id}
          record={record}
          stage={stage}
          token={token}
          view={view}
        />
      ) : (
        <p>No attempt recorded.</p>
      )}
    </section>
  );
}
// Token is supplied by context-free props rather than storage, so credential changes remount reads.
export function StageDetails({
  record,
  stage,
  token = "",
  view = "details",
}: {
  record: Recording;
  stage: StageRun;
  token?: string;
  view?: "details" | "evidence";
}) {
  const [pi, setPi] = useState<PiReceipt | null>(null),
    [result, setResult] = useState<Artifact | null>(null);
  const [mode, setMode] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    setPi(null);
    setResult(null);
    setError("");
    if (!mode || !token) return;
    const c = new AbortController();
    let active = true;
    (async () => {
      try {
        if (mode === "pi") {
          const v = await receipt(record.run.id, stage.id, token, c.signal);
          if (
            v.run_id !== record.run.id ||
            v.attempt_id !== stage.id ||
            v.stage_id !== stage.stage_id ||
            v.receipt.run_id !== stage.pi_run_id ||
            v.receipt.reservation_ref !== stage.model_invocation_id
          )
            throw new Error();
          if (active) setPi(v.receipt);
        } else {
          const v = await artifact(
            record.run.id,
            stage.stage_id,
            token,
            c.signal,
          );
          if (
            v.run_id !== record.run.id ||
            v.stage_id !== stage.stage_id ||
            v.definition_sha256 !== record.definition.definition_sha256 ||
            v.run_status !== record.run.status
          )
            throw new Error();
          if (active) setResult(v);
        }
      } catch {
        if (active)
          setError(
            "Record unavailable, stale or integrity check failed. Refresh the run.",
          );
      }
    })();
    return () => {
      active = false;
      c.abort();
    };
  }, [
    mode,
    token,
    record.run.id,
    record.run.status,
    record.definition.definition_sha256,
    stage.id,
    stage.stage_id,
    stage.pi_run_id,
    stage.model_invocation_id,
  ]);
  return (
    <>
      {view === "details" && (
        <>
          <h4>Current persisted snapshot</h4>
          <Facts
            values={{
              Attempt: stage.id,
              "Attempt number": stage.attempt,
              State: stage.state,
              Uncertainty: stage.uncertainty,
              "Error category": stage.error_category,
              Started: timestamp(stage.started_at),
              Finished: timestamp(stage.finished_at),
              "Duration (seconds)": stage.duration_seconds,
              "Input reference": stage.input_ref,
              "Input hash": stage.input_sha256,
              "Output reference": stage.output_ref,
              "Output hash": stage.output_sha256,
              "Authorization reference": record.run.authorization_ref,
              "Approved context reference": record.run.input_ref,
              "Bound input hash": record.run.input_sha256,
              "Requested model": stage.model_requested,
              Tokens: stage.usage?.total_tokens ?? "Unknown",
              "Cost (USD)": stage.cost_usd ?? "Unknown",
            }}
          />
        </>
      )}
      <ValidationView value={stage.validation} />
      <h4>Evidence references</h4>
      <ul>
        {stage.evidence_refs.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      {view === "details" &&
        (stage.pi_run_id ? (
          <button onClick={() => setMode("pi")}>Open actual Pi receipt</button>
        ) : (
          <p>
            {stage.model_invocation_id
              ? "Model invocation recorded; Pi receipt not yet available."
              : "Deterministic stage — no model invocation recorded."}
          </p>
        ))}
      {view === "evidence" &&
        stage.operation === "result.record" &&
        stage.output_ref && (
          <button onClick={() => setMode("artifact")}>
            Open retained artifact
          </button>
        )}
      {mode && !pi && !result && !error && (
        <p role="status">Loading authenticated record…</p>
      )}
      {error && <p role="alert">{error}</p>}
      {pi && <PiReceiptPanel value={pi} />}{" "}
      {result && <ArtifactPanel value={result} />}
    </>
  );
}
