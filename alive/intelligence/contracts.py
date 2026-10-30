"""Bounded immutable wire contracts; hashes identify data, never certify truth."""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ID = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:/-]+$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(min_length=1, max_length=1500)]
Number = Annotated[float, Field(allow_inf_nan=False)]
Origin = Literal["live", "fixture", "simulator"]
Split = Literal["train", "development", "test"]
Action = Literal["monitor", "retrieve", "investigate", "critic", "accept", "reject"]


class Contract(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", validate_default=True, revalidate_instances="always"
    )
    version: Literal[1] = 1


def digest(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


class Evidence(Contract):
    id: ID
    source_id: ID
    fingerprint: Digest
    observed_at: datetime
    origin: Origin
    qualification: Literal["current", "historical", "unqualified"]
    trust: Literal["admitted", "untrusted"]
    excerpt: Text

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value


class Observation(Contract):
    goal_id: ID
    event_id: ID
    episode_id: ID
    observed_at: datetime
    evidence: tuple[Evidence, ...] = Field(min_length=1, max_length=16)
    source_fingerprint: Digest
    safe_text: Text
    origin: Origin
    provenance: ID
    trust: Literal["admitted", "untrusted"]

    _aware = field_validator("observed_at")(Evidence.timezone_required.__func__)


class CandidateAction(Contract):
    id: ID
    action: Action
    expected_evidence_benefit: Number = Field(ge=0, le=1)
    expected_cost: Number = Field(ge=0, le=1000000)
    expected_risk: Number = Field(ge=0, le=1)
    proposal: Literal[True] = True


class EmpiricalState(Contract):
    """Explicit controlled Aster state, not an inferred general-world embedding."""

    subject: Literal["Aster"] = "Aster"
    predicate: Literal["endurance_hours"] = "endurance_hours"
    claim: Annotated[str, Field(pattern=r"^\d{1,6}$")]
    recent_event: Literal["source_replaced"] = "source_replaced"
    goal: Literal["resolve-current-claim"] = "resolve-current-claim"


class History(Contract):
    episode_id: ID
    observed_at: datetime
    origin: Origin
    split: Split
    qualification: Literal["observed", "unqualified"]
    evidence_refs: tuple[ID, ...] = Field(min_length=1, max_length=16)
    summary: Text

    _aware = field_validator("observed_at")(Evidence.timezone_required.__func__)


class Context(Contract):
    goal_id: ID
    goal: Literal["resolve-current-claim"] = "resolve-current-claim"
    scope: Literal["controlled-aster-v1"] = "controlled-aster-v1"
    policy_id: Literal["empirical-outcome-mean-v1"] = "empirical-outcome-mean-v1"
    state: EmpiricalState
    evidence: tuple[Evidence, ...] = Field(max_length=32)
    history: tuple[History, ...] = Field(default=(), max_length=16)
    candidates: tuple[CandidateAction, ...] = Field(max_length=6)
    reported_resources: Number = Field(ge=0, le=1000000)
    origin: Origin
    split: Split

    @model_validator(mode="after")
    def unique_candidates(self):
        if len({c.id for c in self.candidates}) != len(self.candidates) or len(
            {c.action for c in self.candidates}
        ) != len(self.candidates):
            raise ValueError("Duplicate candidate")
        return self


class Claim(Contract):
    subject: Annotated[str, Field(max_length=100)]
    predicate: Annotated[str, Field(max_length=100)]
    value: Annotated[str, Field(max_length=200)]
    citations: tuple[ID, ...] = Field(min_length=1, max_length=8)
    kind: Literal["model_opinion"] = "model_opinion"


class InvocationSummary(Contract):
    invocation_id: ID
    reservation_id: ID
    operation: Literal["cognition.role"]
    provider: ID
    model: ID
    provenance: Literal["fixture", "model"]
    receipt_id: ID | None = None
    prompt_tokens: int = Field(ge=0, le=10000000)
    completion_tokens: int = Field(ge=0, le=10000000)


class ReasoningResult(Contract):
    invocation: InvocationSummary
    summary: Text
    claims: tuple[Claim, ...] = Field(max_length=4)
    limitations: tuple[Text, ...] = Field(max_length=12)
    recommendation: Literal["proceed", "investigate", "revise", "abstain"]


class DecisionProposal(Contract):
    id: ID
    episode_id: ID
    goal_id: ID
    action: CandidateAction | None
    candidate_ids: tuple[ID, ...] = Field(max_length=6)
    policy_name: Literal["empirical-outcome-mean-v1"]
    policy_version: int = Field(ge=0)
    policy_hash: Digest
    state_hash: Digest
    reason: Text
    estimated_value: Number | None = None
    samples: int = Field(ge=0)
    uncertainty: Text = "Unknown generalization; observed means have small-sample uncertainty."
    invocation: InvocationSummary | None = None
    required_authorization: Literal["external_governor_required"] = "external_governor_required"
    executed: Literal[False] = False


class RewardComponent(Contract):
    name: ID
    value: Number = Field(ge=-1.15, le=1)
    source_ref: ID
    basis: Literal["observed"] = "observed"


class OutcomeFeedback(Contract):
    id: ID
    proposal_id: ID
    episode_id: ID
    goal_id: ID
    observed_action: Action
    executed: bool
    result: Text
    measurements: tuple[Evidence, ...] = Field(min_length=1, max_length=16)
    rewards: tuple[RewardComponent, ...] = Field(min_length=1, max_length=8)
    completion: Literal["completed", "failed", "interrupted"]
    event_at: datetime
    origin: Origin
    split: Split

    _aware = field_validator("event_at")(Evidence.timezone_required.__func__)

    @model_validator(mode="after")
    def reward_bounds(self):
        if not -1.15 <= self.reward <= 1:
            raise ValueError("Reward sum out of range")
        refs = {e.id for e in self.measurements}
        if any(c.source_ref not in refs for c in self.rewards):
            raise ValueError("Missing measurement provenance")
        return self

    @property
    def reward(self) -> float:
        return sum(c.value for c in self.rewards)


class ExperienceTransition(Contract):
    proposal: DecisionProposal
    before_state: EmpiricalState
    proposed_action: Action
    executed_action: Action
    outcome: OutcomeFeedback
    before_policy_hash: Digest
    after_policy_hash: Digest
    before_version: int = Field(ge=0)
    after_version: int = Field(ge=0)
    before_samples: int = Field(ge=0)
    after_samples: int = Field(ge=0)
    origin: Origin
    split: Split
    usage: InvocationSummary | None
    prediction_error: Number | None = None


class TraceEvent(Contract):
    sequence: int = Field(ge=0, le=31)
    stage: Literal["input", "evidence", "invocation", "decision", "error", "feedback", "shadow"]
    summary: Text
    reference: ID | None = None


class RunResult(Contract):
    status: Literal["proposed", "abstained", "failed", "cancelled"]
    error_code: (
        Literal[
            "reasoning_unavailable",
            "not_supported",
            "timeout",
            "invalid_input_or_adapter",
            "cancelled",
        ]
        | None
    ) = None
    explanation: Text
    proposal: DecisionProposal | None = None
    reasoning: ReasoningResult | None = None
    trace: tuple[TraceEvent, ...] = Field(max_length=32)


class FeedbackResult(Contract):
    status: Literal["accepted", "rejected", "duplicate", "failed"]
    explanation: Text
    transition: ExperienceTransition | None = None
    trace: tuple[TraceEvent, ...] = Field(default=(), max_length=32)


class ShadowResult(Contract):
    status: Literal["available", "unavailable"]
    explanation: Text
    simulation_only: Literal[True] = True
    checkpoint_hash: Digest | None = None
    action: Action | None = None
    q_values: tuple[Number, ...] = Field(default=(), max_length=6)
    permitted: tuple[bool, ...] = Field(default=(), max_length=6)
    predicted_reward: Number | None = None
    predicted_next_state: tuple[Number, ...] = Field(default=(), max_length=18)


class RevisitResult(Contract):
    current: RunResult
    frozen_action: Action | None
    frozen_policy_hash: Digest
