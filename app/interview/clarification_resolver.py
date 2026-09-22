"""Deterministic clarification resolver converting user responses into resolved ProfilePatches.

This module interprets explicit user answers to clarification questions and produces
a deterministic ProfilePatch resolving exactly one Conflict.

The resolver never decides which value is correct on its own. It only resolves
when the user's response explicitly identifies the value to use.

Does NOT call the LLM, access the network, or mutate any objects.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.profile.conflicts import Conflict
from app.profile.models import ProfilePatch
from app.profile.policies import CONTRADICTION_SENSITIVE_FIELDS
from app.profile.validator import ProfileValidationError, validate_profile_patch


# --- Unresolved reasons ---

REASON_AMBIGUOUS = "ambiguous_answer"
REASON_NO_CANDIDATE = "no_candidate_value"
REASON_UNRELATED = "unrelated_answer"
REASON_UNSUPPORTED = "unsupported_value"
REASON_INVALID = "invalid_value"


@dataclass(frozen=True)
class ClarificationResolution:
    """Immutable result of a clarification resolution attempt.

    Attributes:
        resolved: Whether the conflict was resolved.
        patch: A ProfilePatch with exactly one update, or None if unresolved.
        reason: A deterministic reason code if unresolved, or None if resolved.
    """

    resolved: bool
    patch: Optional[ProfilePatch]
    reason: Optional[str]


# --- Numeric fields requiring semantic number extraction ---

_NUMERIC_FIELDS = frozenset({
    "personal.age",
    "personal.height_cm",
    "goal.target_weight_kg",
    "goal.weight_change_target_kg",
    "training.days_per_week",
})

# --- Gender text options ---

_GENDER_OPTIONS = {
    "راجل": "راجل",
    "رجل": "راجل",
    "أنثى": "ست",
    "بنت": "ست",
    "ست": "ست",
}

# --- Experience text options ---

_EXPERIENCE_OPTIONS = {
    "مبتدئ": "مبتدئ",
    "مبتدئة": "مبتدئ",
    "متوسط": "متوسط",
    "متقدم": "متقدم",
}

# --- Goal type variants ---

_GOAL_TYPE_VARIANTS = {
    "خسارة الوزن": "weight_loss",
    "خسارة": "weight_loss",
    "أخس": "weight_loss",
    "عايز أخس": "weight_loss",
    "عايز اخس": "weight_loss",
    "أنا عايز أخس": "weight_loss",
    "زيادة الوزن": "weight_gain",
    "زيادة": "weight_gain",
    "أزيد وزن": "weight_gain",
    "عايز أزيد": "weight_gain",
    "عايز ازيد": "weight_gain",
    "أنا عايز أزيد": "weight_gain",
    "بناء العضلات": "muscle_gain",
    "بناء": "muscle_gain",
    "أبني عضل": "muscle_gain",
    "عايز أبني عضل": "muscle_gain",
    "عايز ابني عضل": "muscle_gain",
    "أنا عايز أبني عضل": "muscle_gain",
    "الحفاظ على الوزن": "maintenance",
    "المحافظة على الوزن": "maintenance",
    "أثبت وزني": "maintenance",
    "ثبات": "maintenance",
}

# --- Existing value reference phrases ---

_EXISTING_PHRASES = (
    "القديم",
    "القديمة",
    "الأول",
    "الاول",
    "المسجل",
    "اللي عندك",
    "اللي كان مكتوب",
)

# --- Incoming value reference phrases ---

_INCOMING_PHRASES = (
    "الجديد",
    "الجديدة",
    "التاني",
    "الثاني",
    "اللي قولته دلوقتي",
    "آخر حاجة قلتها",
    "اخر حاجة قلتها",
)


class ClarificationResolver:
    """Deterministic resolver converting user responses into ProfilePatches.

    The resolver only resolves when the user's response explicitly identifies
    the value to use. It never guesses or infers values on its own.
    """

    def resolve(
        self,
        conflict: Conflict,
        user_message: str,
    ) -> ClarificationResolution:
        """Resolve a conflict based on an explicit user response.

        Args:
            conflict: The ``Conflict`` to resolve.
            user_message: The user's raw text response.

        Returns:
            A ``ClarificationResolution`` indicating success or failure.
        """
        if conflict.path not in CONTRADICTION_SENSITIVE_FIELDS:
            return ClarificationResolution(
                resolved=False, patch=None, reason=REASON_UNSUPPORTED
            )

        message = user_message.strip()
        if not message:
            return ClarificationResolution(
                resolved=False, patch=None, reason=REASON_NO_CANDIDATE
            )

        normalized = _normalize(message)

        # Check existing/incoming reference phrases
        has_existing = _references_existing(normalized)
        has_incoming = _references_incoming(normalized)

        if has_existing and has_incoming:
            return ClarificationResolution(
                resolved=False, patch=None, reason=REASON_AMBIGUOUS
            )
        if has_existing:
            return ClarificationResolution(
                resolved=True,
                patch=_make_patch(conflict.path, conflict.existing_value),
                reason=None,
            )
        if has_incoming:
            return ClarificationResolution(
                resolved=True,
                patch=_make_patch(conflict.path, conflict.incoming_value),
                reason=None,
            )

        # Extract explicit value based on field type
        value = _extract_value(conflict.path, normalized, message)

        if value is not None:
            # Validate via existing validator
            patch = _make_patch(conflict.path, value)
            try:
                validate_profile_patch(patch)
            except ProfileValidationError:
                return ClarificationResolution(
                    resolved=False, patch=None, reason=REASON_INVALID
                )
            return ClarificationResolution(
                resolved=True, patch=patch, reason=None
            )

        return ClarificationResolution(
            resolved=False, patch=None, reason=REASON_NO_CANDIDATE
        )


def _normalize(text: str) -> str:
    """Normalize text for deterministic parsing."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _references_existing(message: str) -> bool:
    """Check if message explicitly references the existing value."""
    for phrase in _EXISTING_PHRASES:
        if phrase in message:
            return True
    return False


