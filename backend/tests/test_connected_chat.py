import copy
import hashlib
import json
from uuid import UUID
import pytest
from sqlalchemy import select
from app.ai.errors import GenerationError
from app.core.config import Settings, get_settings
from app.db.models import LegalHandoff, AutomatedReview, Question
from app.research.service import WEIGHTS, weighted_score, aggregate, validate_evidence
from app.schemas.chat import ResearchJudgment

QUESTION = {
    "question": "Fictional tenant asks about a California deposit.",
    "jurisdiction": "United States, California",
    "lawDate": "2026-11-06",
    "externalConsent": True,
    "messages": [],
}
REVIEW = {
    "reviewer": "authority",
    "question": "Supplied question",
    "answer": "Client-supplied answer",
    "jurisdiction": "California",
    "lawDate": "2026-11-06",
    "externalConsent": True,
}
CONTEXT = {
    "id": "inquiry-1",
    "title": "Test inquiry",
    "jurisdiction": "California",
    "lawDate": "2026-11-06",
    "messages": [
        {"id": "m1", "role": "user", "text": "ALL ORIGINAL FACTS"},
        {"id": "m2", "role": "assistant", "text": "ALL MAIN ANSWER"},
    ],
    "evaluations": [
        {
            "id": "e1",
            "reviews": [{"score": 65, "sources": [{"text": "ALL RESEARCH"}]}],
            "scorerMessages": [{"role": "user", "text": "FULL SCORER CONVERSATION"}],
        }
    ],
    "selectedEvaluationId": "e1",
}


def test_main_consent_before_generation(client, database):
    r = client.post("/api/legal/answer", json={**QUESTION, "externalConsent": False})
    assert r.status_code == 403
    with database() as db:
        assert db.scalar(select(Question)) is None


def test_main_and_three_actual_answer_reviews(client):
    result = client.post("/api/legal/answer", json=QUESTION)
    assert result.status_code == 200
    answer = result.json()
    assert answer["generationId"] and answer["mode"] == "mock"
    reports = []
    for reviewer in ("authority", "jurisdiction", "reasoning"):
        r = client.post(
            "/api/legal/review",
            json={
                **REVIEW,
                "reviewer": reviewer,
                "generationId": answer["generationId"],
                "answer": "TAMPERED",
            },
        )
        assert r.status_code == 200, r.text
        reports.append(r.json())
        assert r.json()["provenance"] == "stored_main_ai_generation"
        assert "TAMPERED" not in r.text
    assert aggregate(reports)["overall_score"] == 65
    assert aggregate(reports)["recommend_lawyer"] is True
    chat = client.post(
        "/api/legal/review-chat",
        json={
            **{
                k: REVIEW[k]
                for k in [
                    "question",
                    "answer",
                    "jurisdiction",
                    "lawDate",
                    "externalConsent",
                ]
            },
            "reviews": reports,
            "history": [],
            "prompt": "Explain deductions",
        },
    )
    assert chat.status_code == 200, chat.text


def test_stored_answer_and_public_fields_not_client_tampering(client, monkeypatch):
    generated = client.post("/api/legal/answer", json=QUESTION).json()
    captured = {}

    def review(settings, db, request, public, provenance):
        captured.update(public)
        return {"ok": True}

    monkeypatch.setattr("app.api.routes.chat.make_review", review)
    client.post(
        "/api/legal/review",
        json={
            **REVIEW,
            "generationId": generated["generationId"],
            "question": "INJECTED",
            "answer": "INJECTED",
            "jurisdiction": "WRONG",
        },
    )
    assert captured["answer"] == generated["answer"]
    assert captured["question"] == QUESTION["question"]
    assert captured["jurisdiction"] == QUESTION["jurisdiction"]
    assert "reference_answer" not in captured


