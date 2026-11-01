from typing import Literal

from pydantic import Field

from alive.analysis.contracts import Strict

Family = Literal["numeric", "parsing", "state", "authorization", "defaults", "errors"]

# Closed vocabulary of failure mechanisms. A lesson names the mechanisms it addresses and the
# ones it must not be applied to; the live intent call names the mechanisms a task could involve.
# Relevance is decided on this shared vocabulary, never on a model-reported confidence.
Mechanism = Literal[
    "numeric.signed_values",
    "numeric.empty_or_zero",
    "numeric.rounding",
    "numeric.boundary",
    "numeric.counting",
    "parsing.delimiter_position",
    "parsing.whitespace_case",
    "parsing.empty_fields",
    "parsing.type_coercion",
    "state.transition_guard",
    "state.ordering",
    "state.repeat_application",
    "state.input_mutation",
    "authz.default_deny",
    "authz.substring_match",
    "authz.precedence",
    "authz.scope_boundary",
    "defaults.falsy_vs_missing",
    "defaults.merge_depth",
    "defaults.override_precedence",
    "errors.swallowed",
    "errors.wrong_type",
    "errors.partial_state",
]
FAMILY_OF_PREFIX = {
    "numeric": "numeric",
    "parsing": "parsing",
    "state": "state",
    "authz": "authorization",
    "defaults": "defaults",
    "errors": "errors",
}


def family_of(mechanism):
    return FAMILY_OF_PREFIX[mechanism.split(".")[0]]


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
    # AI-FIRST-04. Defaults keep AI-FIRST-03 proposals readable; an unscoped lesson is simply
    # not eligible for relevance-based selection.
    mechanisms: list[Mechanism] = Field(default_factory=list, max_length=3)
    excluded_mechanisms: list[Mechanism] = Field(default_factory=list, max_length=3)
