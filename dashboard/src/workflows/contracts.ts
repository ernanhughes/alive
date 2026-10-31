export interface WorkflowSummary {
  name: string;
  title: string;
  latest_version: number;
  latest_status: string;
  versions: {
    version: number;
    status: string;
    definition_sha256: string;
    stage_count: number;
  }[];
}
export interface StageSpec {
  id: string;
  title: string;
  type: string;
  operation: string;
  depends_on: string[];
  inputs: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  limits: { timeout_seconds: number; max_output_tokens?: number };
}
export interface Definition {
  id: string;
  name: string;
  title: string;
  description: string;
  version: number;
  status: string;
  definition_sha256: string;
  integrity: { verified: boolean };
  definition: { stages: StageSpec[]; limits: Record<string, number> };
}
export interface Graph {
  name: string;
  version: number;
  definition_sha256: string;
  nodes: {
    id: string;
    title: string;
    type: string;
    operation: string;
    available: boolean;
  }[];
  edges: { from: string; to: string }[];
}
export interface WorkflowRun {
  id: string;
  workflow: {
    name: string;
    version: number;
    definition_id: string;
    definition_sha256: string;
  };
  status: string;
  terminal: boolean;
  terminal_reason: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  goal_id: string | null;
  input_ref: string | null;
  input_sha256: string | null;
  authorization_ref: string | null;
  budget: Record<string, unknown>;
}
export interface Validation {
  contract_status: string;
  structural_status: string;
  reference_identity_status: string;
  semantic_status: string;
  independent_verification: boolean;
}
export interface StageRun {
  id: string;
  run_id: string;
  stage_id: string;
  attempt: number;
  type: string;
  operation: string;
  state: string;
  terminal: boolean;
  uncertainty: string;
  error_category: string | null;
  input_ref: string | null;
  input_sha256: string | null;
  output_ref: string | null;
  output_sha256: string | null;
  pi_run_id: string | null;
  model_invocation_id: string | null;
  evidence_refs: string[];
  validation: Validation;
  model_requested: string | null;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null;
  cost_usd: number | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}
export interface RecordedEvent {
  sequence: number;
  event_type: string;
  occurred_at: string;
  run_id: string;
  stage_id: string | null;
  attempt_id: string | null;
  pi_run_id: string | null;
  output_ref: string | null;
  status: string | null;
}
export interface Timeline {
  run_id: string;
  definition_id: string;
  definition_sha256: string;
  events: RecordedEvent[];
  next_after: number;
  has_more: boolean;
  complete_transition_history: false;
  history_note: string;
}
export interface Inspection {
  run: WorkflowRun;
  definition: Definition;
  graph: Graph;
}
export interface Recording extends Inspection {
  stages: StageRun[];
  timeline: Timeline;
}
export interface PiReceipt {
  run_id: string;
  reservation_ref: string;
  state: string;
  terminal_reason: string | null;
  identity: {
    requested_upstream_model: string | null;
    pi_observed: { provider: string | null; model: string | null };
  };
  requests: {
    ceiling: number;
    admitted: number;
    counts: Record<string, number>;
    items: {
      seq: number;
      state: string;
      usage: Record<string, number> | null;
      error_category: string | null;
    }[];
  };
  settlement: Record<string, unknown>;
  cost: { usd: number | null; note: string };
}
export interface Artifact {
  artifact_id: string;
  sha256: string;
  run_id: string;
  stage_id: string;
  definition_sha256: string;
  workflow_completed: boolean;
  run_status: string;
  terminal_reason: string | null;
  result: Record<string, unknown>;
  assessment: Record<string, unknown>;
  evidence_refs: string[];
  context_provenance: Record<string, unknown>;
  independent_feedback: false;
  intelligence_episode_id: null;
  source_status: string;
}
