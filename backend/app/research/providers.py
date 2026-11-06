"""Server-only Groq JSON client. No fallback, auto billing or hidden repair calls."""

import json
import re
import threading
import time
import httpx
from app.ai.errors import GenerationError
from app.core.config import Settings
from app.schemas.chat import Plan, ResearchJudgment

# Serialize remote model calls within this local process to avoid free-tier bursts.
GROQ_LOCK = threading.BoundedSemaphore(1)
LAST_CALL: dict[str, float] = {}


def portable_schema(schema: dict) -> dict:
    """Conservative schema subset: inline refs, retain shape/enums, validate bounds locally."""
    definitions = schema.get("$defs", {})

    def walk(node):
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(definitions[node["$ref"].split("/")[-1]])
        result = {
            key: value
            for key, value in node.items()
            if key
            in (
                "type",
                "enum",
                "properties",
                "items",
                "required",
                "additionalProperties",
            )
        }
        if "properties" in result:
            result["properties"] = {
                key: walk(value) for key, value in result["properties"].items()
            }
            result["required"] = list(result["properties"])
            result["additionalProperties"] = False
        if "items" in result:
            result["items"] = walk(result["items"])
        return result

    return walk(schema)


def decode_model_content(content):
    if isinstance(content, dict):
        return content
    if not isinstance(content, str) or not content.strip():
        raise GenerationError(
            "empty_response", "Groq returned no text content for this reviewer.", 502
        )
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
    except ValueError:
        raise GenerationError(
            "invalid_json",
            "The model returned text that is not valid JSON. No score was accepted.",
            502,
        ) from None
    if not isinstance(result, dict):
        raise GenerationError(
            "invalid_json",
            "The model returned a JSON value instead of an assessment object.",
            502,
        )
    return result


