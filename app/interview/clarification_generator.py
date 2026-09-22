"""Deterministic clarification generator converting Conflict objects into user-facing questions.

This module converts a deterministic Conflict into a single, safe Egyptian Arabic
clarification question. It does NOT call the LLM, access the network, or resolve
the conflict — it is purely a presentation layer.

The Conflict is never mutated.
"""

from typing import Any, Union

from app.interview.clarification_policy import (
    GOAL_TYPE_LABELS,
    ClarificationSpec,
    get_clarification_spec,
)
from app.profile.conflicts import Conflict


def _format_value(field: str, value: Any) -> str:
    """Format a raw value into a clean user-facing string.

    - goal.type internal values are converted to Arabic labels.
    - Numeric values lose unnecessary trailing ``.0``.
    - None is shown as a literal string (should not happen in practice).
    """
    if value is None:
        return "غير محدد"

    if field == "goal.type" and isinstance(value, str):
        return GOAL_TYPE_LABELS.get(value, value)

    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)

    return str(value)


class ClarificationGenerator:
    """Converts a Conflict into a deterministic Egyptian Arabic clarification question.

    The generator uses the ClarificationSpec template from the clarification policy.
    The Conflict object is never mutated.
    """

    def generate(self, conflict: Conflict) -> str:
        """Generate a deterministic Egyptian Arabic clarification question for *conflict*.

        Args:
            conflict: A ``Conflict`` with a known contradiction-sensitive path.

        Returns:
            A single-question Egyptian Arabic string presenting both values and
            asking the user to choose.

        Raises:
            UnknownClarificationFieldError: If *conflict.path* has no clarification spec.
        """
        spec = get_clarification_spec(conflict.path)
        formatted_existing = _format_value(conflict.path, conflict.existing_value)
        formatted_incoming = _format_value(conflict.path, conflict.incoming_value)
        return spec.template.format(
            existing_value=formatted_existing,
            incoming_value=formatted_incoming,
        )
