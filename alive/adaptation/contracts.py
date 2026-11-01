from typing import Literal

from pydantic import Field

from alive.analysis.contracts import Strict

Family = Literal["numeric", "parsing", "state", "authorization", "defaults", "errors"]


class Prediction(Strict):
    case_id: str = Field(min_length=1, max_length=40)
    observed: str = Field(
        max_length=400,
        description="JSON value produced by the supplied implementation, or ERROR:ExceptionName",
    )
    required: str = Field(
        max_length=400,
        description="JSON value required by the stated contract, or ERROR:ExceptionName",
    )


class LessonProposal(Strict):
    family: Family
    strategy: str = Field(min_length=10, max_length=600)
    applies_when: str = Field(min_length=5, max_length=300)
    not_when: str = Field(min_length=5, max_length=300)
    supporting_experience_ids: list[str] = Field(min_length=1, max_length=4)
    uncertainty: str = Field(min_length=5, max_length=300)
