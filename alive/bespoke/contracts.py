"""Bounded, strict public and retained contracts. Page text has no instruction field."""

from typing import Annotated, Literal

from pydantic import Field

from alive.capabilities.manifest import ID, VERSION, Presentation, Strict
from alive.workflows.context import ContextProvenance

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Ref = Annotated[str, Field(min_length=1, max_length=36)]
Surface = Literal["repository", "controlled_evidence", "browser_document", "insufficient"]
Intent = Literal["inspect_implementation", "compare_claims", "assess_claims", "explore_arguments"]
Permission = Literal[
    "repository.read", "evidence.read", "model.infer", "workflow.write", "source.read"
]


class Constraints(Strict):
    max_model_calls: int = Field(default=0, ge=0, le=8)
    max_wall_seconds: int = Field(default=120, ge=1, le=3600)
    max_output_tokens: int = Field(default=0, ge=0, le=16384)
    outbound_allowed: bool = False
    permissions: list[Permission] = Field(default_factory=list, max_length=5)


class Objective(Strict):
    kind: Intent | None = None
    requested_outcome: str = Field(min_length=1, max_length=1000)


class RepositoryApproval(Strict):
    repository_ref: str = Field(min_length=1, max_length=100)
    snapshot_sha256: Hash
    paths: list[str] = Field(max_length=64)


class ObservedContext(Strict):
    context_schema: Literal["bespoke-context/v1"] = "bespoke-context/v1"
    goal_ref: Ref
    investigation_ref: Ref
    source_ref: Ref
    source_sha256: Hash
    surface: Surface
    provenance: ContextProvenance
    claims_count: int = Field(ge=0, le=16)
    sources_count: int = Field(ge=0, le=16)
    repositories: list[RepositoryApproval] = Field(max_length=32)
    inputs_sha256: Hash
    intent_origin: Literal["explicit_user", "unspecified"]
    inferred_intent: None = None


class RecommendRequest(Strict):
    context_schema: Literal["bespoke-context/v1"] = "bespoke-context/v1"
    approval_ref: Ref
    goal_ref: Ref
    investigation_ref: Ref
    source_ref: Ref
    source_sha256: Hash
    objective: Objective
    constraints: Constraints = Field(default_factory=Constraints)
    idempotency_key: str = Field(min_length=1, max_length=100)


class WorkflowPin(Strict):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: int = Field(ge=1, le=1000000)
    definition_sha256: Hash


class CapabilityPin(Strict):
    stage_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    id: str = Field(pattern=ID, max_length=64)
    version: str = Field(pattern=VERSION, max_length=32)
    manifest_sha256: Hash


class Recipe(Strict):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    version: str = Field(pattern=VERSION, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    context_types: list[Surface] = Field(min_length=1, max_length=4)
    intents: list[Intent] = Field(min_length=1, max_length=4)
    workflow: WorkflowPin
    capabilities: list[CapabilityPin] = Field(min_length=1, max_length=32)
    limits: Constraints
    required_evidence: Literal["approved_capture", "claims_and_sources"]
    output_artifact: Literal["captured_files", "workflow_result"]
    validation: Literal["none", "controlled_comparison", "reference_identity"]
    status: Literal["active", "future", "deprecated"] = "active"
    presentation: Presentation


Reason = Literal[
    "workflow_unavailable",
    "workflow_identity_changed",
    "capability_identity_changed",
    "missing_capability",
    "missing_inputs",
    "unsupported_context",
    "intent_unclear",
    "objective_incompatible",
    "missing_approved_source",
    "resource_limit_exceeded",
    "permission_not_grantable",
    "deployment_policy_conflict",
    "recipe_unavailable",
    "context_insufficient",
    "binding_changed",
]


class Candidate(Strict):
    recipe: Recipe
    recipe_sha256: Hash
    eligible: bool
    reasons: list[Reason] = Field(max_length=16)
    definition_id: Ref | None = None
    binding_sha256: Hash | None = None
    capability_identities: list[dict] = Field(default_factory=list, max_length=32)
    capability_policies: list[Hash] = Field(default_factory=list, max_length=32)
    procedure_sha256: Hash | None = None
    graph: dict | None = None
    suitability: int = Field(default=0, ge=0, le=100)
    factors: dict[str, int] = Field(default_factory=dict, max_length=10)


class Selection(Strict):
    schema_version: Literal["bespoke-rationale/v1"] = "bespoke-rationale/v1"
    policy_version: Literal["bespoke-selector/v1"] = "bespoke-selector/v1"
    scoring_version: Literal["bespoke-suitability/v1"] = "bespoke-suitability/v1"
    policy_sha256: Hash
    context_sha256: Hash
    catalogue_sha256: Hash
    context: ObservedContext
    objective: Objective
    constraints: Constraints
    candidates: list[Candidate] = Field(max_length=32)
    selected_recipe_sha256: Hash | None
    state: Literal["recommended", "abstained"]
    authorization: Literal["unavailable"] = "unavailable"
    uncertainty: list[str] = Field(max_length=8)
    distinct_procedures: int = Field(ge=0, le=32)
    outcome_ref: None = None
    independent_feedback_ref: None = None
    selection_model_calls: Literal[0] = 0


class RecommendationView(Strict):
    id: Ref
    created_at: str
    principal: str
    selection_sha256: Hash
    selection: Selection