def test_history_to_existing_provider(client, monkeypatch):
    from app.ai.mock_provider import MockProvider

    original = MockProvider.generate
    seen = {}

    def generate(self, question):
        seen.update(question.model_dump())
        return original(self, question)

    monkeypatch.setattr(MockProvider, "generate", generate)
    history = [
        {"role": "user", "text": "Previous fact"},
        {"role": "assistant", "text": "Unverified earlier answer"},
    ]
    r = client.post("/api/legal/answer", json={**QUESTION, "messages": history})
    assert r.status_code == 200
    assert (
        json.loads(seen["scenario_facts"])["previous_conversation_untrusted"] == history
    )
    assert "reference_answer" not in seen


def test_consent_snapshot_and_model_receives_every_field(client, database, monkeypatch):
    assert (
        client.post(
            "/api/legal/handoff", json={"consentProcessing": True, "context": CONTEXT}
        ).status_code
        == 403
    )
    response = client.post(
        "/api/legal/handoff",
        json={
            "consentProcessing": True,
            "consentShareContext": True,
            "context": CONTEXT,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["handoffToken"]
    with database() as db:
        record = db.scalar(select(LegalHandoff))
        assert record.context_snapshot == CONTEXT
        assert record.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in json.dumps(record.context_snapshot)
    calls = []

    def reply(settings, system, data):
        calls.append(copy.deepcopy(data))
        return {"answer": "AI reply", "mode": "mock", "model": "test"}

    monkeypatch.setattr("app.api.routes.chat.context_reply", reply)
    assert (
        client.post(
            "/api/legal/lawyer-chat",
            json={"handoffToken": token, "message": "First question"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/legal/lawyer-chat",
            json={"handoffToken": token, "message": "Follow-up"},
        ).status_code
        == 200
    )
    assert calls[0]["consented_inquiry_snapshot"] == CONTEXT
    assert calls[1]["conversation"] == [
        {"role": "user", "text": "First question"},
        {"role": "assistant", "text": "AI reply"},
    ]
    assert (
        client.post(
            "/api/legal/handoff/revoke", json={"handoffToken": token}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/legal/lawyer-chat", json={"handoffToken": token, "message": "Blocked"}
        ).status_code
        == 410
    )
    assert len(calls) == 2
    with database() as db:
        assert db.scalar(select(LegalHandoff)).context_snapshot is None


def test_direct_ai_legal_chat_and_close(client):
    assert client.post("/api/legal/handoff", json={}).status_code == 403
    r = client.post("/api/legal/handoff", json={"consentProcessing": True})
    assert r.status_code == 201 and r.json()["contextShared"] is False
    token = r.json()["handoffToken"]
    reply = client.post(
        "/api/legal/lawyer-chat", json={"handoffToken": token, "message": "Hello"}
    )
    assert reply.status_code == 200 and reply.json()["realLawyer"] is False
    assert (
        client.post(
            "/api/legal/handoff/close", json={"handoffToken": token}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/legal/lawyer-chat",
            json={"handoffToken": token, "message": "Cannot continue"},
        ).status_code
        == 410
    )
    assert (
        client.post(
            "/api/legal/lawyer-chat",
            json={"handoffToken": "x" * 40, "message": "Invalid token"},
        ).status_code
        == 404
    )


def test_no_silent_handoff_truncation(client, monkeypatch):
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock", chat_context_max_chars=10000
    )
    large = copy.deepcopy(CONTEXT)
    large["messages"][0]["text"] = "x" * 11000
    assert (
        client.post(
            "/api/legal/handoff",
            json={
                "consentProcessing": True,
                "consentShareContext": True,
                "context": large,
            },
        ).status_code
        == 413
    )


def judgment(n=70):
    return {
        "criteria": {
            key: {"score": n, "reason": "Specific reason based on S1"}
            for key in WEIGHTS
        },
        "research_summary": "Read retrieved page",
        "jurisdiction_analysis": "Specific jurisdiction analysis",
        "date_analysis": "Date applicability limitation",
        "claim_checks": [
            {
                "claim": "The answer says X",
                "verdict": "contradicted",
                "explanation": "The source says something different",
                "evidence": [{"source_id": "S1", "quote": "exact quoted text"}],
            }
        ],
        "limitations": ["No exhaustive legal search"],
        "suggested_correction": "Qualified correction with S1",
        "conclusion": "Specific explanation",
        "abstain": False,
        "abstention_reason": "",
    }


SOURCE = {
    "id": "S1",
    "title": "Official source fixture",
    "url": "https://example.gov/law",
    "text": "Here is exact quoted text for testing.",
    "retrieved_at": "2026-11-06T00:00:00Z",
    "evidence_type": "extracted_page",
    "truncated": False,
    "published_date": None,
}


def test_weighted_formula_and_boundary():
    assert weighted_score(judgment(70)["criteria"]) == 70
    reports = [
        {"id": key, "status": "complete", "score": 80}
        for key in ["authority", "jurisdiction", "reasoning"]
    ]
    assert aggregate(reports)["recommend_lawyer"] is False
    reports[0]["score"] = 76
    assert aggregate(reports)["recommend_lawyer"] is True
    reports[0]["status"] = "abstained"
    assert aggregate(reports)["overall_score"] is None
    assert aggregate([reports[1]] * 3)["overall_score"] is None


def test_unknown_sources_false_quotes_and_snippets_cannot_pass():
    good = ResearchJudgment.model_validate(judgment())
    validate_evidence(good, [SOURCE])
    bad = judgment()
    bad["claim_checks"][0]["evidence"][0]["quote"] = "FABRICATED"
    with pytest.raises(GenerationError):
        validate_evidence(ResearchJudgment.model_validate(bad), [SOURCE])
    bad = judgment()
    bad["claim_checks"][0]["evidence"][0]["source_id"] = "NOT_RETRIEVED"
    with pytest.raises(GenerationError):
        validate_evidence(ResearchJudgment.model_validate(bad), [SOURCE])
    with pytest.raises(GenerationError):
        validate_evidence(good, [{**SOURCE, "evidence_type": "search_excerpt"}])


def test_live_review_research_and_cache_without_network(client, monkeypatch):
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock", review_mode="live"
    )
    prompts = []

    def model(settings, model, system, data):
        prompts.append(data)
        return (
            {"queries": ["site:example.gov legal issue"], "claims_to_check": ["X"]}
            if "output_schema" not in data
            else judgment()
        )

    monkeypatch.setattr("app.research.service.groq_json", model)
    monkeypatch.setattr(
        "app.research.service.search_evidence", lambda *args: ([SOURCE], [])
    )
    r = client.post("/api/legal/review", json=REVIEW)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["score"] == 70 and report["sources"][0]["text"] == SOURCE["text"]
    assert (
        report["research"]["claim_checks"][0]["evidence"][0]["quote"]
        == "exact quoted text"
    )
    cached = client.post("/api/legal/review", json=REVIEW)
    assert cached.json()["reportId"] == report["reportId"] and cached.json()["cached"]
    assert len(prompts) == 2
    second = client.post("/api/legal/review", json={**REVIEW, "force": True})
    assert second.json()["reportId"] != report["reportId"] and len(prompts) == 4


def test_review_errors_never_become_scores(client, monkeypatch):
    def fail(*args):
        raise GenerationError("rate_limited", "Safe quota message", 429)

    monkeypatch.setattr("app.api.routes.chat.make_review", fail)
    response = client.post("/api/legal/review", json=REVIEW)
    assert response.status_code == 429 and "score" not in response.json()


def test_main_provider_configuration_and_api_config_do_not_leak(client):
    r = client.get("/api/legal/config")
    assert r.status_code == 200
    assert "gemini_api_key" not in r.text and "groq_api_key" not in r.text


def test_abstention_never_uses_dimension_scores_as_final_score(client, monkeypatch):
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock", review_mode="live"
    )

    def model(settings, model, system, data):
        if "output_schema" not in data:
            return {"queries": ["public legal query"], "claims_to_check": ["X"]}
        report = judgment(90)
        report["abstain"] = True
        report["abstention_reason"] = "Cannot establish law date"
        return report

    monkeypatch.setattr("app.research.service.groq_json", model)
    monkeypatch.setattr(
        "app.research.service.search_evidence", lambda *args: ([SOURCE], [])
    )
    result = client.post("/api/legal/review", json=REVIEW)
    assert result.status_code == 200 and result.json()["status"] == "abstained"
    assert result.json()["score"] is None


