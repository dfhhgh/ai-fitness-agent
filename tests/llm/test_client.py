"""Tests for app.llm.client — fully mocked, no network access."""

import json
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.llm.client import LLMClient
from app.llm.exceptions import LLMConnectionError, LLMResponseError


def _make_chat_response(content: str) -> dict:
    """Build a minimal OpenAI-compatible chat completion response body."""
    return {
        "id": "test-id",
        "object": "chat.completion",
        "model": "Qwen/Qwen3-8B",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
    }


def _mock_httpx_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body, ensure_ascii=False)
    return resp


class TestLLMClientChat:
    """Tests for LLMClient.chat()."""

    def test_chat_success(self):
        """Valid response returns assistant content string."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")
        body = _make_chat_response("أهلاً بيك! 😊")
        mock_resp = _mock_httpx_response(200, body)

        with patch("app.llm.client.httpx.post", return_value=mock_resp) as mock_post:
            result = client.chat([{"role": "user", "content": "مرحبا"}])

        assert result == "أهلاً بيك! 😊"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "/v1/chat/completions" in call_kwargs.args[0]

    def test_chat_http_error(self):
        """HTTP 500 raises LLMResponseError."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")
        mock_resp = _mock_httpx_response(500, {"error": "internal"})

        with patch("app.llm.client.httpx.post", return_value=mock_resp):
            with pytest.raises(LLMResponseError, match="HTTP 500"):
                client.chat([{"role": "user", "content": "test"}])

    def test_chat_timeout(self):
        """Timeout raises LLMConnectionError."""
        client = LLMClient(
            base_url="http://localhost:8000", model="test-model", timeout=1.0
        )

        with patch(
            "app.llm.client.httpx.post",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(LLMConnectionError, match="timed out"):
                client.chat([{"role": "user", "content": "test"}])

    def test_chat_connect_error(self):
        """Connection failure raises LLMConnectionError."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")

        with patch(
            "app.llm.client.httpx.post",
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(LLMConnectionError, match="Could not connect"):
                client.chat([{"role": "user", "content": "test"}])

    def test_chat_malformed_response_no_choices(self):
        """Response missing 'choices' raises LLMResponseError."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")
        mock_resp = _mock_httpx_response(200, {"id": "x", "model": "m"})

        with patch("app.llm.client.httpx.post", return_value=mock_resp):
            with pytest.raises(LLMResponseError, match="choices"):
                client.chat([{"role": "user", "content": "test"}])

    def test_chat_malformed_response_no_content(self):
        """Response with empty content raises LLMResponseError."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")
        body = {
            "choices": [{"index": 0, "message": {"role": "assistant"}}],
        }
        mock_resp = _mock_httpx_response(200, body)

        with patch("app.llm.client.httpx.post", return_value=mock_resp):
            with pytest.raises(LLMResponseError, match="content"):
                client.chat([{"role": "user", "content": "test"}])

    def test_chat_empty_content_string(self):
        """Response with empty/whitespace content raises LLMResponseError."""
        client = LLMClient(base_url="http://localhost:8000", model="test-model")
        body = _make_chat_response("   ")
        mock_resp = _mock_httpx_response(200, body)

        with patch("app.llm.client.httpx.post", return_value=mock_resp):
            with pytest.raises(LLMResponseError, match="empty content"):
                client.chat([{"role": "user", "content": "test"}])


class TestLLMClientBaseURL:
    """Tests for base URL normalization."""

    def test_trailing_slash_stripped(self):
        """Trailing slash is removed to prevent double-slash in URL."""
        client = LLMClient(base_url="http://example.com/", model="m")
        assert client.base_url == "http://example.com"

    def test_multiple_trailing_slashes_stripped(self):
        client = LLMClient(base_url="http://example.com///", model="m")
        assert client.base_url == "http://example.com"

    def test_no_trailing_slash_unchanged(self):
        client = LLMClient(base_url="http://example.com", model="m")
        assert client.base_url == "http://example.com"

    def test_full_url_constructed_correctly(self):
        """Verify the full endpoint URL is well-formed."""
        client = LLMClient(base_url="https://example.ngrok.dev/", model="m")
        body = _make_chat_response("ok")
        mock_resp = _mock_httpx_response(200, body)

        with patch("app.llm.client.httpx.post", return_value=mock_resp) as mock_post:
            client.chat([{"role": "user", "content": "hi"}])

        called_url = mock_post.call_args.args[0]
        assert called_url == "https://example.ngrok.dev/v1/chat/completions"
        assert "//" not in called_url.split("://")[1]
