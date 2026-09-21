"""Exceptions for the LLM integration layer.

Provides a small, meaningful hierarchy for errors originating from
the LLM HTTP client and the profile extraction pipeline.
"""


class LLMClientError(Exception):
    """Base exception for all LLM client errors."""


class LLMConnectionError(LLMClientError):
    """Raised when the LLM server is unreachable, times out, or a network error occurs."""


class LLMResponseError(LLMClientError):
    """Raised when the LLM server returns an HTTP error or a malformed response."""


class LLMExtractionError(LLMClientError):
    """Raised when the LLM output cannot be parsed into a valid ProfilePatch."""
