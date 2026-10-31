from typing import Literal

from pydantic import Field

from alive.bespoke.contracts import Hash, Objective, Ref
from alive.capabilities.manifest import Strict


class ReviewRequest(Strict):
    profile: Literal["approved-repository-inspection", "approved-repository-analysis"] = (
        "approved-repository-inspection"
    )
    goal_ref: Ref
    approval_ref: Ref
    recipe_sha256: Hash
    objective: Objective
    paths: list[str] = Field(min_length=1, max_length=20)
    ttl_seconds: int = Field(default=300, ge=60, le=600)
    idempotency_key: str = Field(min_length=1, max_length=100)


class Confirmation(Strict):
    review_sha256: Hash