def test_distinct_model_requirement(client, monkeypatch):
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(
        ai_provider="mock",
        review_mode="live",
        review_model_authority="same",
        review_model_jurisdiction="same",
        review_model_reasoning="same",
    )
    result = client.post("/api/legal/review", json=REVIEW)
    assert (
        result.status_code == 503
        and result.json()["detail"]["category"] == "configuration"
    )


def test_busy_lease_prevents_second_send(client, database):
    from datetime import timedelta
    from app.db.models import utcnow

    token = client.post("/api/legal/handoff", json={"consentProcessing": True}).json()[
        "handoffToken"
    ]
    with database() as db:
        record = db.scalar(select(LegalHandoff))
        record.busy_until = utcnow() + timedelta(minutes=1)
        db.commit()
    r = client.post(
        "/api/legal/lawyer-chat",
        json={"handoffToken": token, "message": "blocked concurrent send"},
    )
    assert r.status_code == 409


def test_reviewer_search_extract_marks_provenance(monkeypatch):
    import httpx
    from app.research.service import search_evidence

    real_client = httpx.Client
    requests = []

    def transport(req):
        requests.append(req)
        if req.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Law",
                            "url": "https://example.gov/legal",
                            "content": "Short search snippet",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.gov/legal",
                        "raw_content": "A much longer extracted legal page.",
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "app.research.service.httpx.Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(transport)),
    )
    sources, warnings = search_evidence(
        Settings(tavily_api_key="NOT-A-REAL-KEY"), ["public query"], "A"
    )
    assert len(requests) == 2 and sources[0]["evidence_type"] == "extracted_page"
    assert sources[0]["text"] == "A much longer extracted legal page."
    assert sources[0]["id"] == "A1" and sources[0]["retrieved_at"]
    assert not warnings


