from django.test import Client


def test_health_endpoint() -> None:
    response = Client().get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "code": 200,
        "message": "Service is healthy.",
        "data": {"status": "ok"},
    }
