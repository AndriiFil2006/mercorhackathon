"""Provider factory. Gemini never falls back to mock on failure."""
from typing import Protocol
from openai import OpenAI
from pydantic import ValidationError
from app.ai.errors import GenerationError
from app.ai.mock_provider import MockProvider
from app.ai.prompts import SYSTEM_PROMPT, INPUT_BOUNDARY, build_prompt
from app.ai.schemas import LegalGenerationInput, LegalGenerationResult, StructuredLegalAnswer
from app.core.config import Settings

class AIProvider(Protocol):
    provider: str
    model_name: str
    def generate(self, question: LegalGenerationInput) -> LegalGenerationResult: ...

class OpenAIProvider:
    provider = "openai"

    def __init__(self, settings: Settings):
        self.model_name = settings.openai_model
        self.prompt_version = settings.ai_prompt_version
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=45, max_retries=1)

    def generate(self, question: LegalGenerationInput) -> LegalGenerationResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + INPUT_BOUNDARY},
                    {"role": "user", "content": build_prompt(question)},
                ],
                response_format={"type": "json_schema", "json_schema": {
                    "name": "legal_answer", "strict": True,
                    "schema": StructuredLegalAnswer.model_json_schema(),
                }},
            )
            text = response.choices[0].message.content
            if not text:
                raise GenerationError("empty_response", "OpenAI returned no answer.")
            answer = StructuredLegalAnswer.model_validate_json(text)
            return LegalGenerationResult(
                provider=self.provider, model_name=self.model_name, prompt_version=self.prompt_version,
                structured_answer=answer,
                generation_metadata={"simulated": False, "citations_verified": False, "model_used": response.model},
            )
        except ValidationError:
            raise GenerationError("invalid_output", "OpenAI returned invalid structured output.") from None
        finally:
            self.client.close()

def get_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "mock":
        return MockProvider(settings.ai_prompt_version)
    if settings.ai_provider == "gemini":
        from app.ai.gemini_provider import GeminiProvider
        return GeminiProvider(settings)
    if settings.ai_provider == "openai":
        # Preserve the original optional OpenAI/no-key mock behavior.
        if not settings.openai_api_key:
            return MockProvider(settings.ai_prompt_version)
        return OpenAIProvider(settings)
    raise GenerationError("configuration", "AI_PROVIDER must be mock, gemini, or openai.", 503)

