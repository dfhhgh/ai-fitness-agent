"""Deterministic activity policy — factors, baselines, and versioning.

This module is the single source of truth for:
- Activity factor values per category
- Occupation baseline scores
- Exercise intensity weights
- WES upgrade thresholds
- Policy version string
- Factor lookup API

The activity factors and scoring weights are engineering policy values
for this system. They are NOT universal physiological truths.

Policy source: Nutrition Core V1 specification — Revision 3.
"""

from app.nutrition.models import (
    ActivityCategory,
    DailyMovement,
    ExerciseIntensity,
    OccupationalActivity,
)

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

# ---------------------------------------------------------------------------
# Occupation baseline scores
# ---------------------------------------------------------------------------

# Baseline score per occupational activity level (0–3).
# Source: Revision 3 policy.
OCCUPATION_BASELINES: dict[OccupationalActivity, int] = {
    OccupationalActivity.SEDENTARY: 0,
    OccupationalActivity.LIGHT_MANUAL: 1,
    OccupationalActivity.ACTIVE_MANUAL: 2,
    OccupationalActivity.HEAVY_MANUAL: 3,
}

# ---------------------------------------------------------------------------
# Exercise intensity weights
# ---------------------------------------------------------------------------

# Intensity weight for WES calculation.
# WES = training_days × duration_minutes × intensity_weight
# Source: Revision 3 policy.
INTENSITY_WEIGHTS: dict[ExerciseIntensity, int] = {
    ExerciseIntensity.NONE: 0,
    ExerciseIntensity.LIGHT: 2,
    ExerciseIntensity.MODERATE: 4,
    ExerciseIntensity.VIGOROUS: 7,
}

# ---------------------------------------------------------------------------
# WES upgrade thresholds
# ---------------------------------------------------------------------------

# WES upgrade score thresholds (ascending order).
# Each tuple: (threshold, upgrade_score).
# If WES < threshold, return upgrade_score.
# Source: Revision 3 policy.
WES_UPGRADE_THRESHOLDS: list[tuple[float, int]] = [
    (600.0, 0),    # WES < 600 → upgrade 0
    (1800.0, 1),   # 600 ≤ WES < 1800 → upgrade 1
    (float("inf"), 2),  # WES ≥ 1800 → upgrade 2
]

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


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
