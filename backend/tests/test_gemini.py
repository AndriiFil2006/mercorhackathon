import json
from datetime import date
from unittest.mock import Mock
from uuid import UUID, uuid4

import httpx
import pytest
from google.genai import errors, types
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.ai.errors import GenerationError
from app.ai.gemini_provider import GeminiProvider
from app.ai.mock_provider import MockProvider
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.provider import get_provider
from app.ai.schemas import LegalGenerationInput, StructuredLegalAnswer
from app.core.config import Settings, get_settings
from app.db.models import Generation
from app.main import app


@pytest.fixture
def legal_input():
    return LegalGenerationInput(
        question_id=uuid4(), question_text="Fictional A and B dispute a sale.",
        domain="Contract law", jurisdiction="New York, United States",
        relevant_law_date=date(2025, 1, 1), scenario_facts="A signed an agreement.",
    )


@pytest.fixture
def answer(legal_input):
    return MockProvider().generate(legal_input).structured_answer.model_dump()


def sdk_response(answer, **overrides):
    values = dict(
        candidates=[types.Candidate(
            content=types.Content(parts=[types.Part(text=json.dumps(answer))]),
            finish_reason=types.FinishReason.STOP,
        )],
        model_version="gemini-2.5-flash-reported-version", response_id="test-response-id",
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=50, total_token_count=150,
        ),
    )
    values.update(overrides)
    return types.GenerateContentResponse(**values)


def settings(**overrides):
    return Settings(_env_file=None, **{
        "ai_provider": "gemini", "gemini_api_key": "test-key-not-real",
        "gemini_max_retries": 2, **overrides,
    })


def fake_provider(answer, **config):
    client = Mock()
    client.models.generate_content.return_value = sdk_response(answer)
    sleep = Mock()
    return GeminiProvider(settings(**config), client=client, sleep=sleep), client, sleep


def test_official_sdk_instantiation(monkeypatch, answer, legal_input):
    client = Mock()
    client.models.generate_content.return_value = sdk_response(answer)
    constructor = Mock(return_value=client)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", constructor)
    provider = get_provider(settings())
    result = provider.generate(legal_input)
    kwargs = constructor.call_args.kwargs
    assert kwargs["api_key"] == "test-key-not-real"
    assert kwargs["http_options"].timeout == 45000
    assert kwargs["http_options"].retry_options.attempts == 1
    call = client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-2.5-flash"
    assert call["config"].response_schema is None
    assert call["config"].response_json_schema == StructuredLegalAnswer.model_json_schema()
    assert call["config"].system_instruction.startswith(SYSTEM_PROMPT)
    assert call["config"].max_output_tokens == 2048
    assert result.structured_answer.model_dump() == answer
    assert result.generation_metadata["model_used"] == "gemini-2.5-flash-reported-version"
    assert result.generation_metadata["token_usage"]["total_token_count"] == 150
    assert "Cited authorities (model-generated, unverified)" in result.readable_answer
    client.close.assert_called_once()