def groq_json(settings: Settings, model: str, system: str, data: dict) -> dict:
    if not settings.groq_api_key.strip():
        raise GenerationError(
            "configuration",
            "Set GROQ_API_KEY in backend/.env and restart the backend.",
            503,
        )
    # Send the exact required schema to the provider, not only a JSON-mode hint.
    payload = dict(data)
    schema = portable_schema(
        payload.pop("output_schema", None) or Plan.model_json_schema()
    )
    planning = "criteria" not in schema.get("properties", {})
    body = {
        "model": model,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": (
                    "legal_research_plan" if planning else "legal_research_assessment"
                ),
                "strict": True,
                "schema": schema,
            },
        },
        "max_completion_tokens": min(
            settings.reviewer_max_output_tokens, 1200 if planning else 3000
        ),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    }
    if model.startswith("openai/gpt-oss-"):
        body["reasoning_effort"] = "low"
    elif model.startswith("qwen/"):
        body["reasoning_effort"] = "none"
    try:
        with GROQ_LOCK, httpx.Client(
            timeout=settings.reviewer_timeout_seconds
        ) as client:
            delay = settings.groq_min_interval_seconds - (
                time.monotonic() - LAST_CALL.get(model, -1e12)
            )
            if delay > 0:
                time.sleep(delay)
            LAST_CALL[model] = time.monotonic()
            for attempt in range(2):
                response = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json=body,
                )
                if response.status_code != 429 or attempt:
                    break
                try:
                    message = (
                        response.json().get("error", {}).get("message", "").lower()
                    )
                except (ValueError, AttributeError):
                    message = ""
                if any(
                    word in message
                    for word in (
                        "request too large",
                        "tokens per day",
                        "requests per day",
                    )
                ):
                    break
                try:
                    pause = max(1, float(response.headers.get("retry-after", "60")))
                except (ValueError, TypeError):
                    pause = 60
                if pause > 90:
                    break
                response.close()
                time.sleep(pause)
                LAST_CALL[model] = time.monotonic()

        if response.status_code == 429:
            try:
                text = response.json().get("error", {}).get("message", "").lower()
            except (ValueError, AttributeError):
                text = ""
            if (
                "request too large" in text
                or "requested tokens" in text
                and "limit" in text
            ):
                raise GenerationError(
                    "request_too_large",
                    "This complete answer plus evidence exceeds the model's free token allowance. Use a shorter main-AI answer in a new inquiry; repeated retries cannot fix request size.",
                    429,
                )
            if "tokens per day" in text or "requests per day" in text:
                raise GenerationError(
                    "daily_quota",
                    "Groq daily free quota is exhausted for this model. Wait for the quota reset; no assessment was fabricated.",
                    429,
                )
            wait = response.headers.get("retry-after", "60")
            try:
                seconds = max(1, int(float(wait)))
            except (ValueError, TypeError):
                seconds = 60
            raise GenerationError(
                "rate_limited",
                f"Groq temporary rate limit. Wait at least {seconds} seconds before retrying this reviewer; no score was substituted.",
                429,
            )
        if response.status_code in (401, 403):
            raise GenerationError(
                "authentication",
                "Groq rejected the key or model permission. Check GROQ_API_KEY and your free account's model access.",
                503,
            )
        # Some account/model deployments reject schema mode. Retry format only,
        # using the SAME model and original input, with local validation unchanged.
        if response.status_code == 400:
            try:
                rejected = response.json().get("error", {})
            except ValueError:
                rejected = {}
            detail = str(rejected.get("message", "")).lower()
            if (
                rejected.get("param") == "response_format"
                or "schema" in detail
                or "response_format" in detail
            ):
                body["response_format"] = {"type": "json_object"}
                body["messages"][0]["content"] += (
                    "\nReturn one JSON object matching this exact schema; all fields required: "
                    + json.dumps(schema)
                )
                with GROQ_LOCK, httpx.Client(
                    timeout=settings.reviewer_timeout_seconds
                ) as client:
                    response = client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                        json=body,
                    )
                if response.status_code == 429:
                    raise GenerationError(
                        "rate_limited",
                        "Groq rate limit during same-model format retry. Wait at least 60 seconds before retrying this reviewer.",
                        429,
                    )
        if response.status_code in (400, 404):
            try:
                info = response.json().get("error", {})
            except (ValueError, AttributeError):
                info = {}
            # Only return constrained error identifiers, never failed_generation/raw text.
            code = re.sub(
                r"[^a-zA-Z0-9_.-]", "", str(info.get("code") or "unspecified")
            )[:60]
            param = re.sub(
                r"[^a-zA-Z0-9_.-]", "", str(info.get("param") or "unspecified")
            )[:60]
            detail = str(info.get("message") or "").lower()
            if response.status_code == 404:
                reason = (
                    "Configured model was not found or is unavailable to this account."
                )
            elif "schema" in detail or "response_format" in detail:
                reason = "Groq rejected the structured-output schema/request."
            elif "reasoning" in detail:
                reason = "Groq rejected the reasoning configuration."
            elif code == "json_validate_failed":
                reason = "Groq could not produce the required structured output."
            else:
                reason = (
                    "Groq rejected the request; its error identifier is included below."
                )
            raise GenerationError(
                "groq_request_rejected",
                f"{reason} HTTP {response.status_code}; code={code}; parameter={param}. No model substitution was made.",
                502,
            )
        if response.status_code >= 500:
            raise GenerationError(
                "provider_unavailable",
                f"Groq server/gateway failure: HTTP {response.status_code}. This is not a JSON-input error.",
                503,
            )
        if not response.is_success:
            raise GenerationError(
                "provider_http_error",
                f"Groq rejected the request with HTTP {response.status_code}.",
                502,
            )
        try:
            envelope = response.json()
        except ValueError:
            raise GenerationError(
                "provider_non_json",
                f"Groq/gateway returned a non-JSON HTTP response (HTTP {response.status_code}).",
                502,
            ) from None
        choices = envelope.get("choices") if isinstance(envelope, dict) else None
        if not isinstance(choices, list) or not choices:
            raise GenerationError(
                "provider_envelope", "Groq response had no completion choices.", 502
            )
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise GenerationError(
                "output_limit",
                "Reviewer response reached its output-token limit before completing. No partial score was accepted.",
                502,
            )
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise GenerationError(
                "model_refusal", "This model declined to assess the request.", 502
            )
        return decode_model_content(message.get("parsed") or message.get("content"))
    except GenerationError:
        raise
    except httpx.TimeoutException:
        raise GenerationError(
            "timeout", "Groq reviewer timed out; retry later.", 504
        ) from None
    except httpx.HTTPError:
        raise GenerationError(
            "provider_network",
            "Network/connection failure contacting Groq. Check connectivity; this is not invalid JSON input.",
            503,
        ) from None
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        raise GenerationError(
            "provider_envelope",
            "Unexpected Groq response structure. No model score was accepted.",
            502,
        ) from None
