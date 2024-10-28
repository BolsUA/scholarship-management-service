# tests/conftest.py

import pytest
from sqlmodel import SQLModel, Session, create_engine
from fastapi.testclient import TestClient
from app.main import app, get_session

# Create a test database in memory
@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False, "foreign_keys": "ON"},
    )
    SQLModel.metadata.create_all(engine)
    yield engine

# Create a new session for each test
@pytest.fixture(name="session", scope="function")
def session_fixture(engine):
    with Session(engine) as session:
        yield session

# Create a TestClient that uses the test session
@pytest.fixture(name="client", scope="function")
def client_fixture(session):
    # Override the get_session dependency
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