def test_real_sdk_serialization_with_offline_transport(answer, legal_input):
    """Exercise the actual SDK serializer/HTTP path, with zero external requests."""
    from google import genai
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        assert request.url.path.endswith("gemini-2.5-flash:generateContent")
        return httpx.Response(200, json={
            "candidates": [{"content": {"role": "model", "parts": [{"text": json.dumps(answer)}]}, "finishReason": "STOP"}],
            "modelVersion": "reported-test-model", "usageMetadata": {"totalTokenCount": 42},
        })
    transport_client = httpx.Client(transport=httpx.MockTransport(handle))
    sdk = genai.Client(api_key="test-key", http_options=types.HttpOptions(
        httpx_client=transport_client, retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        result = GeminiProvider(settings(), client=sdk).generate(legal_input)
    finally:
        transport_client.close()
    assert result.structured_answer.model_dump() == answer
    assert len(requests) == 1
    assert requests[0]["generationConfig"]["responseMimeType"] == "application/json"
    wire_config = requests[0]["generationConfig"]
    assert "responseSchema" not in wire_config
    wire_schema = wire_config["responseJsonSchema"]
    assert wire_schema == StructuredLegalAnswer.model_json_schema()
    assert wire_schema["properties"]["short_answer"]["minLength"] == 1
    assert wire_schema["additionalProperties"] is False
    for invalid_field in ("additional_properties", "min_length", "property_ordering"):
        assert invalid_field not in json.dumps(wire_schema)
    assert "short_answer" in json.dumps(requests[0]["generationConfig"])
    assert requests[0]["systemInstruction"]["parts"][0]["text"].startswith(SYSTEM_PROMPT)


def test_gemini_3_sampling_and_thinking_config(answer, legal_input):
    provider, client, _ = fake_provider(answer, gemini_model="gemini-3.8-flash")
    result = provider.generate(legal_input)
    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.temperature is None
    assert config.thinking_config.thinking_level == "LOW"
    assert config.thinking_config.thinking_budget is None
    assert config.response_json_schema == StructuredLegalAnswer.model_json_schema()
    assert result.model_name == "gemini-3.8-flash"
    assert result.generation_metadata["temperature"] is None


@pytest.mark.parametrize("text,category", [("", "empty_response"), ("not json", "invalid_json"),
                                          ('{"short_answer":"only one field"}', "invalid_output")])
def test_invalid_responses(answer, legal_input, text, category):
    provider, client, sleep = fake_provider(answer)
    client.models.generate_content.return_value = sdk_response(answer, candidates=[types.Candidate(
        content=types.Content(parts=[types.Part(text=text)]), finish_reason="STOP")])
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == category
    client.models.generate_content.assert_called_once()
    sleep.assert_not_called()
    client.close.assert_called_once()


@pytest.mark.parametrize("change", [{"analysis": " "}, {"legal_rules": "not a list"},
                                   {"citations": [{"authority_name": "Missing fields"}]},
                                   {"conclusion": 12}, {"hidden_field": "forbidden"}])
def test_strict_output_validation(answer, change):
    with pytest.raises(ValidationError):
        StructuredLegalAnswer.model_validate({**answer, **change})


@pytest.mark.parametrize("response,category", [
    (types.GenerateContentResponse(prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")), "blocked_response"),
    (types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="SAFETY")]), "blocked_response"),
    (types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="MAX_TOKENS")]), "output_truncated"),
])
def test_blocked_and_truncated(answer, legal_input, response, category):
    provider, client, sleep = fake_provider(answer)
    client.models.generate_content.return_value = response
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == category
    assert client.models.generate_content.call_count == 1
    sleep.assert_not_called()


def test_missing_key_and_invalid_config(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", constructor)
    with pytest.raises(GenerationError, match="GEMINI_API_KEY"):
        get_provider(settings(gemini_api_key=""))
    constructor.assert_not_called()
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_provider="unknown")
    for name, value in (("gemini_max_retries", -1), ("gemini_timeout_seconds", 0), ("gemini_max_output_tokens", 0)):
        with pytest.raises(ValidationError):
            settings(**{name: value})
    assert "test-key-not-real" not in repr(settings())


@pytest.mark.parametrize("code,category,attempts", [
    (401, "authentication", 1), (403, "authentication", 1),
    (400, "invalid_request", 1), (404, "model_unavailable", 1),
    (429, "rate_limited", 3), (503, "provider_unavailable", 3), (504, "timeout", 3),
])
def test_api_failures(answer, legal_input, code, category, attempts):
    provider, client, sleep = fake_provider(answer)
    client.models.generate_content.side_effect = errors.APIError(code, {"error": {"message": "SECRET RAW ERROR"}})
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == category
    assert "SECRET" not in str(failure.value)
    assert client.models.generate_content.call_count == attempts
    assert sleep.call_count == attempts - 1


def test_retry_after_then_success(answer, legal_input):
    provider, client, sleep = fake_provider(answer)
    error = errors.APIError(429, {}, response=httpx.Response(429, headers={"retry-after": "3"}))
    client.models.generate_content.side_effect = [error, sdk_response(answer)]
    result = provider.generate(legal_input)
    assert result.generation_metadata["attempts"] == 2
    sleep.assert_called_once_with(3.0)


