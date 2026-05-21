from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_set_lang_cookie() -> None:
    client = TestClient(app)
    response = client.get("/set-lang?lang=en&next=/", follow_redirects=False)
    assert response.status_code == 303
    assert response.cookies.get("ui_lang") == "en"
