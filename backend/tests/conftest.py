import pytest
import socket
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.core.config import Settings, get_settings
from app.db.session import get_db, make_engine
from app.main import app

@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    """All tests must be offline, even when the developer has real keys configured."""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    def guarded_connect(sock, address):
        # Windows asyncio builds its internal socketpair over loopback.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost"):
            return original_connect(sock, address)
        raise AssertionError("External network is forbidden in automated tests")
    def guarded_create_connection(address, *args, **kwargs):
        if address[0] in ("127.0.0.1", "::1", "localhost"):
            return original_create_connection(address, *args, **kwargs)
        raise AssertionError("External network is forbidden in automated tests")
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)

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

