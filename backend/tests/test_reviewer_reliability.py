import json
import httpx
import pytest
from app.core.config import Settings
from app.ai.errors import GenerationError
from app.schemas.chat import ResearchJudgment
from app.research import providers


def setup_transport(monkeypatch, statuses):
    original = httpx.Client
    requests = []
    sleeps = []

    def handle(request):
        requests.append(json.loads(request.content))
        code, body, headers = statuses.pop(0)
        return httpx.Response(code, json=body, headers=headers)

    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handle)),
    )
    monkeypatch.setattr(providers, "LAST_CALL", {})
    monkeypatch.setattr(providers.time, "sleep", sleeps.append)
    return requests, sleeps


SUCCESS = {
    "choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}]
}


def test_strict_report_schema_not_duplicated_in_prompt(monkeypatch):
    bodies, _ = setup_transport(monkeypatch, [(200, SUCCESS, {})])
    settings = Settings(_env_file=None, groq_api_key="FAKE-OFFLINE-KEY")
    schema = ResearchJudgment.model_json_schema()
    providers.groq_json(
        settings,
        "openai/gpt-oss-120b",
        "System",
        {"answer": "Entire original answer", "output_schema": schema},
    )
    body = bodies[0]
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"][
        "schema"
    ] == providers.portable_schema(schema)
    assert "$defs" not in body["response_format"]["json_schema"]["schema"]
    assert body["reasoning_effort"] == "low"
    assert body["max_completion_tokens"] == 3000
    payload = json.loads(body["messages"][1]["content"])
    assert (
        "output_schema" not in payload and payload["answer"] == "Entire original answer"
    )


def test_temporary_rate_limit_waits_once(monkeypatch):
    bodies, sleeps = setup_transport(
        monkeypatch,
        [
            (429, {"error": {"message": "temporary rate limit"}}, {"retry-after": "2"}),
            (200, SUCCESS, {}),
        ],
    )
    result = providers.groq_json(
        Settings(_env_file=None, groq_api_key="FAKE"), "qwen/qwen3.8-27b", "System", {}
    )
    assert result == {"ok": True} and len(bodies) == 2 and sleeps == [2.0]
    assert bodies[0]["reasoning_effort"] == "none"
    assert bodies[0]["max_completion_tokens"] == 1200


@pytest.mark.parametrize(
    "message,category",
    [
        ("request too large for free tier", "request_too_large"),
        ("tokens per day exhausted", "daily_quota"),
    ],
)
def test_non_transient_quota_never_retries(monkeypatch, message, category):
    bodies, sleeps = setup_transport(
        monkeypatch, [(429, {"error": {"message": message}}, {"retry-after": "30"})]
    )
    with pytest.raises(GenerationError) as error:
        providers.groq_json(
            Settings(_env_file=None, groq_api_key="FAKE"),
            "openai/gpt-oss-20b",
            "System",
            {},
        )
    assert error.value.category == category and len(bodies) == 1 and sleeps == []


def test_schema_rejection_retries_format_with_same_model(monkeypatch):
    bodies, _ = setup_transport(
        monkeypatch,
        [
            (
                400,
                {
                    "error": {
                        "param": "response_format",
                        "message": "Unsupported schema",
                    }
                },
                {},
            ),
            (200, SUCCESS, {}),
        ],
    )
    result = providers.groq_json(
        Settings(_env_file=None, groq_api_key="FAKE"),
        "openai/gpt-oss-20b",
        "System",
        {},
    )
    assert result == {"ok": True}
    assert len(bodies) == 2 and bodies[0]["model"] == bodies[1]["model"]
    assert bodies[1]["response_format"] == {"type": "json_object"}


def test_gateway_error_is_not_claimed_as_invalid_json(monkeypatch):
    setup_transport(monkeypatch, [(503, {"error": "Unavailable"}, {})])
    with pytest.raises(GenerationError) as error:
        providers.groq_json(
            Settings(_env_file=None, groq_api_key="FAKE"),
            "openai/gpt-oss-20b",
            "System",
            {},
        )
    assert error.value.category == "provider_unavailable"


def test_wrapped_json_and_canonical_evidence():
    from app.research.service import (
        evidence_catalog,
        attach_exact_evidence,
        constrained_report_schema,
    )

    assert providers.decode_model_content('```json\n{"ok":true}\n```') == {"ok": True}
    sources = [
        {
            "id": "A1",
            "text": "A court must consider the applicable rule and any exception.",
        }
    ]
    catalog = evidence_catalog(sources)
    selected = next(iter(catalog))
    result = attach_exact_evidence(
        {"claim_checks": [{"evidence": [{"evidence_id": selected}]}]}, sources
    )
    assert result["claim_checks"][0]["evidence"][0] == catalog[selected]
    schema = providers.portable_schema(constrained_report_schema(sources))
    assert "$defs" not in schema and "anyOf" not in json.dumps(schema)
