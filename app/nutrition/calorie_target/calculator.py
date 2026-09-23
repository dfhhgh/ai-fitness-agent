"""Deterministic Calorie Target calculator — calorie-v1.

This module implements the calorie target calculation using fixed
integer arithmetic only.

Policy version: calorie-v1

Formula:
    Target Calories = TDEE + Goal Adjustment

Goal mapping (V1 operational baseline):
    maintenance → 0
    weight_loss → -500
    weight_gain → +500
    muscle_gain → +500

Low-calorie Engineering Review Trigger:
    0 < target < 1200 → append LOW_CALORIE_REVIEW_REQUIRED (no clamping)

Post-calculation target validity (calorie-v1 Rev1.2):
    target <= 0 → status = ERROR, target = None,
                  issue = NEGATIVE_OR_ZERO_TARGET
    Evaluated AFTER target = TDEE + adjustment and BEFORE the
    low-calorie review rule. No calorie floor is introduced.

This module is deterministic and side-effect free:
- No LLM calls
- No database access
- No external APIs
- No system clock
- No random state
- No Decimal arithmetic
- No floating-point target arithmetic
- No RMR / activity / TDEE recalculation
- No macro or food logic
- No InBody logic
- No percentage-based adjustments
- No high-calorie threshold of any kind
- No hidden 1200 kcal floor
"""

import math

from app.nutrition.calorie_target.models import (
    CalorieTargetInput,
    CalorieTargetResult,
    CalorieTargetStatus,
    CalorieTargetTraceability,
)
from app.nutrition.models import GoalType
from app.nutrition.tdee.tdee_models import TDEEResult, TDEEStatus

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

CALORIE_TARGET_POLICY_VERSION: str = "calorie-v1"

LOW_CALORIE_REVIEW_REQUIRED: str = "LOW_CALORIE_REVIEW_REQUIRED"
LOW_CALORIE_THRESHOLD_KCAL: int = 1200

NEGATIVE_OR_ZERO_TARGET: str = "NEGATIVE_OR_ZERO_TARGET"

# V1 operational baseline adjustments (integer kcal).
GOAL_ADJUSTMENTS: dict[GoalType, int] = {
    GoalType.MAINTENANCE: 0,
    GoalType.WEIGHT_LOSS: -500,
    GoalType.WEIGHT_GAIN: 500,
    GoalType.MUSCLE_GAIN: 500,
}


def get_goal_adjustment(goal_type: GoalType) -> int:
    """Return the fixed integer calorie adjustment for a goal type."""
    return GOAL_ADJUSTMENTS[goal_type]


def _map_tdee_status(tdee_status: TDEEStatus) -> CalorieTargetStatus:
    """Map TDEEStatus to CalorieTargetStatus.

    Both enums share the same four-tier values (OK, INCOMPLETE,
    INVALID, ERROR), so the mapping is direct by value.
    """
    return CalorieTargetStatus(tdee_status.value)


def _is_non_finite(value: object) -> bool:
    """Check if a numeric value is NaN, +Infinity, or -Infinity."""
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    return False


def _build_traceability(correlation_id: str | None) -> CalorieTargetTraceability:
    """Build deterministic traceability (no timestamps)."""
    return CalorieTargetTraceability(
        correlation_id=correlation_id,
        formula_expression="Target Calories = TDEE + Goal Adjustment",
        arithmetic_mode="integer",
        policy_version=CALORIE_TARGET_POLICY_VERSION,
    )


def _failure_result(
    status: CalorieTargetStatus,
    issues: list[str],
    goal_type: GoalType,
    adjustment: int,
    correlation_id: str | None,
) -> CalorieTargetResult:
    """Build a non-OK result with calculation fields nulled."""
    return CalorieTargetResult(
        status=status,
        issues=issues,
        safety_flags=[],
        target_calories_kcal=None,
        tdee_kcal_used=None,
        goal_type_used=goal_type,
        calorie_adjustment_kcal=adjustment,
        policy_version=CALORIE_TARGET_POLICY_VERSION,
        traceability=_build_traceability(correlation_id),
    )


def calculate_calorie_target(input_data: CalorieTargetInput) -> CalorieTargetResult:
    """Calculate the daily calorie target from validated CalorieTargetInput.

    Execution order:
        1. Check upstream TDEE status → short-circuit if non-OK
        2. Domain validation → tdee_kcal presence, positivity, finiteness
        3. Integer addition → target = tdee + adjustment
        4. Post-calculation target validity → target <= 0 → ERROR
        5. Low-calorie Engineering Review Trigger → safety flag (no clamp)
        6. Return CalorieTargetResult with traceability

    Args:
        input_data: Validated CalorieTargetInput with TDEEResult and GoalType.

    Returns:
        CalorieTargetResult with status, target, and traceability.
    """
    tdee_result = input_data.tdee_result
    goal_type = input_data.goal_type
    correlation_id = input_data.correlation_id
    adjustment = get_goal_adjustment(goal_type)

    # Step 1: Upstream TDEE status propagation
    if tdee_result.status != TDEEStatus.OK:
        issues = ["UPSTREAM_TDEE_NOT_OK"]
        for issue in tdee_result.issues:
            if issue not in issues:
                issues.append(issue)
        return _failure_result(
            _map_tdee_status(tdee_result.status),
            issues,
            goal_type,
            adjustment,
            correlation_id,
        )

    # Step 2: Domain validation — TDEE status is OK
    tdee_kcal = tdee_result.tdee_kcal
    if tdee_kcal is None:
        return _failure_result(
            CalorieTargetStatus.ERROR,
            ["MISSING_TDEE_VALUE"],
            goal_type,
            adjustment,
            correlation_id,
        )
    if _is_non_finite(tdee_kcal):
        return _failure_result(
            CalorieTargetStatus.ERROR,
            ["NON_FINITE_INPUT"],
            goal_type,
            adjustment,
            correlation_id,
        )
    if tdee_kcal <= 0:
        return _failure_result(
            CalorieTargetStatus.ERROR,
            ["TDEE_VALUE_NON_POSITIVE"],
            goal_type,
            adjustment,
            correlation_id,
        )

    # Step 3: Integer arithmetic — target = tdee + adjustment
    target = tdee_kcal + adjustment

    # Step 4: Post-calculation target validity (calorie-v1 Rev1.2).
    # Evaluated BEFORE the low-calorie review rule.
    if target <= 0:
        return _failure_result(
            CalorieTargetStatus.ERROR,
            [NEGATIVE_OR_ZERO_TARGET],
            goal_type,
            adjustment,
            correlation_id,
        )

    # Step 5: Low-calorie Engineering Review Trigger (no clamping)
    safety_flags: list[str] = []
    if target < LOW_CALORIE_THRESHOLD_KCAL:
        safety_flags.append(LOW_CALORIE_REVIEW_REQUIRED)

    # Step 6: Success result
    return CalorieTargetResult(
        status=CalorieTargetStatus.OK,
        issues=[],
        safety_flags=safety_flags,
        target_calories_kcal=target,
        tdee_kcal_used=tdee_kcal,
        goal_type_used=goal_type,
        calorie_adjustment_kcal=adjustment,
        policy_version=CALORIE_TARGET_POLICY_VERSION,
        traceability=_build_traceability(correlation_id),
    )
