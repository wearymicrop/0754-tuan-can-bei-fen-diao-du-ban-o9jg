import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.pipeline import evaluate
from app.source import load_sample


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "ledger.sqlite3")) as session:
        yield session


@pytest.fixture
def dirty():
    return load_sample("dirty")


@pytest.fixture
def clean():
    return load_sample("clean")


@pytest.fixture
def dirty_result(dirty):
    return evaluate(dirty)


@pytest.fixture
def clean_result(clean):
    return evaluate(clean)
