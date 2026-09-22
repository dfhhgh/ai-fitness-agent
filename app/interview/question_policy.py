"""Deterministic policy mapping required onboarding fields to question specifications.

This module is the single source of truth for question metadata. It maps each
required onboarding field to a canonical intent, expected answer type, and
safe Egyptian Arabic template. The policy is immutable and read-only.

Does NOT call the LLM, generate natural language dynamically, or decide which
field to ask — it only provides the specification for a known field.
"""

from dataclasses import dataclass
from typing import Dict


class UnknownQuestionFieldError(ValueError):
    """Raised when a question is requested for an unsupported field path."""


@dataclass(frozen=True)
class QuestionSpec:
    """Immutable specification for generating a question about a single field.

    Attributes:
        field: Dot-notation field path (e.g. ``personal.height_cm``).
        intent: Short description of what the question asks.
        answer_type: Expected answer type (e.g. ``"int"``, ``"float"``,
            ``"string"``, ``"list[str]"``).
        template: Safe Egyptian Arabic question template.
    """

    field: str
    intent: str
    answer_type: str
    template: str


QUESTION_SPECS: Dict[str, QuestionSpec] = {
    "personal.gender": QuestionSpec(
        field="personal.gender",
        intent="ask gender",
        answer_type="string",
        template="ممكن أعرف حضرتك راجل ولا ست؟",
    ),
    "personal.age": QuestionSpec(
        field="personal.age",
        intent="ask age",
        answer_type="int",
        template="عندك كام سنة؟",
    ),
    "personal.height_cm": QuestionSpec(
        field="personal.height_cm",
        intent="ask height in centimeters",
        answer_type="float",
        template="طولك كام سم؟",
    ),
    "personal.weight_kg": QuestionSpec(
        field="personal.weight_kg",
        intent="ask current weight in kilograms",
        answer_type="float",
        template="وزنك كام كيلو؟",
    ),
    "health.injuries": QuestionSpec(
        field="health.injuries",
        intent="ask about injuries or health issues affecting training",
        answer_type="list[str]",
        template="عندك أي إصابات أو مشاكل صحية بتأثر على تمرينك؟",
    ),
    "training.experience": QuestionSpec(
        field="training.experience",
        intent="ask gym experience level",
        answer_type="string",
        template="بقالك قد إيه بتتمرن في الجيم؟",
    ),
    "training.days_per_week": QuestionSpec(
        field="training.days_per_week",
        intent="ask training frequency per week",
        answer_type="int",
        template="بتتمرن كام يوم في الأسبوع؟",
    ),
    "training.duration": QuestionSpec(
        field="training.duration",
        intent="ask how long the current regular training period has been",
        answer_type="string",
        template="بقالك قد إيه ملتزم بالتمرين بشكل منتظم؟",
    ),
    "training.activity_description": QuestionSpec(
        field="training.activity_description",
        intent="ask about daily activity level and job type",
        answer_type="string",
        template="طبيعة نشاطك اليومي إيه — شغلك مكتبي ولا بتتحرك كتير؟",
    ),
    "goal.type": QuestionSpec(
        field="goal.type",
        intent="ask primary fitness goal",
        answer_type="string",
        template="إيه هدفك الأساسي — تخس، تزيد وزن، تبني عضل، ولا تحافظ على وزنك؟",
    ),
}


def get_question_spec(field: str) -> QuestionSpec:
    """Return the QuestionSpec for a known required onboarding field.

    Args:
        field: Dot-notation field path (e.g. ``personal.height_cm``).

    Returns:
        The corresponding ``QuestionSpec``.

    Raises:
        UnknownQuestionFieldError: If *field* is not in ``QUESTION_SPECS``.
    """
    try:
        return QUESTION_SPECS[field]
    except KeyError:
        raise UnknownQuestionFieldError(
            f"No question spec for field: {field!r}. "
            f"Known fields: {sorted(QUESTION_SPECS.keys())}"
        )
