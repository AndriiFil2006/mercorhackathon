import json
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.db.models import Question, Generation
from app.ai.provider import MockProvider, get_provider
from app.core.config import Settings
from app.ai.prompts import build_prompt

def evaluation_payload(generated, verdict="correct"):
    question, generation = generated
    return dict(question_id=question["id"], generation_id=generation["id"], verdict=verdict)

def test_health_and_openapi(client):
    assert client.get("/health").json() == {"status": "healthy"}
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/api/v1/questions", "/api/v1/questions/{question_id}",
                         "/api/v1/questions/{question_id}/generate", "/api/v1/generations/{generation_id}",
                         "/api/v1/evaluations", "/api/v1/evaluations/{evaluation_id}", "/api/v1/exports/evaluations"} <= set(paths)
    assert {"/api/legal/answer", "/api/legal/review", "/api/legal/handoff", "/api/legal/lawyer-chat"} <= set(paths)

def test_questions_and_persistence(client, database, question_data):
    response = client.post("/api/v1/questions", json=question_data)
    assert response.status_code == 201
    question = response.json()
    assert "reference_answer" not in question and "reference_sources" not in question
    assert question["created_at"].endswith("Z")
    assert client.get(f"/api/v1/questions/{question['id']}").json() == question
    assert len(client.get("/api/v1/questions?domain=Contract%20law&difficulty=medium&limit=1").json()) == 1
    assert client.get("/api/v1/questions?offset=1").json() == []
    assert client.get("/api/v1/questions?domain=Other").json() == []
    with database() as session:
        assert session.get(Question, UUID(question["id"])).reference_answer == "SECRET BENCHMARK"

@pytest.mark.parametrize("field,value", [("title", " "), ("difficulty", "extreme"), ("relevant_law_date", "bad"), ("jurisdiction", "")])
def test_question_validation(client, question_data, field, value):
    question_data[field] = value
    assert client.post("/api/v1/questions", json=question_data).status_code == 422

def test_generation_and_reference_boundary(client, generated, monkeypatch):
    question, generation = generated
    assert generation["status"] == "completed"
    assert "SIMULATED MOCK ANSWER" in generation["ai_answer"]
    assert "SECRET BENCHMARK" not in json.dumps(generation)
    assert client.get(f"/api/v1/generations/{generation['id']}").json() == generation
    captured = []
    original_generate = MockProvider.generate
    def generate(self, data):
        captured.append(data)
        assert not hasattr(data, "reference_answer")
        assert not hasattr(data, "reference_sources")
        assert "SECRET BENCHMARK" not in build_prompt(data)
        assert not hasattr(data, "difficulty")
        assert not hasattr(data, "title")
        return original_generate(self, data)
    monkeypatch.setattr(MockProvider, "generate", generate)
    assert client.post(f"/api/v1/questions/{question['id']}/generate").status_code == 201
    assert len(captured) == 1

def test_mock_deterministic(client, generated):
    question, first = generated
    second = client.post(f"/api/v1/questions/{question['id']}/generate").json()
    assert second["ai_answer"] == first["ai_answer"]
    assert isinstance(get_provider(Settings(ai_provider="openai", openai_api_key="")), MockProvider)

def test_evaluation_and_export(client, generated):
    payload = evaluation_payload(generated)
    payload.update(expert_explanation="Expert reviewed the relevant rules.", confidence=4,
                   supporting_sources=[{"title": "Reviewer-supplied authority", "citation": "Fictional test citation"}])
    response = client.post("/api/v1/evaluations", json=payload)
    assert response.status_code == 201
    result = response.json()
    assert result["verification_status"] == "expert_approved"
    assert client.get(f"/api/v1/evaluations/{result['id']}").json() == result
    assert client.get("/api/v1/evaluations").json() == [result]
    exported = client.get("/api/v1/exports/evaluations")
    assert "attachment" in exported.headers["content-disposition"]
    records = [json.loads(line) for line in exported.text.splitlines()]
    assert len(records) == 1
    assert records[0]["generation"]["ai_answer"] == generated[1]["ai_answer"]
    assert records[0]["evaluation"] == result
    assert "SECRET BENCHMARK" not in exported.text
    assert "reference_answer" not in exported.text

def test_missing_and_mismatched(client, generated):
    payload = evaluation_payload(generated)
    payload["generation_id"] = str(uuid4())
    assert client.post("/api/v1/evaluations", json=payload).status_code == 404
    payload = evaluation_payload(generated)
    payload["question_id"] = str(uuid4())
    assert client.post("/api/v1/evaluations", json=payload).status_code == 422
    for path in ("questions", "generations", "evaluations"):
        assert client.get(f"/api/v1/{path}/{uuid4()}").status_code == 404
    assert client.post(f"/api/v1/questions/{uuid4()}/generate").status_code == 404

@pytest.mark.parametrize("verdict", ["incorrect", "partially_correct"])
def test_corrections_required(client, generated, verdict):
    payload = evaluation_payload(generated, verdict)
    assert client.post("/api/v1/evaluations", json=payload).status_code == 422
    payload.update(expert_explanation="Missing a material exception.", corrected_answer="Apply the exception after confirming facts.",
                   error_categories=["incomplete_answer"])
    assert client.post("/api/v1/evaluations", json=payload).status_code == 201

def test_abstention_and_validation(client, generated):
    payload = evaluation_payload(generated, "uncertain")
    assert client.post("/api/v1/evaluations", json=payload).json()["verification_status"] == "expert_abstained"
    for change in ({"confidence": 6}, {"error_categories": ["fake"]}, {"confidence": True}):
        assert client.post("/api/v1/evaluations", json={**payload, **change}).status_code == 422
    assert client.get("/api/v1/questions?limit=0").status_code == 422

def test_failure_and_immutability(client, database, generated, monkeypatch):
    question, generation = generated
    with database() as session:
        record = session.get(Generation, UUID(generation["id"]))
        record.ai_answer = "Changed"
        with pytest.raises(ValueError, match="immutable"):
            session.commit()
        session.rollback()
    def fail(self, data):
        raise RuntimeError("SECRET PROVIDER TOKEN")
    monkeypatch.setattr(MockProvider, "generate", fail)
    failed = client.post(f"/api/v1/questions/{question['id']}/generate").json()
    assert failed["status"] == "failed"
    assert "SECRET" not in json.dumps(failed)
    payload = dict(question_id=question["id"], generation_id=failed["id"], verdict="correct")
    assert client.post("/api/v1/evaluations", json=payload).status_code == 409

def test_empty_export(client):
    assert client.get("/api/v1/exports/evaluations").text == ""

def test_database_guards(database, generated):
    from sqlalchemy import update, delete
    from sqlalchemy.exc import IntegrityError
    generation_id = UUID(generated[1]["id"])
    for statement in (
        update(Generation).where(Generation.id == generation_id).values(ai_answer="Changed by SQL"),
        delete(Generation).where(Generation.id == generation_id),
    ):
        with database() as session:
            with pytest.raises(IntegrityError, match="immutable"):
                session.execute(statement)
            session.rollback()
    with database() as session:
        session.add(Generation(question_id=uuid4(), model_name="mock", prompt_version="test"))
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()
        session.rollback()

def test_seed_is_idempotent(database, monkeypatch):
    from app import seed
    monkeypatch.setattr(seed, "SessionLocal", database)
    assert seed.seed() == 5
    assert seed.seed() == 0
    with database() as session:
        records = session.scalars(select(Question)).all()
        assert len(records) == 5
        assert all("[FICTIONAL DEMO]" in item.title and item.jurisdiction and item.relevant_law_date for item in records)

