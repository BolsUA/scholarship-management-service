# tests/conftest.py
import os
import tempfile
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

@pytest.fixture(name="temp_dirs", scope="function")
def temp_dirs_fixture():
    with tempfile.TemporaryDirectory() as temp_dir:
        application_files_dir = os.path.join(temp_dir, "application_files")
        edict_files_dir = os.path.join(temp_dir, "edict_files")
        os.makedirs(application_files_dir, exist_ok=True)
        os.makedirs(edict_files_dir, exist_ok=True)
        
        # Set the directories in environment variables
        os.environ["APPLICATION_FILES_DIR"] = application_files_dir
        os.environ["EDICT_FILES_DIR"] = edict_files_dir
        
        yield {
            "application_files_dir": application_files_dir,
            "edict_files_dir": edict_files_dir,
        }
        
        # Clean up: remove environment variables
        del os.environ["APPLICATION_FILES_DIR"]
        del os.environ["EDICT_FILES_DIR"]

# Create a TestClient that uses the test session
@pytest.fixture(name="client", scope="function")
def client_fixture(session):
    # Override the get_session dependency
    def get_session_override():
        yield session

    from importlib import reload
    import app.main
    reload(app.main)

    app.main.app.dependency_overrides[get_session] = get_session_override
    with TestClient(app.main.app) as client:
        yield client
    app.main.app.dependency_overrides.clear()
