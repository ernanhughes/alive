from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from alive.cognitive_schema import CognitiveConfiguration


class Fact(BaseModel):
    key: str
    value: float


class Source(BaseModel):
    id: str
    authority: Literal["verified", "unverified"]
    window: str
    facts: list[Fact]
    annotation: str


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    split: Literal["calibration", "evaluation"]
    category: Literal["straightforward", "ambiguous", "contradictory", "adversarial"]
    family: str
    subject: str
    objective: str
    operation: str
    required_fields: list[str]
    sources: list[Source]
    expected: dict
    scoring_rule: str
    acceptable_abstention: str
    verification: str
    provenance: str
    action_risk: float = Field(ge=0, le=1)

    def payload(self):
        # Labels, split, task family, expected values and scorer instructions cannot reach a role.
        return {
            key: getattr(self, key)
            for key in ["subject", "objective", "operation", "required_fields", "action_risk"]
        } | {"sources": [source.model_dump() for source in self.sources]}


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    uncertainty: float = Field(ge=0, le=1)
    contradiction: float = Field(ge=0, le=1)
    evidence_gap: float = Field(ge=0, le=1)
    weak_evidence: float = Field(ge=0, le=1)
    action_risk: float = Field(ge=0, le=1)
    estimated_tokens: int = Field(ge=1)


class PolicyChoice(BaseModel):
    policy: str
    invoke: bool
    score: float
    threshold: float
    reason: str
    features: Features


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phase: Literal["calibration", "pilot", "full"]
    provider: Literal["mock", "meta"] = "meta"
    freeze_id: str
    max_calls: int = Field(default=16, ge=1, le=360)
    max_tokens: int = Field(default=100000, ge=1000, le=2000000)
    authorization_id: str | None = None


class FullAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    freeze_id: str
    confirmation: Literal["AUTHORIZE FROZEN 120 TASK META EVALUATION"]
    max_calls: int = Field(ge=240, le=360)
    max_tokens: int = Field(ge=1000, le=2000000)
    session_plan: Literal["TWO_60_TASK_SESSIONS"]


def validate_limits(config):
    return CognitiveConfiguration.model_validate(config)
