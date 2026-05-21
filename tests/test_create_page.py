"""Tests for story creation UI."""

from fastapi.testclient import TestClient

from app.main import app


def test_create_page_renders() -> None:
    client = TestClient(app)
    response = client.get("/create")
    assert response.status_code == 200
    assert "create-form" in response.text
    assert "/api/v1/stories/generate" in response.text


def test_home_has_nav_links() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "/create" in response.text
