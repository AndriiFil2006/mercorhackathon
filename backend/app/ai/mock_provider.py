from app.ai.schemas import LegalGenerationInput, LegalGenerationResult, StructuredLegalAnswer

# Illustrations only, not verified authorities, expected answers, or real model failures.
ILLUSTRATIONS = {
    "contract": ("Assess formation and enforceability before identifying remedies.",
                 "A limitation clause may affect relief; its scope and enforceability require review."),
    "employment": ("Worker classification depends on the applicable legal test.",
                   "Assigned work and actual control may matter; the contract label alone does not resolve classification."),
    "landlord": ("Assess notice requirements and available housing remedies.",
                 "The remedy and required procedure depend on the defect, notice, and local rules."),
    "consumer": ("Assess the disclosure and cancellation terms.",
                 "Compare representations at purchase with actual restrictions and statutory requirements."),
    "intellectual": ("Assess protectable expression, ownership, and copying.",
                     "Distinguish protected expression from permitted use and possible defenses."),
}

class MockProvider:
    provider = "mock"
    model_name = "mock-legal-v2"

    def __init__(self, prompt_version: str = "legal-v1"):
        self.prompt_version = prompt_version

    def generate(self, question: LegalGenerationInput) -> LegalGenerationResult:
        rule, analysis = next(
            (value for key, value in ILLUSTRATIONS.items() if key in question.domain.lower()),
            ("Identify the governing rule.", "The stated facts need legal expert assessment."),
        )
        answer = StructuredLegalAnswer(
            short_answer="SIMULATED MOCK ANSWER — fictional demonstration, not a Gemini response or real model failure.",
            legal_rules=[rule],
            analysis=f"Illustrative analysis for {question.jurisdiction} as of {question.relevant_law_date}: {analysis}",
            exceptions_or_limitations=["This simulation is not a verified statement of applicable law."],
            conclusion="An expert must assess the law and scenario before reaching a substantive conclusion.",
            citations=[],
            uncertainties=["Authorities have not been researched or verified.", "Material facts may be missing."],
        )
        return LegalGenerationResult(
            provider=self.provider, model_name=self.model_name, prompt_version=self.prompt_version,
            structured_answer=answer,
            generation_metadata={"simulated": True, "citations_verified": False},
        )

