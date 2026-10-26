from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(Strict):
    subject: str = Field(max_length=100)
    predicate: str = Field(max_length=100)
    value: str = Field(max_length=200)
    evidence_refs: list[str] = Field(max_length=8)


class ProposedAction(Strict):
    kind: Literal["record_analysis", "lab_draft", "external_message"]
    content: str = Field(max_length=1500)
    rationale: str = Field(max_length=1000)


class RoleOutput(Strict):
    summary: str = Field(max_length=1500)
    claims: list[Claim] = Field(max_length=4)
    actions: list[ProposedAction] = Field(max_length=2)
    criticisms: list[str] = Field(max_length=6)
    uncertainties: list[str] = Field(max_length=6)
    recommendation: Literal["proceed", "investigate", "revise", "abstain"]
    confidence: float = Field(ge=0, le=1)


class CognitiveConfiguration(Strict):
    topics: list[str] = Field(
        default_factory=lambda: ["battery endurance", "coolant temperature"], max_length=12
    )
    origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:8000"], max_length=8)
    threshold: float = Field(default=0.45, ge=0.1, le=1)
    session_calls: int = Field(default=30, ge=0, le=200)
    session_tokens: int = Field(default=200000, ge=0, le=1000000)
    experiment_calls: int = Field(default=100, ge=0, le=500)
    experiment_tokens: int = Field(default=500000, ge=0, le=2000000)
    investigation_calls: int = Field(default=4, ge=1, le=6)
    investigation_tokens: int = Field(default=50000, ge=1000, le=100000)
    request_tokens: int = Field(default=18000, ge=512, le=30000)
    output_tokens: int = Field(default=1536, ge=256, le=4096)
    wall_seconds: int = Field(default=90, ge=1, le=180)
    tool_calls: int = Field(default=3, ge=0, le=6)
    depth: int = Field(default=1, ge=1, le=1)
    retries: int = Field(default=0, ge=0, le=0)
    concurrency: int = Field(default=1, ge=1, le=1)
    lab_writes: bool = False
    use_critic: bool = True
    preferred_action: Literal["record_analysis", "lab_draft"] = "record_analysis"


class AutonomyCommand(Strict):
    command: Literal["start", "pause", "stop", "new_session"]
    provider: Literal["mock", "meta"] = "mock"


class Approval(Strict):
    decision: Literal["approve", "reject", "cancel"]


class HistoryEntry(Strict):
    url: str = Field(max_length=2048)
    title: str = Field(max_length=200)
    content: str = Field(max_length=8000)
    visited_at: datetime | None = None


class ImportPreview(Strict):
    entries: list[HistoryEntry] = Field(min_length=1, max_length=30)


class ImportApproval(Strict):
    approved: bool


class LabCreate(Strict):
    scenario: Literal["relevant", "contradiction", "noise"]
    seed: int = Field(default=7, ge=0, le=100000)


class CognitiveEnvelope(Strict):
    schema_version: Literal[1] = 1
    message_id: str
    investigation_id: str
    sender: Literal["observer", "proposer", "critic", "investigator", "evaluator", "governor"]
    recipient: Literal["governor"] = "governor"
    message_type: Literal[
        "observation",
        "hypothesis",
        "proposal",
        "critique",
        "evidence",
        "decision",
        "result",
        "evaluation",
        "abstention",
    ]
    content: dict
    model_invocation_id: str | None = None
    timestamp: datetime


class ExperienceRecord(Strict):
    schema_version: Literal[1]
    experience_id: str
    agent_instance: str
    environment_id: str | None
    episode_id: str
    state_snapshot: dict
    candidate_actions: list[dict]
    chosen_action: dict | None
    behaviour_policy: str
    selection_probability: float | None = Field(ge=0, le=1)
    action_permissions: dict
    outcome_state: dict
    reward_components: dict
    reward_provenance: str
    terminated: bool
    truncated: bool
    timestamp: datetime
    relevant_event_ids: list[str]
    model_versions: dict
    embedding_version: dict
    evaluation: dict
    usage: dict
    elapsed_seconds: float = Field(ge=0)
    evaluation_split: str
    outcome_termination_note: str


TERMINAL = {"COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"}
TRANSITIONS = {
    "SCHEDULED": {"INVESTIGATING", "CANCELLED", "FAILED"},
    "INVESTIGATING": {"CRITIQUING", "EVALUATING", "FAILED", "CANCELLED"},
    "CRITIQUING": {"EVALUATING", "FAILED", "CANCELLED"},
    "EVALUATING": {"AWAITING_APPROVAL", "EXECUTING", "ABSTAINED", "FAILED", "CANCELLED"},
    "AWAITING_APPROVAL": {"EXECUTING", "ABSTAINED", "CANCELLED", "FAILED"},
    "EXECUTING": {"COMPLETED", "FAILED", "CANCELLED"},
}
