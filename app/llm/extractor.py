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
import logging
import re
from typing import Any, Dict

from app.llm.client import LLMClient
from app.llm.exceptions import LLMExtractionError
from app.llm.prompts import PROFILE_EXTRACTION_SYSTEM_PROMPT
from app.profile.models import ProfilePatch
from app.profile.validator import validate_profile_patch

logger = logging.getLogger(__name__)



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
        logger.debug("LLM raw output (first 500 chars): %s", raw_text[:500])
        cleaned = self._clean_llm_output(raw_text)
        parsed = self._parse_json(cleaned)
        logger.debug("Parsed LLM updates keys: %s", list(parsed.get("updates", {}).keys()))
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
        """Validate *data* into ProfilePatch and enforce deterministic validation rules.

        If the LLM returns nested section dicts (e.g. ``{"health": {"injuries": []}}``),
        they are flattened to dotted paths (e.g. ``{"health.injuries": []}``) before
        validation. Only known section prefixes are flattened; arbitrary top-level
        dicts are passed through unchanged so the validator rejects them.

        Raises:
            LLMExtractionError: If validation against ProfilePatch or deterministic rules fails.
        """
        data = _flatten_nested_sections(data)
        try:
            patch = ProfilePatch.model_validate(data)
            validate_profile_patch(patch)
            return patch
        except Exception as exc:
            raise LLMExtractionError(
                f"LLM output failed ProfilePatch validation: {exc}"
            ) from exc


# Known section prefixes that the LLM may emit as nested dicts.
# Each maps to its allowed child field names.
_KNOWN_SECTIONS: Dict[str, frozenset[str]] = {
    "personal": frozenset({"age", "gender", "height_cm", "weight_kg"}),
    "goal": frozenset({"type", "target_weight_kg", "weight_change_target_kg"}),
    "training": frozenset({"days_per_week", "duration", "experience", "activity_description"}),
    "health": frozenset({"injuries"}),
    "nutrition": frozenset({"food_preferences", "disliked_foods", "disliked_activities"}),
}


def _flatten_nested_sections(data: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested section dicts in ``updates`` to dotted paths.

    Only converts ``{"section": {"field": value}}`` → ``{"section.field": value}``
    for known sections. Returns *data* unchanged if ``updates`` is missing or empty.

    This is NOT a generic JSON flattener. Unknown top-level keys in ``updates``
    are left as-is so the validator rejects them deterministically.
    """
    updates = data.get("updates")
    if not isinstance(updates, dict):
        return data

    flattened: Dict[str, Any] = {}
    for key, val in updates.items():
        if key in _KNOWN_SECTIONS and isinstance(val, dict):
            allowed_children = _KNOWN_SECTIONS[key]
            for child_key, child_val in val.items():
                dotted = f"{key}.{child_key}"
                if child_key in allowed_children:
                    flattened[dotted] = child_val
                else:
                    flattened[dotted] = child_val
        else:
            flattened[key] = val

    data["updates"] = flattened
    return data

