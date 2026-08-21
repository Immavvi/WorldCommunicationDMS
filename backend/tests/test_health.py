from fastapi.testclient import TestClient

from app.main import app


def test_application_starts_and_health_endpoint_is_available() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "wcdms-api"}
