"""Tests for LLM provider selection."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm import LLMUnavailableError, select_provider


def test_select_provider_prefers_ollama_in_auto_mode() -> None:
    client = MagicMock()
    with patch("app.services.llm._ollama_available", return_value=True):
        assert select_provider(client) == "ollama"


def test_select_provider_falls_back_to_openai() -> None:
    client = MagicMock()
    with patch("app.services.llm._ollama_available", return_value=False):
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.llm_provider = "auto"
            mock_settings.openai_api_key = "test-key"
            assert select_provider(client) == "openai"


def test_select_provider_raises_when_none_available() -> None:
    client = MagicMock()
    with patch("app.services.llm._ollama_available", return_value=False):
        with patch("app.services.llm.settings") as mock_settings:
            mock_settings.llm_provider = "auto"
            mock_settings.openai_api_key = ""
            with pytest.raises(LLMUnavailableError):
                select_provider(client)