def _references_incoming(message: str) -> bool:
    """Check if message explicitly references the incoming value."""
    for phrase in _INCOMING_PHRASES:
        if phrase in message:
            return True
    return False


def _extract_value(path: str, normalized: str, original: str) -> Optional[object]:
    """Extract an explicit value from the user message for the given field."""
    if path in _NUMERIC_FIELDS:
        return _extract_numeric_value(path, normalized)
    if path == "personal.gender":
        return _extract_gender(normalized)
    if path == "training.experience":
        return _extract_experience(normalized)
    if path == "goal.type":
        return _extract_goal_type(normalized)
    if path in ("training.duration", "training.activity_description"):
        return None
    return None


def _extract_numeric_value(path: str, message: str) -> Optional[object]:
    """Extract a numeric value with field-specific semantic context."""
    if path == "personal.age":
        return _extract_age(message)
    if path == "training.days_per_week":
        return _extract_days(message)
    if path == "personal.height_cm":
        return _extract_number_near(message, ("طول", "سم", "height"))
    if path == "goal.target_weight_kg":
        return _extract_number_near(message, ("وزن", "كيلو", "مستهدف"))
    if path == "goal.weight_change_target_kg":
        return _extract_number_near(message, ("تغيير", "كيلو", "فرق"))
    return None


