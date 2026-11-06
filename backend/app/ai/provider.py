from typing import Protocol
from openai import OpenAI
from app.core.config import Settings
from app.schemas.questions import PublicQuestionInput
from app.ai.prompts import build_prompt
class AIProvider(Protocol):
    model_name: str
    def generate(self, question: PublicQuestionInput) -> str: ...
class MockProvider:
    model_name = "mock-legal-v1"
    def generate(self, question: PublicQuestionInput) -> str:
        return (
            f"SIMULATED MOCK ANSWER — fictional demonstration, not a real model failure. "
            f"For this {question.domain} scenario in {question.jurisdiction} as of "
            f"{question.relevant_law_date}, the outcome depends on applicable rules, terms, and facts. "
            "An expert should assess remedies and exceptions. No legal authorities have been verified. "
            "Human legal review is required."
        )
class OpenAIProvider:
    def __init__(self, settings: Settings):
        self.model_name = settings.openai_model
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=45, max_retries=1)
    def generate(self, question: PublicQuestionInput) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name, messages=[{"role": "user", "content": build_prompt(question)}])
        answer = response.choices[0].message.content
        if not answer or not answer.strip():
            raise ValueError("Empty provider response")
        return answer
def get_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "mock" or not settings.openai_api_key:
        return MockProvider()
    return OpenAIProvider(settings)

