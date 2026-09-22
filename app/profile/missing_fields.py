"""Deterministic resolver determining which required onboarding fields are missing from a ClientProfile.

This module inspects stored profile state only. It does NOT call the LLM,
ask questions, generate natural language, resolve conflicts, or modify the profile.

The only responsibility is: given a ClientProfile, return the ordered list of
required onboarding field paths whose values are still absent.
"""

from typing import List

from app.profile.models import ClientProfile

# Authoritative ordered list of required onboarding fields.
# The order defines the interview sequence used by the future State Machine.
REQUIRED_ONBOARDING_FIELDS: List[str] = [
    "personal.gender",
    "personal.age",
    "personal.height_cm",
    "personal.weight_kg",
    "health.injuries",
    "training.experience",
    "training.days_per_week",
    "training.duration",
    "training.activity_description",
    "goal.type",
]


def _get_nested_value(obj: object, path: str) -> object:
    """Retrieve a value from a nested object using a dot-notation path."""
    parts = path.split(".")
    current = obj
    for part in parts:
        current = getattr(current, part, None)
        if current is None and part != parts[-1]:
            return None
    return current


def _is_empty_string(value: object) -> bool:
    """Return True if value is a string that is empty or whitespace-only."""
    return isinstance(value, str) and value.strip() == ""


def _is_field_present(value: object) -> bool:
    """Return True if the field value is considered present (not missing).

    Semantics:
    - None  => missing
    - "" or "   " => missing (empty/whitespace string)
    - []    => present (explicitly provided, e.g. injuries = [] means no injuries)
    - everything else => present
    """
    if value is None:
        return False
    if _is_empty_string(value):
        return False
    return True


def get_missing_fields(profile: ClientProfile) -> List[str]:
    """Return the ordered list of required onboarding fields still missing from the profile.

    Each required field is checked against the profile. A scalar field is missing
    when its value is None or an empty/whitespace-only string. List fields (like
    health.injuries) are missing only when their value is None; an empty list []
    means the user explicitly reported nothing and is considered present.

    The returned list preserves the deterministic order defined in
    REQUIRED_ONBOARDING_FIELDS.

    Args:
        profile: The current ClientProfile to inspect.

    Returns:
        An ordered list of dot-notation field paths that are still missing.
        An empty list means all required onboarding fields are present.
    """
    missing: List[str] = []
    for field_path in REQUIRED_ONBOARDING_FIELDS:
        value = _get_nested_value(profile, field_path)
        if not _is_field_present(value):
            missing.append(field_path)
    return missing


def is_profile_complete(profile: ClientProfile) -> bool:
    """Return True if all required onboarding fields are present.

    This is a convenience wrapper over get_missing_fields().
    """
    return len(get_missing_fields(profile)) == 0
