"""Tests for news comment UI."""

from fastapi.testclient import TestClient

from app.main import app


def test_comment_page_renders() -> None:
    client = TestClient(app)
    response = client.get("/comment")
    assert response.status_code == 200
    assert "comment-form" in response.text
    assert "/api/v1/stories/generate" in response.text
    assert "story-placeholder" in response.text
    assert "comment_subtitle" not in response.text
    assert "Ироничный комментарий" in response.text or "Ironic news" in response.text


def test_generate_htmx_shows_llm_error(monkeypatch) -> None:
    from app.services.llm import LLMUnavailableError

    def fake_generate(db, **kwargs):
        raise LLMUnavailableError("No LLM available")

    monkeypatch.setattr(
        "app.api.generation_router.generate_story",
        fake_generate,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/stories/generate",
        data={
            "text": "А" * 100,
            "format": "parable",
            "language": "ru",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 503
    assert "story-error" in response.text
    assert "Ollama" in response.text or "LLM" in response.text


def test_create_redirects_to_comment() -> None:
    client = TestClient(app)
    response = client.get("/create", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/comment"


def test_home_has_comment_nav() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "/comment" in response.text
