"""Deterministic activity policy — factors and versioning.

This module is the single source of truth for:
- Activity factor values per category
- Policy version string
- Factor lookup API

The activity factors are engineering policy values for this system.
They are NOT universal physiological truths.

Policy source: Nutrition Core V1 specification.
"""

from app.nutrition.models import ActivityCategory

# ---------------------------------------------------------------------------
# Policy version
# ---------------------------------------------------------------------------

ACTIVITY_POLICY_VERSION: str = "activity-v1"

# ---------------------------------------------------------------------------
# Activity factors (authoritative)
# ---------------------------------------------------------------------------

# Activity factor per category.
# Source: Nutrition Core V1 specification.
# These values are exact and must NOT be modified without a new policy version.
ACTIVITY_FACTORS: dict[ActivityCategory, float] = {
    ActivityCategory.SEDENTARY: 1.20,
    ActivityCategory.LIGHT: 1.35,
    ActivityCategory.MODERATE: 1.55,
    ActivityCategory.HIGH: 1.75,
}


def get_activity_factor(category: ActivityCategory) -> float:
    """Return the deterministic activity factor for a given category.

    This is the single source of truth for activity factor lookup.
    The TDEE calculator MUST use this function — not inline literals.

    Args:
        category: A normalized ActivityCategory value.

    Returns:
        The activity factor (float) for the given category.

    Raises:
        KeyError: If the category is not in ACTIVITY_FACTORS.
            Unknown categories must fail explicitly — never silently
            default to sedentary.
    """
    try:
        return ACTIVITY_FACTORS[category]
    except KeyError:
        raise KeyError(
            f"No activity factor defined for category: {category!r}. "
            f"Valid categories: {sorted(c.value for c in ACTIVITY_FACTORS)}"
        )
