from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=500)
    citation: str | None = Field(default=None, max_length=1000)
    url: str | None = Field(default=None, max_length=2000)
    jurisdiction: str | None = Field(default=None, max_length=250)
class PublicQuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=250)
    question_text: str = Field(min_length=1, max_length=50000)
    domain: str = Field(min_length=1, max_length=100)
    jurisdiction: str = Field(min_length=1, max_length=250)
    relevant_law_date: date
    scenario_facts: str | None = Field(default=None, max_length=50000)
    difficulty: Difficulty
class QuestionCreate(PublicQuestionInput):
    reference_answer: str | None = Field(default=None, max_length=50000)
    reference_sources: list[Citation] | None = None
class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    @field_validator("created_at", "updated_at", "completed_at", "independent_answer_received_at", mode="after", check_fields=False)
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
class QuestionPublic(PublicQuestionInput, ORMResponse):
    id: UUID
    created_at: datetime
    updated_at: datetime

