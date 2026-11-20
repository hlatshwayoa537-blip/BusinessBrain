from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

client = TestClient(app)


class FakeResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, schema_revision="0030_payfast_payments", fail=False):
        self.schema_revision = schema_revision
        self.fail = fail

    def execute(self, statement):
        if self.fail:
            raise RuntimeError("database unavailable")
        if "version_num" in str(statement):
            return FakeResult(self.schema_revision)
        return FakeResult()


def test_health_check_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vexion-api"}


def test_readiness_reports_database_schema_and_optional_integrations() -> None:
    session = FakeSession()
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["schema"] == "ok"
    assert body["checks"]["schema_revision"] == "0030_payfast_payments"
    assert body["optional_integrations"]["payfast"] in {"configured", "not_configured"}
    assert body["optional_integrations"]["document_storage_and_scanning"] in {"configured", "not_configured"}


def test_readiness_fails_when_database_is_unavailable() -> None:
    session = FakeSession(fail=True)
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "schema": "unavailable"},
    }


def test_readiness_fails_when_schema_is_not_initialized() -> None:
    session = FakeSession(schema_revision=None)
    app.dependency_overrides[get_db] = lambda: session
    try:
        response = client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.json()["checks"]["schema"] == "not_initialized"


def test_root_returns_api_identity() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "VEXION API"
