from typing import Literal

from pydantic import Field, field_validator

from alive.bespoke.contracts import Hash, Objective, Ref
from alive.capabilities.manifest import Strict
from alive.research.contracts import ResearchReference


class ReviewRequest(Strict):
    profile: Literal[
        "approved-repository-inspection",
        "approved-repository-analysis",
        "intent-interpretation",
        "contextual-reasoning",
        "code-review-v1",
        "code-review-repair-v1",
    ] = "approved-repository-inspection"
    goal_ref: Ref
    approval_ref: Ref
    recipe_sha256: Hash
    objective: Objective
    paths: list[str] = Field(min_length=1, max_length=20)
    ttl_seconds: int = Field(default=300, ge=60, le=600)
    idempotency_key: str = Field(min_length=1, max_length=100)
    context_ref: Ref | None = None


class Confirmation(Strict):
    review_sha256: Hash


class LiveSetup(Strict):
    goal_ref: Ref
    approval_ref: Ref
    paths: list[str] = Field(min_length=1, max_length=8)
    max_calls: int = Field(default=6, ge=2, le=100)
    max_tokens: int = Field(default=200000, ge=1, le=2000000)
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    contextual: bool = False
    adaptive: bool = False
    code_review: bool = False
    completion_repair: bool = False
    research: bool = False


class LiveGoal(Strict):
    consent_ref: Ref
    goal: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=60)
    conversation_ref: Ref | None = None
    task_mode: Literal["general_contextual", "code_review", "research"] = "general_contextual"
    task_case_ids: list[str] | None = Field(default=None, max_length=8)
    repair_incomplete: bool = False
    strategy_mode: Literal["stateless", "contextual", "learned", "selective"] = "selective"
    # Qualification-only frozen labels. This is host-side verification metadata and is never
    # included in the model situation or sent to a provider.
    reference: ResearchReference | None = None

    @field_validator("task_case_ids")
    @classmethod
    def bounded_case_ids(cls, values):
        if values is not None and (
            len(set(values)) != len(values) or any(not v.strip() or len(v) > 40 for v in values)
        ):
            raise ValueError("Case IDs must be distinct, nonempty and at most 40 characters")
        return values


class ConversationRequest(Strict):
    consent_ref: Ref
    title: str = Field(default="New conversation", min_length=1, max_length=120)
