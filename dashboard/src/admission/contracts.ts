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
export interface Profile {
  recipe_sha256: string;
  recipe: Recipe;
}
export interface Admission {
  id: string;
  review_sha256: string;
  state: string;
  authorization_state: "pending" | "approved" | "revoked" | "expired";
  terms: {
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
  if (
    !grant ||
    grant.max_model_calls !== 0 ||
    grant.max_output_tokens !== 0 ||
    grant.outbound_approved !== false ||
    grant.wall_seconds !== 30 ||
    value.terms.expected_output !== "captured_files" ||
    !value.terms.candidate?.graph
  )
    throw new Error(
      "Admission exceeds the supported no-inference inspection profile.",
    );
  return value;
}
