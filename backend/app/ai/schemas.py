"""Narrow provider input and validated legal output."""
from datetime import date
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class LegalGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    question_id: UUID
    question_text: str
    domain: str
    jurisdiction: str
    relevant_law_date: date
    scenario_facts: str | None = None

class ModelCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    authority_name: str = Field(min_length=1)
    citation: str = Field(min_length=1)
    relevance: str = Field(min_length=1)

class StructuredLegalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    short_answer: str = Field(min_length=1)
    legal_rules: list[str]
    analysis: str = Field(min_length=1)
    exceptions_or_limitations: list[str]
    conclusion: str = Field(min_length=1)
    citations: list[ModelCitation]
    uncertainties: list[str]

    @model_validator(mode="after")
    def reject_blank_content(self):
        strings = [self.short_answer, self.analysis, self.conclusion,
                   *self.legal_rules, *self.exceptions_or_limitations, *self.uncertainties]
        strings += [value for citation in self.citations for value in citation.model_dump().values()]
        if any(not value.strip() for value in strings):
            raise ValueError("Legal answer fields must not contain blank strings")
        return self

class LegalGenerationResult(BaseModel):
    provider: str
    model_name: str
    prompt_version: str
    structured_answer: StructuredLegalAnswer
    generation_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def readable_answer(self) -> str:
        answer = self.structured_answer
        def bullets(items: list[str]) -> str:
            return "\n".join(f"- {item}" for item in items) if items else "None provided."
        citations = [f"{item.authority_name} — {item.citation}: {item.relevance}" for item in answer.citations]
        return "\n\n".join([
            "Short answer\n" + answer.short_answer,
            "Applicable law\n" + bullets(answer.legal_rules),
            "Legal analysis\n" + answer.analysis,
            "Exceptions and limitations\n" + bullets(answer.exceptions_or_limitations),
            "Conclusion\n" + answer.conclusion,
            "Cited authorities (model-generated, unverified)\n" + bullets(citations),
            "Uncertainties\n" + bullets(answer.uncertainties),
            "Review status: AI output; requires human expert review.",
        ])

