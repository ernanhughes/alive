from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from alive.models import now


class EventEnvelope(BaseModel):
    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    instance_id: UUID
    event_type: str = Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_.]+$")
    source: str = Field(min_length=1, max_length=100)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    timestamp: datetime = Field(default_factory=now)
    payload: dict = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("timestamp requires a timezone")
        return value


class Observation(BaseModel):
    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    event_type: Literal["browser.page_opened", "browser.dom_changed"]
    source: Literal["extension", "user"] = "extension"
    payload: dict


class GoalInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=8000)
    priority: int = Field(default=50, ge=0, le=100)


class GoalTransition(BaseModel):
    status: Literal["accepted", "active", "completed", "cancelled"]


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: Literal["text", "vector"] = "text"


class RunInput(BaseModel):
    runner: Literal["mock", "pi"] = "mock"
    objective: str = Field(min_length=1, max_length=16000)


class Navigation(BaseModel):
    url: str = Field(max_length=2048)


class BrowserAction(BaseModel):
    operation: Literal["inspect", "click", "fill", "screenshot"]
    selector: str = Field(default="body", max_length=300)
    value: str = Field(default="", max_length=2000)


class PersistedEvent(EventEnvelope):
    sequence_number: int


class MemoryOutput(BaseModel):
    id: str
    instance_id: str
    content: str
    memory_type: str
    source_event_id: str | None
    importance: float
    confidence: float
    metadata: dict
    created_at: datetime
    updated_at: datetime


class GoalOutput(BaseModel):
    id: str
    instance_id: str
    title: str
    description: str
    origin: str
    priority: int
    status: str
    parent_goal_id: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class RunOutput(BaseModel):
    id: str
    instance_id: str
    runner: str
    model_provider: str
    model_id: str
    objective: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    result: str | None
    error: str | None
    usage: dict
