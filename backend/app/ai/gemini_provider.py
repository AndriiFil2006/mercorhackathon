"""Official Gemini SDK adapter: one structured call, bounded transient retries."""
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

import httpx
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.errors import GenerationError
from app.ai.prompts import SYSTEM_PROMPT, INPUT_BOUNDARY, build_prompt
from app.ai.schemas import LegalGenerationInput, LegalGenerationResult, StructuredLegalAnswer
from app.core.config import Settings


def retry_delay(error: errors.APIError, attempt: int) -> float:
    """Honor Retry-After (seconds/date) or RetryInfo without shortening it."""
    headers = getattr(error.response, "headers", {}) or {}
    value = headers.get("retry-after")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (ValueError, TypeError):
                pass
    details = error.details if isinstance(error.details, dict) else {}
    body = details.get("error", details)
    for item in body.get("details", []) if isinstance(body, dict) else []:
        if isinstance(item, dict) and item.get("@type", "").endswith("RetryInfo"):
            try:
                return max(0.0, float(item["retryDelay"].removesuffix("s")))
            except (KeyError, ValueError, TypeError, AttributeError):
                pass
    return min(2 ** attempt, 8)


def api_error(error: errors.APIError) -> GenerationError:
    if error.code in (401, 403):
        return GenerationError("authentication", "Gemini authentication failed. Check GEMINI_API_KEY and API access.", 503)
    if error.code == 404:
        if any(term in json.dumps(error.details, default=str).lower() for term in ("no longer", "retired", "decommissioned", "shut down")):
            return GenerationError("model_unavailable", "Configured GEMINI_MODEL has been retired. Set GEMINI_MODEL to a supported model and restart the backend; no fallback was used.", 503)
        return GenerationError("model_unavailable", "Configured GEMINI_MODEL is unavailable. Check the model ID and access; no fallback was used.", 503)
    if error.code == 400:
        # Classify known reasons in memory; never expose Google's raw message/details.
        detail_text = json.dumps(error.details, default=str).lower()
        if any(reason in detail_text for reason in (
            "api_key_invalid", "api_key_expired", "api key not valid", "api key expired", "reported as leaked",
        )):
            return GenerationError("authentication", "Gemini rejected the API key. Replace GEMINI_API_KEY with a valid active key and restart the backend.", 503)
        if any(field in detail_text for field in ("response_schema", "responseschema", "response_json_schema", "responsejsonschema")):
            return GenerationError("invalid_request", "Gemini rejected the structured-output schema. Check the backend SDK/schema configuration and configured model's JSON Schema support.", 503)
        return GenerationError("invalid_request", "Gemini rejected the request. Check GEMINI_API_KEY, GEMINI_MODEL and structured-output support.", 503)
    if error.code == 429:
        return GenerationError("rate_limited", "Gemini quota or rate limit reached. Wait before retrying; check your project limits.", 429)
    if error.code in (408, 504):
        return GenerationError("timeout", "Gemini request timed out. Retry later or adjust GEMINI_TIMEOUT_SECONDS.", 504)
    return GenerationError("provider_unavailable", "Gemini is unavailable. Retry later.", 503)


