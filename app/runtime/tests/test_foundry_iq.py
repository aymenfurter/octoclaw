"""Tests for foundry_iq pure functions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.runtime.services.foundry_iq import (
    _chunk_text,
    _discover_memory_files,
    _file_to_doc_id,
    _search_headers,
    _search_url,
    get_index_stats,
    test_search_connection,
)


class TestChunkText:
    def test_short_text(self) -> None:
        assert _chunk_text("hello", max_chars=100) == ["hello"]

    def test_exact_limit(self) -> None:
        text = "a" * 100
        assert _chunk_text(text, max_chars=100) == [text]

    def test_splits_on_paragraphs(self) -> None:
        text = "paragraph one\n\nparagraph two\n\nparagraph three"
        chunks = _chunk_text(text, max_chars=25)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 25 or len(chunk.split("\n\n")) == 1

    def test_very_long_single_paragraph(self) -> None:
        text = "a" * 8000
        chunks = _chunk_text(text, max_chars=4000)
        # No paragraph breaks to split on, so entire text returned as-is
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self) -> None:
        chunks = _chunk_text("", max_chars=100)
        assert chunks == [""]

    def test_multiple_paragraphs(self) -> None:
        paragraphs = [f"Paragraph {i} with some content." for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = _chunk_text(text, max_chars=100)
        assert len(chunks) >= 2
        rejoined = "\n\n".join(chunks)
        for p in paragraphs:
            assert p in rejoined


class TestFileToDocId:
    def test_deterministic(self) -> None:
        assert _file_to_doc_id("/a/b.md") == _file_to_doc_id("/a/b.md")

    def test_different_paths(self) -> None:
        assert _file_to_doc_id("/a/b.md") != _file_to_doc_id("/a/c.md")

    def test_is_md5(self) -> None:
        result = _file_to_doc_id("/path/to/file.md")
        assert len(result) == 32
        int(result, 16)  # must be valid hex


class TestDiscoverMemoryFiles:
    def test_no_dirs(self, tmp_path: Path) -> None:
        with patch("app.runtime.services.foundry_iq.cfg") as mock_cfg:
            mock_cfg.memory_daily_dir = tmp_path / "daily"
            mock_cfg.memory_topics_dir = tmp_path / "topics"
            result = _discover_memory_files()
        assert result == []

    def test_daily_files(self, tmp_path: Path) -> None:
        daily = tmp_path / "daily"
        daily.mkdir()
        (daily / "2025-01-01.md").write_text("daily log")
        (daily / "2025-01-02.md").write_text("daily log 2")
        with patch("app.runtime.services.foundry_iq.cfg") as mock_cfg:
            mock_cfg.memory_daily_dir = daily
            mock_cfg.memory_topics_dir = tmp_path / "topics"
            result = _discover_memory_files()
        assert len(result) == 2
        assert all(r["source_type"] == "daily" for r in result)
        assert "2025-01-01" in result[0]["date"]

    def test_topic_files(self, tmp_path: Path) -> None:
        topics = tmp_path / "topics"
        topics.mkdir()
        (topics / "python-tips.md").write_text("tips")
        with patch("app.runtime.services.foundry_iq.cfg") as mock_cfg:
            mock_cfg.memory_daily_dir = tmp_path / "daily"
            mock_cfg.memory_topics_dir = topics
            result = _discover_memory_files()
        assert len(result) == 1
        assert result[0]["source_type"] == "topic"
        assert "Python Tips" in result[0]["title"]

    def test_both_dirs(self, tmp_path: Path) -> None:
        daily = tmp_path / "daily"
        daily.mkdir()
        (daily / "2025-01-01.md").write_text("log")
        topics = tmp_path / "topics"
        topics.mkdir()
        (topics / "notes.md").write_text("note")
        with patch("app.runtime.services.foundry_iq.cfg") as mock_cfg:
            mock_cfg.memory_daily_dir = daily
            mock_cfg.memory_topics_dir = topics
            result = _discover_memory_files()
        assert len(result) == 2


class TestSearchHeaders:
    def test_includes_api_key(self) -> None:
        config = MagicMock()
        config.config.search_api_key = "test-key"
        headers = _search_headers(config)
        assert headers["api-key"] == "test-key"
        assert "application/json" in headers["Content-Type"]


class TestSearchUrl:
    def test_builds_url(self) -> None:
        config = MagicMock()
        config.config.search_endpoint = "https://mysearch.search.windows.net"
        url = _search_url(config, "indexes/my-idx")
        assert "mysearch.search.windows.net" in url
        assert "indexes/my-idx" in url
        assert "api-version=" in url

    def test_strips_trailing_slash(self) -> None:
        config = MagicMock()
        config.config.search_endpoint = "https://search.example.com/"
        url = _search_url(config, "indexes")
        assert "//" not in url.replace("https://", "")


class TestGetIndexStats:
    def test_not_configured(self) -> None:
        config = MagicMock()
        config.is_configured = False
        result = get_index_stats(config)
        assert result["status"] == "ok"
        assert result["document_count"] == 0
        assert result.get("index_missing") is True

    @patch("app.runtime.services.foundry_iq.requests")
    def test_success(self, mock_requests) -> None:
        config = MagicMock()
        config.is_configured = True
        config.config.index_name = "test-idx"
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"documentCount": 42, "storageSize": 1024}
        mock_requests.get.return_value = mock_resp
        result = get_index_stats(config)
        assert result["status"] == "ok"
        assert result["document_count"] == 42

    @patch("app.runtime.services.foundry_iq.requests")
    def test_404(self, mock_requests) -> None:
        config = MagicMock()
        config.is_configured = True
        config.config.index_name = "missing"
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 404
        mock_requests.get.return_value = mock_resp
        result = get_index_stats(config)
        assert result.get("index_missing") is True

    @patch("app.runtime.services.foundry_iq.requests")
    def test_connection_error(self, mock_requests) -> None:
        config = MagicMock()
        config.is_configured = True
        config.config.index_name = "idx"
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_requests.get.side_effect = ConnectionError("timeout")
        result = get_index_stats(config)
        assert result["status"] == "error"


class TestTestSearchConnection:
    @patch("app.runtime.services.foundry_iq.requests")
    def test_success(self, mock_requests) -> None:
        config = MagicMock()
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"value": [{"name": "idx1"}, {"name": "idx2"}]}
        mock_requests.get.return_value = mock_resp
        result = test_search_connection(config)
        assert result["status"] == "ok"
        assert "2 index" in result["message"]

    @patch("app.runtime.services.foundry_iq.requests")
    def test_failure(self, mock_requests) -> None:
        config = MagicMock()
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_requests.get.return_value = mock_resp
        result = test_search_connection(config)
        assert result["status"] == "error"

    @patch("app.runtime.services.foundry_iq.requests")
    def test_exception(self, mock_requests) -> None:
        config = MagicMock()
        config.config.search_endpoint = "https://search.example.com"
        config.config.search_api_key = "key"
        mock_requests.get.side_effect = RuntimeError("boom")
        result = test_search_connection(config)
        assert result["status"] == "error"
