"""Gemini conversation wrapper for scorer explanations and the AI lawyer placeholder."""

import json
import time
import httpx
from google import genai
from google.genai import types, errors
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from app.ai.errors import GenerationError
from app.ai.gemini_provider import api_error, retry_delay
from app.core.config import Settings


class ChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    answer: str = Field(min_length=1)


def context_reply(settings: Settings, system: str, data: dict) -> dict:
    # Never silently drop earlier conversation/context to make a model call fit.
    payload = json.dumps(data, ensure_ascii=False)
    if len(payload) > settings.chat_context_max_chars:
        raise GenerationError(
            "context_too_large",
            "The complete conversation exceeds the configured context budget. No history was silently truncated; start a new conversation or adjust the server budget.",
            413,
        )
    if settings.ai_provider == "mock":
        return {
            "answer": "MOCK AI assistant response — offline fixture only. I received the supplied context; no real model or new research was used.",
            "mode": "mock",
            "model": "mock-context-v1",
        }
    if settings.ai_provider != "gemini":
        raise GenerationError(
            "configuration",
            "Connected chat wrappers currently require AI_PROVIDER=gemini or mock.",
            503,
        )
    if not settings.gemini_api_key.strip():
        raise GenerationError(
            "configuration", "Set GEMINI_API_KEY in backend/.env.", 503
        )
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=int(settings.gemini_timeout_seconds * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    modern = settings.gemini_model.removeprefix("models/").startswith("gemini-3")
    try:
        for attempt in range(settings.gemini_max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=payload,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_json_schema=ChatReply.model_json_schema(),
                        max_output_tokens=settings.gemini_max_output_tokens,
                        temperature=None if modern else 0.2,
                        thinking_config=(
                            types.ThinkingConfig(thinking_level="LOW")
                            if modern
                            else None
                        ),
                    ),
                )
                text = response.text
                if not text:
                    raise GenerationError(
                        "empty_response", "Gemini returned an empty chat response."
                    )
                result = ChatReply.model_validate_json(text)
                if not result.answer.strip():
                    raise GenerationError(
                        "empty_response", "Gemini returned a blank chat response."
                    )
                return {
                    "answer": result.answer,
                    "mode": "live",
                    "model": settings.gemini_model,
                }
            except errors.APIError as error:
                failure = api_error(error)
                if (
                    error.code not in (408, 429, 500, 502, 503, 504)
                    or attempt >= settings.gemini_max_retries
                ):
                    raise failure from None
                delay = retry_delay(error, attempt)
                if delay > 30:
                    raise failure from None
                time.sleep(delay)
            except (httpx.TimeoutException, TimeoutError):
                if attempt >= settings.gemini_max_retries:
                    raise GenerationError(
                        "timeout", "Gemini chat timed out.", 504
                    ) from None
            except ValidationError:
                raise GenerationError(
                    "invalid_output", "Gemini returned invalid chat output."
                ) from None
        raise GenerationError("provider_unavailable", "Gemini chat unavailable.", 503)
    finally:
        client.close()
