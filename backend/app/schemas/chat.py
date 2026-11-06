from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


class Message(StrictInput):
    id: str | None = None
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=50000)


class AnswerRequest(StrictInput):
    question: str = Field(min_length=1, max_length=30000)
    jurisdiction: str = Field(min_length=1, max_length=250)
    law_date: date = Field(alias="lawDate")
    messages: list[Message] = Field(default_factory=list, max_length=200)
    external_consent: bool = Field(default=False, alias="externalConsent")


class ReviewRequest(StrictInput):
    reviewer: Literal["authority", "jurisdiction", "reasoning"]
    generation_id: UUID | None = Field(default=None, alias="generationId")
    question: str = Field(min_length=1, max_length=30000)
    answer: str = Field(min_length=1, max_length=50000)
    jurisdiction: str = Field(min_length=1, max_length=250)
    law_date: date = Field(alias="lawDate")
    external_consent: bool = Field(default=False, alias="externalConsent")
    force: bool = False


class Source(StrictInput):
    id: str
    title: str
    url: str
    text: str
    retrieved_at: str
    evidence_type: Literal["extracted_page", "search_excerpt", "mock"]
    truncated: bool = False
    published_date: str | None = None


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    queries: list[str] = Field(min_length=1, max_length=2)
    claims_to_check: list[str] = Field(min_length=1, max_length=8)


class Dimension(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    score: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=6000)


class Criteria(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    authority: Dimension
    jurisdiction: Dimension
    interpretation: Dimension
    completeness: Dimension
    clarity: Dimension


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str
    quote: str = Field(min_length=1, max_length=1200)


class ClaimCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim: str = Field(min_length=1)
    verdict: Literal["supported", "contradicted", "incomplete", "unresolved"]
    explanation: str = Field(min_length=1)
    evidence: list[Evidence] = Field(max_length=5)


class ResearchJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    criteria: Criteria
    research_summary: str = Field(min_length=1)
    jurisdiction_analysis: str = Field(min_length=1)
    date_analysis: str = Field(min_length=1)
    claim_checks: list[ClaimCheck] = Field(min_length=1, max_length=12)
    limitations: list[str] = Field(min_length=1)
    suggested_correction: str = Field(min_length=1)
    conclusion: str = Field(min_length=1)
    abstain: bool
    abstention_reason: str

    @model_validator(mode="after")
    def meaningful(self):
        if self.abstain and not self.abstention_reason.strip():
            raise ValueError("Explain abstention")
        if any(not c["reason"].strip() for c in self.criteria.model_dump().values()):
            raise ValueError("Blank criterion reason")
        return self


class ScorerChatRequest(StrictInput):
    question: str = Field(min_length=1, max_length=30000)
    answer: str = Field(min_length=1, max_length=50000)
    jurisdiction: str = Field(min_length=1, max_length=250)
    law_date: date = Field(alias="lawDate")
    reviews: list[dict] = Field(min_length=1, max_length=3)
    history: list[Message] = Field(default_factory=list, max_length=200)
    prompt: str = Field(min_length=1, max_length=15000)
    external_consent: bool = Field(default=False, alias="externalConsent")


class HandoffContext(StrictInput):
    id: str
    title: str
    jurisdiction: str
    law_date: str = Field(alias="lawDate")
    messages: list[Message] = Field(max_length=200)
    # Full accepted session evaluations, including original answers, all reports,
    # sources, criterion reasoning, expert feedback and scorer follow-up history.
    evaluations: list[dict] = Field(max_length=200)
    selected_evaluation_id: str = Field(alias="selectedEvaluationId")


class HandoffRequest(StrictInput):
    consent_processing: bool = Field(default=False, alias="consentProcessing")
    consent_share_context: bool = Field(default=False, alias="consentShareContext")
    context: HandoffContext | None = None


class LawyerRequest(StrictInput):
    handoff_token: str = Field(alias="handoffToken", min_length=30, max_length=200)
    message: str = Field(min_length=1, max_length=15000)


class TokenRequest(StrictInput):
    handoff_token: str = Field(alias="handoffToken", min_length=30, max_length=200)
