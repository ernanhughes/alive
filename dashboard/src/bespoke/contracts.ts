import type { Graph, WorkflowRun } from "../workflows/contracts";

export interface ContextRef {
  approval_ref: string;
  goal_ref: string;
  investigation_ref: string;
  source_ref: string;
  source_sha256: string;
}
export interface Limits {
  max_model_calls: number;
  max_wall_seconds: number;
  max_output_tokens: number;
  outbound_allowed: boolean;
  permissions: string[];
}
export interface Recipe {
  id: string;
  version: string;
  name: string;
  description: string;
  context_types: string[];
  intents: string[];
  workflow: { name: string; version: number; definition_sha256: string };
  capabilities: {
    stage_id: string;
    id: string;
    version: string;
    manifest_sha256: string;
  }[];
  limits: Limits;
  required_evidence: string;
  output_artifact: string;
  validation: string;
  status: string;
}
export interface CatalogueEntry {
  recipe: Recipe;
  recipe_sha256: string;
  status: string;
  reasons: string[];
}
export interface Candidate extends Omit<CatalogueEntry, "status"> {
  eligible: boolean;
  factors: Record<string, number>;
  suitability: number;
  graph: Graph | null;
  definition_id: string | null;
  binding_sha256: string | null;
  procedure_sha256: string | null;
}
export interface Recommendation {
  id: string;
  created_at: string;
  principal: string;
  selection_sha256: string;
  selection: {
    state: "recommended" | "abstained";
    authorization: "unavailable";
    selected_recipe_sha256: string | null;
    context: { surface: string; source_ref: string; intent_origin: string };
    objective: { kind: string | null; requested_outcome: string };
    constraints: Limits;
    candidates: Candidate[];
    distinct_procedures: number;
    uncertainty: string[];
    policy_version: string;
    scoring_version: string;
  };
}
export type LinkedRuns = { runs: WorkflowRun[] };
