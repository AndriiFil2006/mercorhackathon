from datetime import datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from app.schemas.questions import Citation, ORMResponse
class Verdict(str, Enum):
    correct = "correct"
    partially_correct = "partially_correct"
    incorrect = "incorrect"
    uncertain = "uncertain"
class ErrorCategory(str, Enum):
    hallucinated_authority = "hallucinated_authority"
    outdated_law = "outdated_law"
    wrong_jurisdiction = "wrong_jurisdiction"
    incorrect_interpretation = "incorrect_interpretation"
    missing_authority = "missing_authority"
    incomplete_answer = "incomplete_answer"
    incorrect_conclusion = "incorrect_conclusion"
    unsupported_claim = "unsupported_claim"
    other = "other"
class EvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question_id: UUID
    generation_id: UUID
    reviewer_id: str | None = Field(default=None, max_length=200)
    verdict: Verdict
    error_categories: list[ErrorCategory] = Field(default_factory=list)
    expert_explanation: str = Field(default="", max_length=50000)
    corrected_answer: str | None = Field(default=None, max_length=50000)
    supporting_sources: list[Citation] | None = None
    confidence: int | None = Field(default=None, ge=1, le=5, strict=True)
    @model_validator(mode="after")
    def require_correction(self):
        if self.verdict in (Verdict.incorrect, Verdict.partially_correct):
            if not self.expert_explanation or not self.corrected_answer:
                raise ValueError("Incorrect and partially correct verdicts require explanation and corrected_answer")
        return self
class EvaluationPublic(EvaluationCreate, ORMResponse):
    id: UUID
    created_at: datetime
    @computed_field
    @property
    def verification_status(self) -> str:
        if self.verdict == Verdict.correct:
            return "expert_approved"
        return "expert_abstained" if self.verdict == Verdict.uncertain else "expert_reviewed"

