"""Profile extraction pipeline: user message → LLM → ProfilePatch.

Sends the user message to the remote LLM with the extraction system prompt,
parses the returned JSON, and validates it into the existing ProfilePatch model.

This module does NOT:
- merge patches into profiles
- calculate missing fields
- determine interview state
- apply conflict resolution
- calculate calories/macros
- generate workouts
"""

import json
import re
from typing import Any, Dict

from app.llm.client import LLMClient
from app.llm.exceptions import LLMExtractionError
from app.llm.prompts import PROFILE_EXTRACTION_SYSTEM_PROMPT
from app.profile.models import ProfilePatch


# Regex to strip ```json ... ``` fences the LLM may accidentally emit
_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL,
)


class ProfileExtractor:
    """Extracts a ProfilePatch from a raw user message via the remote LLM."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def extract(self, user_message: str) -> ProfilePatch:
        """Send *user_message* through the LLM and return a validated ProfilePatch.

        Args:
            user_message: Raw text from the user (typically Egyptian Arabic).

        Returns:
            A validated ``ProfilePatch`` instance.

        Raises:
            LLMExtractionError: If the LLM output cannot be parsed or validated.
            LLMConnectionError: Propagated from ``LLMClient`` on network issues.
            LLMResponseError: Propagated from ``LLMClient`` on HTTP/response issues.
        """
        messages = [
            {"role": "system", "content": PROFILE_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        raw_text = self._client.chat(messages)
        cleaned = self._clean_llm_output(raw_text)
        parsed = self._parse_json(cleaned)
        return self._to_profile_patch(parsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_llm_output(text: str) -> str:
        """Strip whitespace and remove accidental Markdown JSON fences."""
        text = text.strip()
        match = _JSON_FENCE_RE.match(text)
        if match:
            text = match.group(1).strip()
        return text

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Parse *text* as JSON.

        Raises:
            LLMExtractionError: If the text is not valid JSON.
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMExtractionError(
                f"LLM returned invalid JSON: {exc}. "
                f"Raw text (first 300 chars): {text[:300]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMExtractionError(
                f"LLM returned JSON of type {type(data).__name__}, expected object"
            )
        return data

    @staticmethod
    def _to_profile_patch(data: Dict[str, Any]) -> ProfilePatch:
        """Validate *data* into the existing ProfilePatch Pydantic model.

        Raises:
            LLMExtractionError: If validation against ProfilePatch fails.
        """
        try:
            return ProfilePatch.model_validate(data)
        except Exception as exc:
            raise LLMExtractionError(
                f"LLM output failed ProfilePatch validation: {exc}"
            ) from exc
