from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert "timestamp" in body


def test_meta_exposes_versions() -> None:
    response = TestClient(app).get("/api/v1/meta")
    assert response.status_code == 200
    assert response.json()["schema_version"] == "1"
