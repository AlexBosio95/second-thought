from enum import StrEnum
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
NextAction = Literal["execute", "clarify", "retrieve_more", "human", "block"]

class Decision(StrEnum):
    EXECUTE = "EXECUTE"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"

class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any]

class Choice(BaseModel):
    choice: NextAction
    probabilities: dict[NextAction, Probability]

    @model_validator(mode="after")
    def valid_distribution(self) -> "Choice":
        if set(self.probabilities) != {"execute", "clarify", "retrieve_more", "human", "block"}:
            raise ValueError("Incomplete next_action distribution")
        if abs(sum(self.probabilities.values()) - 1) > .02:
            raise ValueError("Invalid probability sum")
        if self.probabilities[self.choice] < max(self.probabilities.values()):
            raise ValueError("Choice disagrees with distribution")
        return self

class Signals(BaseModel):
    intent_clear: Probability
    evidence_sufficient: Probability
    action_supported: Probability
    safe_to_execute: Probability
    human_review_required: Probability
    next_action: Choice

class PolicyResult(BaseModel):
    decision: Decision
    rule: str
    reason: str

class EvaluationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, pattern=r"\S")