def test_long_retry_after_does_not_retry_early(answer, legal_input):
    provider, client, sleep = fake_provider(answer)
    client.models.generate_content.side_effect = errors.APIError(429, {}, response=httpx.Response(429, headers={"retry-after": "120"}))
    with pytest.raises(GenerationError):
        provider.generate(legal_input)
    sleep.assert_not_called()
    assert client.models.generate_content.call_count == 1


@pytest.mark.parametrize("error,category", [(httpx.ReadTimeout("SECRET"), "timeout"),
                                          (httpx.ConnectError("SECRET"), "provider_unavailable")])
def test_transport_retry_budget(answer, legal_input, error, category):
    provider, client, sleep = fake_provider(answer, gemini_max_retries=1)
    client.models.generate_content.side_effect = error
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == category
    assert client.models.generate_content.call_count == 2
    sleep.assert_called_once_with(1)


def test_no_usage_metadata_required(answer, legal_input):
    provider, client, _ = fake_provider(answer)
    client.models.generate_content.return_value = sdk_response(answer, usage_metadata=None, model_version=None)
    assert provider.generate(legal_input).generation_metadata["token_usage"] == {}


def test_sdk_validation_failure_is_not_retried(answer, legal_input):
    provider, client, sleep = fake_provider(answer)
    try:
        StructuredLegalAnswer.model_validate({})
    except ValidationError as error:
        client.models.generate_content.side_effect = error
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == "invalid_output"
    assert client.models.generate_content.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("detail,category,expected", [
    ({"error": {"details": [{"reason": "API_KEY_INVALID"}]}}, "authentication", "Replace GEMINI_API_KEY"),
    ({"error": {"message": "Invalid JSON payload at generation_config.response_schema: min_length"}}, "invalid_request", "structured-output schema"),
])
def test_actionable_sanitized_400_errors(answer, legal_input, detail, category, expected):
    provider, client, sleep = fake_provider(answer)
    detail["secret"] = "SECRET TOKEN NEVER EXPOSE"
    client.models.generate_content.side_effect = errors.APIError(400, detail)
    with pytest.raises(GenerationError) as failure:
        provider.generate(legal_input)
    assert failure.value.category == category
    assert expected in str(failure.value)
    assert "SECRET" not in str(failure.value)
    assert "min_length" not in str(failure.value)
    assert client.models.generate_content.call_count == 1
    sleep.assert_not_called()


def test_full_gemini_workflow_blind_boundary(client, database, generated, answer, monkeypatch):
    question, original = generated
    review = client.post("/api/v1/evaluations", json={
        "question_id": question["id"], "generation_id": original["id"], "verdict": "incorrect",
        "expert_explanation": "HIDDEN EXPERT REASON", "corrected_answer": "HIDDEN CORRECTION",
    })
    assert review.status_code == 201
    sdk = Mock()
    sdk.models.generate_content.return_value = sdk_response(answer)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", Mock(return_value=sdk))
    app.dependency_overrides[get_settings] = lambda: settings(ai_prompt_version="legal-demo-v2")
    response = client.post(f"/api/v1/questions/{question['id']}/generate")
    assert response.status_code == 201
    result = response.json()
    assert result["id"] != original["id"]
    assert result["provider"] == "gemini"
    assert result["model_name"] == "gemini-2.5-flash"
    assert result["prompt_version"] == "legal-demo-v2"
    assert result["structured_answer"] == answer
    assert result["completed_at"].endswith("Z")
    call = sdk.models.generate_content.call_args.kwargs
    prompt = call["contents"]
    for hidden in ("SECRET BENCHMARK", "Private benchmark", "HIDDEN EXPERT REASON", "HIDDEN CORRECTION", "medium", "Fictional test"):
        assert hidden not in prompt
    assert "Fictional A and B dispute a contract." in prompt
    assert "untrusted data" in call["config"].system_instruction
    with database() as session:
        saved = session.get(Generation, UUID(result["id"]))
        assert saved.ai_answer == result["ai_answer"]
        assert saved.structured_answer == answer
        assert saved.generation_metadata["model_used"] == "gemini-2.5-flash-reported-version"
        assert len(session.scalars(select(Generation)).all()) == 2
    assert client.get(f"/api/v1/generations/{result['id']}").json() == result
    assert sdk.models.generate_content.call_count == 1  # GET never generates
    evaluation = client.post("/api/v1/evaluations", json={
        "question_id": question["id"], "generation_id": result["id"], "verdict": "uncertain",
        "independent_expert_answer": "An independently drafted answer, timing not established.",
        "expert_explanation": "Primary authority still needs checking.",
    }).json()
    assert evaluation["independent_answer_received_at"] is not None
    assert evaluation["reviewer_identity_verified"] is False
    records = [json.loads(line) for line in client.get("/api/v1/exports/evaluations").text.splitlines()]
    record = next(row for row in records if row["generation"]["id"] == result["id"])
    assert record["generation"] == result
    assert record["evaluation"] == evaluation
    assert client.get(f"/api/v1/generations/{result['id']}").json() == result


