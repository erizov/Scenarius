"""Tests for embedding helpers and semantic fallback."""

from unittest.mock import MagicMock, patch

from app.services.embeddings import semantic_match


def test_semantic_match_skips_query_when_table_missing() -> None:
    db = MagicMock()
    with patch(
        "app.services.embeddings._embeddings_table_exists",
        return_value=False,
    ):
        rows = semantic_match(db, context="новости дня", language="ru")
    assert rows == []
    db.execute.assert_not_called()
