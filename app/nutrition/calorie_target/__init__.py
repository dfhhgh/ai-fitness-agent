"""Calorie Target Calculator — deterministic calorie target (calorie-v1).

This package provides the isolated calorie target calculation layer
for the Nutrition Core pipeline.

Responsibilities:
- Target Calories = TDEE + Goal Adjustment (integer arithmetic only)
- Fixed goal mapping: maintenance=0, weight_loss=-500, weight_gain=+500,
  muscle_gain=+500 (V1 operational baseline)
- Upstream TDEE status propagation (OK / INCOMPLETE / INVALID / ERROR)
- Domain validation (presence, positivity, finiteness of tdee_kcal)
- Post-calculation target validity (target <= 0 → ERROR,
  issue NEGATIVE_OR_ZERO_TARGET; evaluated before the low-calorie rule)
- Low-calorie Engineering Review Trigger (0 < target < 1200 →
  LOW_CALORIE_REVIEW_REQUIRED, no clamping)

Does NOT:
- Calculate or recalculate RMR
- Classify activity
- Calculate or recalculate TDEE
- Clamp or floor targets
- Apply percentage-based adjustments
- Calculate macronutrients
- Apply food or InBody logic
- Implement any high-calorie threshold
- Call LLM or external APIs
- Use system clock or random state
- Use Decimal arithmetic

Architecture:

    TDEEResult ─────┐
                    ├──► CalorieTargetInput
    GoalType ───────┘
                         │
                         ▼
                  CalorieTargetCalculator
                         │
                         ▼
                  CalorieTargetResult

Policy version: calorie-v1
"""

from app.nutrition.calorie_target.calculator import (
    CALORIE_TARGET_POLICY_VERSION,
    GOAL_ADJUSTMENTS,
    LOW_CALORIE_REVIEW_REQUIRED,
    LOW_CALORIE_THRESHOLD_KCAL,
    NEGATIVE_OR_ZERO_TARGET,
    calculate_calorie_target,
    get_goal_adjustment,
)
from app.nutrition.calorie_target.models import (
    CalorieTargetInput,
    CalorieTargetResult,
    CalorieTargetStatus,
    CalorieTargetTraceability,
)

__all__ = [
    "CALORIE_TARGET_POLICY_VERSION",
    "GOAL_ADJUSTMENTS",
    "LOW_CALORIE_REVIEW_REQUIRED",
    "LOW_CALORIE_THRESHOLD_KCAL",
    "NEGATIVE_OR_ZERO_TARGET",
    "CalorieTargetInput",
    "CalorieTargetResult",
    "CalorieTargetStatus",
    "CalorieTargetTraceability",
    "calculate_calorie_target",
    "get_goal_adjustment",
]