def test_context_wrapper_reuses_gemini_and_full_payload(monkeypatch):
    from unittest.mock import Mock
    from app.ai.context_chat import context_reply, ChatReply
    from app.research.prompts import LAWYER_SYSTEM

    sdk = Mock()
    sdk.models.generate_content.return_value.text = json.dumps(
        {"answer": "AI legal assistant reply"}
    )
    constructor = Mock(return_value=sdk)
    monkeypatch.setattr("app.ai.context_chat.genai.Client", constructor)
    settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        gemini_api_key="FAKE-OFFLINE-KEY",
        gemini_max_retries=0,
    )
    payload = {
        "consented_inquiry_snapshot": CONTEXT,
        "conversation": [{"role": "user", "text": "Complete prior turn"}],
        "message": "Follow-up",
    }
    result = context_reply(settings, LAWYER_SYSTEM, payload)
    assert result["model"] == settings.gemini_model
    call = sdk.models.generate_content.call_args.kwargs
    assert json.loads(call["contents"]) == payload
    assert call["config"].response_json_schema == ChatReply.model_json_schema()
    assert call["config"].system_instruction == LAWYER_SYSTEM
    sdk.close.assert_called_once()


def test_groq_client_paces_and_sends_distinct_model_without_network(monkeypatch):
    import httpx
    from app.research import providers

    original = httpx.Client
    bodies = []

    def transport(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ]
            },
        )

    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(transport)),
    )
    monkeypatch.setattr(providers, "LAST_CALL", {"model-a": 100.0})
    monkeypatch.setattr(providers.time, "monotonic", lambda: 110.0)
    sleeps = []
    monkeypatch.setattr(providers.time, "sleep", sleeps.append)
    settings = Settings(
        _env_file=None, groq_api_key="FAKE-KEY", groq_min_interval_seconds=60
    )
    assert providers.groq_json(settings, "model-a", "System", {"text": "Data"}) == {
        "ok": True
    }
    assert sleeps == [50.0]
    assert bodies[0]["model"] == "model-a"
    assert bodies[0]["response_format"]["type"] == "json_schema"
    assert bodies[0]["response_format"]["json_schema"]["strict"] is True
    assert bodies[0]["max_completion_tokens"] == 1200
