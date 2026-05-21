"""Tests for story generation orchestration."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.generation import StoryCitation, StoryResult, generate_story
from app.services.llm import LLMResult


@pytest.fixture
def sample_story_result() -> StoryResult:
    return StoryResult(
        story="Once upon a time there was news.",
        format="story",
        language="ru",
        news_title="Test news",
        news_source_url=None,
        citations=[
            StoryCitation(
                id=uuid.uuid4(),
                text="Test quote",
                fragment_type="quote",
                work_title="Film",
            ),
        ],
        provider="ollama",
        model="llama3.2",
    )


def test_generate_story_endpoint_json(monkeypatch, sample_story_result) -> None:
    def fake_generate(db, **kwargs):
        return sample_story_result

    monkeypatch.setattr(
        "app.api.generation_router.generate_story",
        fake_generate,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/stories/generate",
        json={
            "text": "А" * 100,
            "format": "story",
            "language": "ru",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["story"] == sample_story_result.story
    assert payload["provider"] == "ollama"
    assert len(payload["citations"]) == 1


def test_generate_story_rejects_missing_input() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/stories/generate",
        json={"format": "story", "language": "ru"},
    )
    assert response.status_code == 400


@patch("app.services.generation.generate_text")
@patch("app.services.generation._retrieve_fragments")
@patch("app.services.generation.resolve_news_input")
def test_generate_story_service(
    mock_news,
    mock_retrieve,
    mock_llm,
    sample_story_result,
) -> None:
    from app.services.news import NewsContent

    mock_news.return_value = NewsContent(title="News", body="А" * 100)
    mock_retrieve.return_value = []
    mock_llm.return_value = LLMResult(
        text="Generated tale",
        provider="ollama",
        model="llama3.2",
    )

    class FakeDb:
        pass

    result = generate_story(
        FakeDb(),
        text="А" * 100,
        story_format="fairy_tale",
        language="ru",
    )
    assert result.story == "Generated tale"
    assert result.format == "fairy_tale"
