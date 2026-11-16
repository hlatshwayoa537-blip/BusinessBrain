from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "businessbrain-api"}


def test_root_returns_api_identity() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "BusinessBrain API"
