"""Deterministic clarification policy mapping contradiction-sensitive fields to clarification specifications.

This module is the single source of truth for clarification metadata. It maps each
contradiction-sensitive field to a canonical intent and safe Egyptian Arabic template
for resolving conflicts between existing and incoming values.

Does NOT call the LLM, generate natural language dynamically, or resolve conflicts.
"""

from dataclasses import dataclass
from typing import Dict


class UnknownClarificationFieldError(ValueError):
    """Raised when a clarification is requested for a field with no spec."""


# Deterministic human-readable mapping for goal.type internal values
GOAL_TYPE_LABELS: Dict[str, str] = {
    "weight_loss": "خسارة الوزن",
    "weight_gain": "زيد الوزن",
    "muscle_gain": "بناء العضلات",
    "maintenance": "الحفاظ على الوزن",
}


@dataclass(frozen=True)
class ClarificationSpec:
    """Immutable specification for generating a clarification question about a single field.

    Attributes:
        field: Dot-notation field path (e.g. ``personal.age``).
        intent: Short description of what the clarification resolves.
        template: Safe Egyptian Arabic template with {existing_value} and {incoming_value}.
    """

    field: str
    intent: str
    template: str


CLARIFICATION_SPECS: Dict[str, ClarificationSpec] = {
    "personal.age": ClarificationSpec(
        field="personal.age",
        intent="Resolve conflicting age information.",
        template=(
            "تمام، عندي مسجل إن سنك {existing_value} سنة، وإنت دلوقتي بتقول "
            "{incoming_value} سنة. تحب نعتمد أنهي سن؟"
        ),
    ),
    "personal.gender": ClarificationSpec(
        field="personal.gender",
        intent="Resolve conflicting gender information.",
        template=(
            "تمام، عندي مسجل إنك {existing_value}، وإنت دلوقتي بتقول "
            "{incoming_value}. أنهي معلومة الصح؟"
        ),
    ),
    "personal.height_cm": ClarificationSpec(
        field="personal.height_cm",
        intent="Resolve conflicting height information.",
        template=(
            "تمام، عندي مسجل إن طولك {existing_value} سم، وإنت دلوقتي بتقول "
            "{incoming_value} سم. نعتمد أنهي طول؟"
        ),
    ),
    "goal.type": ClarificationSpec(
        field="goal.type",
        intent="Resolve conflicting fitness goal type.",
        template=(
            "تمام، عندي مسجل إن هدفك {existing_value}، وإنت دلوقتي بتقول "
            "{incoming_value}. أنهي هدف هو الصح؟"
        ),
    ),
    "goal.target_weight_kg": ClarificationSpec(
        field="goal.target_weight_kg",
        intent="Resolve conflicting target weight.",
        template=(
            "تمام، عندي مسجل إن وزنك المستهدف {existing_value} كيلو، وإنت دلوقتي بتقول "
            "{incoming_value} كيلو. نعتمد أنهي وزن مستهدف؟"
        ),
    ),
    "goal.weight_change_target_kg": ClarificationSpec(
        field="goal.weight_change_target_kg",
        intent="Resolve conflicting weight change target.",
        template=(
            "تمام، عندي مسجل إن التغيير المطلوب في الوزن {existing_value} كيلو، وإنت "
            "دلوقتي بتقول {incoming_value} كيلو. نعتمد أنهي تغيير مطلوب؟"
        ),
    ),
    "training.days_per_week": ClarificationSpec(
        field="training.days_per_week",
        intent="Resolve conflicting training frequency.",
        template=(
            "تمام، عندي مسجل إنك بتتمرن {existing_value} أيام في الأسبوع، وإنت دلوقتي بتقول "
            "{incoming_value} أيام. نعتمد أنهي عدد؟"
        ),
    ),
    "training.duration": ClarificationSpec(
        field="training.duration",
        intent="Resolve conflicting training duration.",
        template=(
            "تمام، عندي مسجل إنك ملتزم بالتمرين لمدة {existing_value}، وإنت دلوقتي بتقول "
            "{incoming_value}. نعتمد أنهي مدة؟"
        ),
    ),
    "training.experience": ClarificationSpec(
        field="training.experience",
        intent="Resolve conflicting experience level.",
        template=(
            "تمام، عندي مسجل إن مستوى خبرتك {existing_value}، وإنت دلوقتي بتقول "
            "{incoming_value}. نعتمد أنهي مستوى؟"
        ),
    ),
    "training.activity_description": ClarificationSpec(
        field="training.activity_description",
        intent="Resolve conflicting daily activity description.",
        template=(
            "تمام، عندي مسجل إن نشاطك اليومي {existing_value}، وإنت دلوقتي بتقول "
            "{incoming_value}. أنهي وصف أدق لنشاطك اليومي؟"
        ),
    ),
}


def get_clarification_spec(field: str) -> ClarificationSpec:
    """Return the ClarificationSpec for a known contradiction-sensitive field.

    Args:
        field: Dot-notation field path (e.g. ``personal.age``).

    Returns:
        The corresponding ``ClarificationSpec``.

    Raises:
        UnknownClarificationFieldError: If *field* is not in ``CLARIFICATION_SPECS``.
    """
    try:
        return CLARIFICATION_SPECS[field]
    except KeyError:
        raise UnknownClarificationFieldError(
            f"No clarification spec for field: {field!r}. "
            f"Known fields: {sorted(CLARIFICATION_SPECS.keys())}"
        )
