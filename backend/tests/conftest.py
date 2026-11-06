import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings, get_settings
from app.db.session import get_db, make_engine
from app.main import app

@pytest.fixture
def database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = make_engine(url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()

@pytest.fixture
def client(database):
    def sessions():
        with database() as session:
            yield session
    app.dependency_overrides[get_db] = sessions
    app.dependency_overrides[get_settings] = lambda: Settings(ai_provider="mock", openai_api_key="")
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

@pytest.fixture
def question_data():
    return dict(title="Fictional test", question_text="Fictional A and B dispute a contract.",
                domain="Contract law", jurisdiction="New York, United States",
                relevant_law_date="2025-01-01", difficulty="medium",
                reference_answer="SECRET BENCHMARK", reference_sources=[{"title": "Private benchmark"}])

@pytest.fixture
def generated(client, question_data):
    question = client.post("/api/v1/questions", json=question_data).json()
    generation = client.post(f"/api/v1/questions/{question['id']}/generate").json()
    return question, generation