@pytest.mark.parametrize("failure,status,category", [
    (None, 503, "configuration"),
    (errors.APIError(401, {"error": {"message": "API SECRET"}}), 503, "authentication"),
    (errors.APIError(429, {}), 429, "rate_limited"),
    (httpx.ReadTimeout("API SECRET"), 504, "timeout"),
])
def test_failed_generation_persisted(client, database, question_data, monkeypatch, failure, status, category):
    question = client.post("/api/v1/questions", json=question_data).json()
    sdk = Mock()
    sdk.models.generate_content.side_effect = failure
    constructor = Mock(return_value=sdk)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", constructor)
    app.dependency_overrides[get_settings] = lambda: settings(
        gemini_api_key="" if failure is None else "test-key-not-real", gemini_max_retries=0)
    response = client.post(f"/api/v1/questions/{question['id']}/generate")
    assert response.status_code == status
    result = response.json()
    assert result["status"] == "failed"
    assert result["error_category"] == category
    assert result["provider"] == "gemini"  # Never mock fallback
    assert not result["ai_answer"] and result["structured_answer"] is None
    assert "API SECRET" not in response.text
    with database() as session:
        assert session.get(Generation, UUID(result["id"])).status == "failed"
    assert client.get(f"/api/v1/generations/{result['id']}").json() == result
    if failure is None:
        constructor.assert_not_called()


def test_no_network_in_mock(legal_input, monkeypatch):
    import socket
    def deny(*args, **kwargs):
        raise AssertionError("Mock mode attempted network access")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", deny)
    result = get_provider(Settings(_env_file=None, ai_provider="mock")).generate(legal_input)
    assert result.provider == "mock"
    assert result.generation_metadata["simulated"] is True
    assert result.structured_answer.citations == []


def test_correction_reason_and_timestamp_control(client, generated):
    question, generation = generated
    payload = dict(question_id=question["id"], generation_id=generation["id"], verdict="incorrect",
                   expert_explanation="Additional facts are needed.", correction_unavailable_reason="The signed agreement is missing.")
    assert client.post("/api/v1/evaluations", json=payload).status_code == 201
    assert client.post("/api/v1/evaluations", json={**payload, "independent_answer_received_at": "2020-01-01T00:00:00Z"}).status_code == 422


def test_persistence_failure_no_model_call(database, question_data, monkeypatch):
    from app.services.question_service import create_question
    from app.services.generation_service import generate_answer
    from app.schemas.questions import QuestionCreate
    from fastapi import HTTPException
    with database() as session:
        question = create_question(session, QuestionCreate(**question_data))
        factory = Mock()
        monkeypatch.setattr("app.services.generation_service.get_provider", factory)
        monkeypatch.setattr(session, "commit", Mock(side_effect=OperationalError("sql", {}, Exception("SECRET"))))
        with pytest.raises(HTTPException) as failure:
            generate_answer(session, question.id, settings())
        assert failure.value.status_code == 503
        factory.assert_not_called()


def test_demo_seed_has_no_hidden_answers(database, monkeypatch):
    from app import demo
    from app.db.models import Question
    monkeypatch.setattr(demo, "SessionLocal", database)
    assert demo.seed_demo() == demo.seed_demo()
    with database() as session:
        questions = session.scalars(select(Question)).all()
        assert len(questions) == 5
        assert all(q.scenario_facts and q.relevant_law_date and q.jurisdiction for q in questions)
        assert all(q.reference_answer is None and q.reference_sources is None for q in questions)


