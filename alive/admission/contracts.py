from typing import Literal

from pydantic import Field

from alive.bespoke.contracts import Hash, Objective, Ref
from alive.capabilities.manifest import Strict


class ReviewRequest(Strict):
    profile: Literal[
        "approved-repository-inspection",
        "approved-repository-analysis",
        "intent-interpretation",
        "contextual-reasoning",
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


class LiveGoal(Strict):
    consent_ref: Ref
    goal: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=60)
    conversation_ref: Ref | None = None
    strategy_mode: Literal["stateless", "contextual", "learned", "selective"] = "selective"


class ConversationRequest(Strict):
    consent_ref: Ref
    title: str = Field(default="New conversation", min_length=1, max_length=120)
