"""Deterministic question generator converting field paths into Egyptian Arabic questions.

This module converts a known required onboarding field into a single,
deterministic Egyptian Arabic question. It uses the ``QuestionSpec`` templates
from the question policy.

The generator does NOT decide which field to ask — the State Machine
determines ``next_field``. This module only converts a field path into
a natural-language question string.

Does NOT call the LLM, access the network, or persist any state.
"""

from typing import Any, Dict, Optional

from app.interview.question_policy import (
    QuestionSpec,
    get_question_spec,
)


class QuestionGenerator:
    """Converts a known required field into one deterministic Egyptian Arabic question.

    In this phase the generator uses only the deterministic template from the
    question policy. The ``context`` parameter is accepted but unused — it is
    reserved for future LLM-based phrasing while preserving the same field intent.
    """

    def generate(
        self,
        field: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a deterministic Egyptian Arabic question for *field*.

        Args:
            field: Dot-notation field path (e.g. ``personal.height_cm``).
            context: Optional profile context for future phrasing. Currently unused.

        Returns:
            A single-question Egyptian Arabic string targeting exactly *field*.

        Raises:
            UnknownQuestionFieldError: If *field* is not a known required field.
        """
        spec = get_question_spec(field)
        return spec.template