def test_final_persistence_failure_is_sanitized(database, question_data, monkeypatch):
    from app.services.question_service import create_question
    from app.services.generation_service import generate_answer
    from app.schemas.questions import QuestionCreate
    from fastapi import HTTPException
    with database() as session:
        question = create_question(session, QuestionCreate(**question_data))
        original_commit = session.commit
        calls = 0
        def commit():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OperationalError("sql", {}, Exception("SECRET DATABASE DETAILS"))
            original_commit()
        monkeypatch.setattr(session, "commit", commit)
        with pytest.raises(HTTPException) as failure:
            generate_answer(session, question.id, Settings(_env_file=None, ai_provider="mock"))
        assert failure.value.status_code == 503
        assert "SECRET" not in str(failure.value.detail)
        generation_id = UUID(failure.value.detail["generation_id"])
    with database() as session:
        generation = session.get(Generation, generation_id)
        assert generation.status == "failed"
        assert generation.error_category == "persistence"
        assert generation.ai_answer == ""


def test_frontend_has_no_changes():
    """Read-only repository boundary check; never formats or generates frontend files."""
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    for args in (["git", "diff", "--name-only", "--", "frontend"],
                 ["git", "diff", "--cached", "--name-only", "--", "frontend"]):
        result = subprocess.run(args, cwd=root, check=True, capture_output=True, text=True)
        assert result.stdout.strip() == "", "Frontend changes exist; inspect ownership without reverting them"


def test_migration_preserves_historical_answer_and_review(tmp_path):
    import sqlite3
    from alembic import command
    from alembic.config import Config
    db_path = tmp_path / "legacy.db"
    config = Config("alembic.ini")
    config.attributes["database_url"] = f"sqlite:///{db_path.as_posix()}"
    command.upgrade(config, "9c2a1")
    question_id, generation_id, evaluation_id = (uuid4().hex for _ in range(3))
    timestamp = "2025-01-01 00:00:00"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO questions (id,title,question_text,domain,jurisdiction,relevant_law_date,difficulty,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (question_id, "Legacy question", "Legacy fictional scenario", "Contract law", "New York", "2025-01-01", "medium", timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO generations (id,question_id,model_name,ai_answer,status,prompt_version,created_at) VALUES (?,?,?,?,?,?,?)",
            (generation_id, question_id, "legacy-model", "EXACT ORIGINAL ANSWER", "completed", "legacy-prompt", timestamp),
        )
        connection.execute(
            "INSERT INTO evaluations (id,question_id,generation_id,verdict,error_categories,expert_explanation,created_at) VALUES (?,?,?,?,?,?,?)",
            (evaluation_id, question_id, generation_id, "uncertain", "[]", "Original review", timestamp),
        )
    command.upgrade(config, "head")
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT ai_answer,model_name,provider,structured_answer FROM generations WHERE id=?", (generation_id,)).fetchone()
        assert row == ("EXACT ORIGINAL ANSWER", "legacy-model", None, None)
        assert connection.execute("SELECT expert_explanation FROM evaluations WHERE id=?", (evaluation_id,)).fetchone() == ("Original review",)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE generations SET ai_answer='changed' WHERE id=?", (generation_id,))


def test_public_scenario_facts_reach_gemini(client, question_data, answer, monkeypatch):
    question_data["scenario_facts"] = "PUBLIC SCENARIO FACT: delivery was made on Monday."
    question = client.post("/api/v1/questions", json=question_data).json()
    sdk = Mock()
    sdk.models.generate_content.return_value = sdk_response(answer)
    monkeypatch.setattr("app.ai.gemini_provider.genai.Client", Mock(return_value=sdk))
    app.dependency_overrides[get_settings] = lambda: settings()
    assert client.post(f"/api/v1/questions/{question['id']}/generate").status_code == 201
    assert "PUBLIC SCENARIO FACT" in sdk.models.generate_content.call_args.kwargs["contents"]
