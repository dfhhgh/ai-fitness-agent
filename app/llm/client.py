"""Lightweight HTTP client for the remote LLM inference server.

Sends OpenAI-compatible chat completion requests and returns the raw
assistant content string.  Completely independent of profile models
and business logic.
"""

from typing import Any, Dict, List

import httpx

from app.llm.exceptions import LLMConnectionError, LLMResponseError


class LLMClient:
    """Thin wrapper around the OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        # Normalize: strip trailing slashes so joining never produces "//"
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 400,
        temperature: float = 0.0,
        top_p: float = 0.9,
    ) -> str:
        """Send a chat completion request and return the assistant's content.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            top_p: Nucleus sampling parameter.

        Returns:
            The text content from ``choices[0].message.content``.

        Raises:
            LLMConnectionError: Network or timeout failure.
            LLMResponseError: HTTP error, malformed body, or missing fields.
        """
        url = f"{self._base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=self._timeout,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        except httpx.TimeoutException as exc:
            raise LLMConnectionError(
                f"Request to LLM server timed out after {self._timeout}s"
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMConnectionError(
                f"Could not connect to LLM server at {self._base_url}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError(
                f"Network error communicating with LLM server: {exc}"
            ) from exc

        # HTTP-level errors
        if response.status_code != 200:
            raise LLMResponseError(
                f"LLM server returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        # Parse JSON body
        try:
            body = response.json()
        except Exception as exc:
            raise LLMResponseError(
                "LLM server returned non-JSON response"
            ) from exc

        # Extract content
        return self._extract_content(body)

    @staticmethod
    def _extract_content(body: Dict[str, Any]) -> str:
        """Pull ``choices[0].message.content`` from the response body.

        Raises:
            LLMResponseError: If the expected structure is missing.
        """
        choices = body.get("choices")
        if not choices or not isinstance(choices, list):
            raise LLMResponseError(
                "LLM response missing 'choices' array"
            )

        first = choices[0]
        message = first.get("message")
        if not message or not isinstance(message, dict):
            raise LLMResponseError(
                "LLM response missing 'message' in first choice"
            )

        content = message.get("content")
        if content is None:
            raise LLMResponseError(
                "LLM response missing 'content' in message"
            )

        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "LLM response returned empty content"
            )

        return content