class GeminiProvider:
    provider = "gemini"

    def __init__(self, settings: Settings, client=None, sleep: Callable[[float], None] = time.sleep):
        if not settings.gemini_api_key.strip():
            raise GenerationError("configuration", "Set GEMINI_API_KEY before using AI_PROVIDER=gemini.", 503)
        self.settings = settings
        self.model_name = settings.gemini_model
        self.prompt_version = settings.ai_prompt_version
        self.sleep = sleep
        self.client = client or genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.gemini_timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(self, question: LegalGenerationInput) -> LegalGenerationResult:
        modern_model = self.model_name.removeprefix("models/").startswith("gemini-3")
        try:
            for attempt in range(self.settings.gemini_max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=build_prompt(question),
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT + "\n\n" + INPUT_BOUNDARY,
                            response_mime_type="application/json",
                            # Use JSON Schema directly. The legacy response_schema
                            # converter can emit invalid snake_case schema fields.
                            response_json_schema=StructuredLegalAnswer.model_json_schema(),
                            # Gemini 3 models use thinking levels; newer releases
                            # reject deprecated sampling parameters.
                            temperature=None if modern_model else 0.2,
                            max_output_tokens=self.settings.gemini_max_output_tokens,
                            # For the default 2.5 Flash, leave the output budget for the answer.
                            thinking_config=(
                                types.ThinkingConfig(thinking_level="LOW") if modern_model else
                                types.ThinkingConfig(thinking_budget=0)
                                if self.model_name == "gemini-2.5-flash" else None
                            ),
                        ),
                    )
                    return self._parse(response, attempt + 1)
                except errors.APIError as error:
                    failure = api_error(error)
                    transient = error.code in (408, 429, 500, 502, 503, 504)
                    if not transient or attempt >= self.settings.gemini_max_retries:
                        raise failure from None
                    delay = retry_delay(error, attempt)
                    # Do not sleep excessively or retry earlier than Google's requested delay.
                    if delay > 30:
                        raise failure from None
                    self.sleep(delay)
                except (httpx.TimeoutException, TimeoutError):
                    if attempt >= self.settings.gemini_max_retries:
                        raise GenerationError("timeout", "Gemini request timed out. Retry later.", 504) from None
                    self.sleep(min(2 ** attempt, 8))
                except httpx.TransportError:
                    if attempt >= self.settings.gemini_max_retries:
                        raise GenerationError("provider_unavailable", "Could not reach Gemini. Retry later.", 503) from None
                    self.sleep(min(2 ** attempt, 8))
                except json.JSONDecodeError:
                    raise GenerationError("invalid_json", "Gemini returned malformed JSON; no repair call was made.") from None
                except ValidationError:
                    raise GenerationError("invalid_output", "Gemini output did not match the legal answer schema.") from None
        finally:
            self.client.close()

    def _parse(self, response: types.GenerateContentResponse, attempts: int) -> LegalGenerationResult:
        feedback = response.prompt_feedback
        if feedback and feedback.block_reason and str(feedback.block_reason) != "BLOCK_REASON_UNSPECIFIED":
            raise GenerationError("blocked_response", "Gemini blocked this request; review the scenario.")
        candidates = response.candidates or []
        if candidates:
            reason = candidates[0].finish_reason
            if reason and reason != types.FinishReason.STOP:
                if reason == types.FinishReason.MAX_TOKENS:
                    raise GenerationError("output_truncated", "Gemini exceeded the output budget. Adjust GEMINI_MAX_OUTPUT_TOKENS.")
                raise GenerationError("blocked_response", "Gemini did not provide a complete permitted response.")
        text = response.text
        if not text or not text.strip():
            raise GenerationError("empty_response", "Gemini returned an empty response.")
        try:
            json.loads(text)
        except (ValueError, TypeError):
            raise GenerationError("invalid_json", "Gemini returned malformed JSON; no repair call was made.") from None
        try:
            answer = StructuredLegalAnswer.model_validate_json(text)
        except ValidationError:
            raise GenerationError("invalid_output", "Gemini output did not match the legal answer schema.") from None
        usage = response.usage_metadata
        token_usage = {
            key: getattr(usage, key, None) for key in (
                "prompt_token_count", "candidates_token_count", "total_token_count", "thoughts_token_count"
            ) if usage is not None and getattr(usage, key, None) is not None
        }
        return LegalGenerationResult(
            provider=self.provider, model_name=self.model_name, prompt_version=self.prompt_version,
            structured_answer=answer,
            generation_metadata={
                "simulated": False, "citations_verified": False,
                "model_used": response.model_version, "response_id": response.response_id,
                "token_usage": token_usage, "attempts": attempts,
                "temperature": None if self.model_name.removeprefix("models/").startswith("gemini-3") else 0.2,
            },
        )
