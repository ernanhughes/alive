import type { Goal } from "../api";
import type { Candidate, Recipe } from "../bespoke/contracts";
import type { WorkflowRun } from "../workflows/contracts";

export interface Source {
  approval_ref: string;
  capture_ref: string;
  label: string;
  content_sha256: string;
  scope: { all?: boolean; items?: string[] };
  inventory: { items: { item: string; bytes?: number; sha256?: string }[] };
  expires_at: string;
}
export type ProfileName =
  "approved-repository-inspection" | "approved-repository-analysis";
export const PROFILE_LIMITS: Record<
  ProfileName,
  { files: number; bytes: number; model: boolean }
> = {
  "approved-repository-inspection": { files: 20, bytes: 32768, model: false },
  "approved-repository-analysis": { files: 8, bytes: 8192, model: true },
};
export interface Profile {
  profile: ProfileName;
  model_call: boolean;
  recipe_sha256: string;
  recipe: Recipe;
}
export interface Disclosure {
  operation: string;
  destination: {
    kind: string;
    provider: string;
    transport: string;
    host: string | null;
    model: string;
  };
  files: { path: string; bytes: number }[];
  source_bytes: number;
  reserved_request_bytes: number;
  max_model_calls: number;
  max_output_tokens: number;
  leaves_host: boolean;
  cost: string;
  cancellation: string;
  retention: string;
}
export interface Finding {
  finding_id: string;
  model_assessment: {
    title: string;
    category: string;
    severity: string;
    explanation: string;
    uncertainty: string;
    suggested_verification: string;
  };
  reference_check: {
    status: string;
    evidence: {
      file: string;
      status: string;
      line_start?: number;
      line_end?: number;
    }[];
  };
  verification: string;
}
export interface Report {
  admission_id: string;
  run_id: string;
  artifact_sha256: string;
  result: {
    summary: string;
    findings: Finding[];
    unresolved_questions: string[];
    report_markdown: string;
  };
  assessment: {
    reference_identity_status: string;
    findings_total: number;
    findings_with_valid_references: number;
    findings_with_unsupported_references: number;
    semantic_status: string;
    independent_verification: boolean;
  };
  usage: {
    status: string;
    provider: string;
    model: string;
    reserved_tokens: number;
    usage: Record<string, unknown>;
    latency_ms: number;
    model_calls: number;
    cost: string;
  };
  verification: string;
}
export interface Admission {
  id: string;
  review_sha256: string;
  state: string;
  authorization_state: "pending" | "approved" | "revoked" | "expired";
  terms: {
    profile?: ProfileName;
    model_disclosure?: Disclosure;
    source: {
      resources: {
        source_ref: string;
        approval_id: string;
        content_sha256: string;
        scope_sha256: string;
      };
      scope: { all?: boolean; items?: string[] };
      inventory: { items: { item: string; bytes?: number; sha256?: string }[] };
      label: string;
    };
    goal: Pick<Goal, "id" | "title">;
    candidate: Candidate;
    proposed_grant_data: {
      max_model_calls: number;
      max_output_tokens: number;
      wall_seconds: number;
      outbound_approved: boolean;
      expires_at: string;
      inputs?: { paths?: string[] };
    };
    paths?: string[];
    expected_output: string;
    objective: { kind: string; requested_outcome: string };
  };
  run: WorkflowRun | null;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const SHA = /^[0-9a-f]{64}$/;
export function admissionRef(hash: string): string | null {
  if (!hash.startsWith("#admission?") || hash.length > 100) return null;
  const values = new URLSearchParams(hash.slice(11));
  const id = values.get("id");
  return id && UUID.test(id) && values.getAll("id").length === 1 ? id : null;
}
export function checkedAdmission(
  value: Admission,
  expectedId?: string,
): Admission {
  if (
    !value ||
    !UUID.test(value.id) ||
    !SHA.test(value.review_sha256) ||
    (expectedId && value.id !== expectedId) ||
    !["pending", "approved", "revoked", "expired"].includes(
      value.authorization_state,
    )
  )
    throw new Error("Admission identity or authorization state is invalid.");
  const grant = value.terms?.proposed_grant_data;
  const disclosure = value.terms?.model_disclosure;
  const analysis = value.terms?.profile === "approved-repository-analysis";
  const inspection = value.terms?.profile === undefined;
  if (
    !grant ||
    !value.terms.candidate?.graph ||
    !(analysis || inspection) ||
    (inspection &&
      (grant.max_model_calls !== 0 ||
        grant.max_output_tokens !== 0 ||
        grant.outbound_approved !== false ||
        grant.wall_seconds !== 30 ||
        disclosure !== undefined ||
        value.terms.expected_output !== "captured_files")) ||
    (analysis &&
      (grant.max_model_calls !== 1 ||
        grant.max_output_tokens > 1536 ||
        grant.outbound_approved !== true ||
        grant.wall_seconds !== 180 ||
        !disclosure ||
        disclosure.leaves_host !== true ||
        disclosure.max_model_calls !== 1 ||
        value.terms.expected_output !== "workflow_result"))
  )
    throw new Error(
      "Admission exceeds the supported inspection and analysis profiles.",
    );
  return value;
}
