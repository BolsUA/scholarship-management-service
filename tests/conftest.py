# tests/conftest.py

import pytest
from sqlmodel import SQLModel, Session
from fastapi.testclient import TestClient
from app.main import app, get_session
from app.database import engine

# Create a test database in memory
@pytest.fixture(name="engine", scope="session")
def engine_fixture():
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

# Create a new session for each test
@pytest.fixture(name="session", scope="function")
def session_fixture(engine):
    with Session(engine) as session:
        yield session

    session.rollback()

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