def _extract_age(message: str) -> Optional[int]:
    """Extract age from message with semantic field boundary protection."""
    # Priority 1: number near age-specific keywords
    match = re.search(r"(-?\d+)\s*سنه|سنه\s*(-?\d+)|(-?\d+)\s*سنة|سنة\s*(-?\d+)", message)
    if match:
        val = match.group(1) or match.group(2) or match.group(3) or match.group(4)
        return int(val)

    match = re.search(r"عمري\s*(-?\d+)|(-?\d+)\s*عمري", message)
    if match:
        val = match.group(1) or match.group(2)
        return int(val)

    # Reject if message contains keywords from other numeric fields
    _OTHER_FIELD_KEYWORDS = ("أيام", "يوم", "أسبوع", "تمرن", "تمرين", "طول", "سم", "كيلو", "وزن", "مستهدف", "تغيير", "فرق")
    if any(kw in message for kw in _OTHER_FIELD_KEYWORDS):
        return None

    # Reject if message contains hedging language
    _HEDGE_WORDS = ("تقريبًا", "تقريبا", "يمكن", " يمكن")
    if any(hw in message for hw in _HEDGE_WORDS):
        return None

    # Priority 2: bare number ONLY if it's the only number in the message
    numbers = re.findall(r"-?\d+", message)
    if len(numbers) == 1:
        return int(numbers[0])

    return None


def _extract_days(message: str) -> Optional[int]:
    """Extract days-per-week from message with semantic field boundary protection."""
    # Priority 1: number near day-specific keywords
    match = re.search(r"(\d+)\s*أيام|أيام\s*(\d+)|(\d+)\s*يوم|يوم\s*(\d+)", message)
    if match:
        return int(match.group(1) or match.group(2) or match.group(3) or match.group(4))

    match = re.search(r"(\d+)\s*أسبوع|أسبوع\s*(\d+)", message)
    if match:
        return int(match.group(1) or match.group(2))

    # Reject if message contains keywords from other numeric fields
    _OTHER_FIELD_KEYWORDS = ("سنة", "سنه", "عمري", "طول", "سم", "كيلو", "وزن", "مستهدف", "تغيير", "فرق")
    if any(kw in message for kw in _OTHER_FIELD_KEYWORDS):
        return None

    # Reject if message contains hedging language
    _HEDGE_WORDS = ("تقريبًا", "تقريبا", "يمكن", " يمكن")
    if any(hw in message for hw in _HEDGE_WORDS):
        return None

    # Priority 2: bare number ONLY if it's the only number in the message
    numbers = re.findall(r"\d+", message)
    if len(numbers) == 1:
        return int(numbers[0])

    return None


def _extract_number_near(message: str, keywords: tuple) -> Optional[float]:
    """Extract a number from message with semantic field boundary protection."""
    # Priority 1: number near semantic keywords
    for keyword in keywords:
        match = re.search(re.escape(keyword) + r"\s*(-?\d+(?:\.\d+)?)", message)
        if match:
            return float(match.group(1))
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*" + re.escape(keyword), message)
        if match:
            return float(match.group(1))

    # Reject if message contains keywords from other numeric fields
    _OTHER_FIELD_KEYWORDS = ("سنة", "سنه", "عمري", "أيام", "يوم", "أسبوع", "تمرن", "تمرين", "تغيير", "فرق")
    if any(kw in message for kw in _OTHER_FIELD_KEYWORDS):
        return None

    # Reject if message contains hedging language
    _HEDGE_WORDS = ("تقريبًا", "تقريبا", "يمكن")
    if any(hw in message for hw in _HEDGE_WORDS):
        return None

    # Priority 2: bare number ONLY if it's the only number in the message
    numbers = re.findall(r"-?\d+(?:\.\d+)?", message)
    if len(numbers) == 1:
        return float(numbers[0])

    return None


def _extract_gender(message: str) -> Optional[str]:
    """Extract gender value from message."""
    for option, value in _GENDER_OPTIONS.items():
        if option in message:
            return value
    return None


def _extract_experience(message: str) -> Optional[str]:
    """Extract experience value from message."""
    for option, value in _EXPERIENCE_OPTIONS.items():
        if option in message:
            return value
    return None


def _extract_goal_type(message: str) -> Optional[str]:
    """Extract goal type value from message."""
    for variant, value in _GOAL_TYPE_VARIANTS.items():
        if variant in message:
            return value
    return None


def _make_patch(path: str, value: object) -> ProfilePatch:
    """Create a ProfilePatch with exactly one update."""
    return ProfilePatch(
        updates={path: value},
        unknown_fields=[],
        conflicts=[],
    )
