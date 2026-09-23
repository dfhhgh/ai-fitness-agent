"""Deterministic TDEE calculator — tdee-v1.

This module implements the TDEE calculation using fixed-point
decimal arithmetic with ROUND_HALF_UP rounding.

Policy version: tdee-v1

Formula:
    TDEE = RMR × ActivityFactor

This module is deterministic and side-effect free:
- No LLM calls
- No database access
- No external APIs
- No system clock
- No random state
- No RMR recalculation
- No activity reclassification
- No calorie deficit/surplus adjustments
"""

import math
from decimal import Decimal, ROUND_HALF_UP

from app.nutrition.activity.activity_models import (
    ActivityClassificationResult,
    ActivityClassificationStatus,
)
from app.nutrition.tdee.tdee_models import (
    TDEEInput,
    TDEEResult,
    TDEEStatus,
    TDEETraceability,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

TDEE_POLICY_VERSION: str = "tdee-v1"

# Status precedence: ERROR > INVALID > INCOMPLETE
_STATUS_PRECEDENCE: dict[TDEEStatus, int] = {
    TDEEStatus.OK: 0,
    TDEEStatus.INCOMPLETE: 1,
    TDEEStatus.INVALID: 2,
    TDEEStatus.ERROR: 3,
}


def _map_activity_status(
    activity_status: ActivityClassificationStatus,
) -> TDEEStatus:
    """Map ActivityClassificationStatus to TDEEStatus.

    Activity uses CONFLICT where TDEE uses INVALID.
    All other status values map directly.
    """
    if activity_status == ActivityClassificationStatus.OK:
        return TDEEStatus.OK
    if activity_status == ActivityClassificationStatus.CONFLICT:
        return TDEEStatus.INVALID
    if activity_status == ActivityClassificationStatus.INCOMPLETE:
        return TDEEStatus.INCOMPLETE
    if activity_status == ActivityClassificationStatus.ERROR:
        return TDEEStatus.ERROR
    # Unknown status — treat as ERROR
    return TDEEStatus.ERROR


def _resolve_status(
    rmr_status: TDEEStatus,
    activity_status: TDEEStatus,
) -> TDEEStatus:
    """Resolve combined status using precedence: ERROR > INVALID > INCOMPLETE.

    If either is OK and the other is OK → OK.
    Otherwise, return the higher-severity status.
    """
    if rmr_status == TDEEStatus.OK and activity_status == TDEEStatus.OK:
        return TDEEStatus.OK
    return (
        rmr_status
        if _STATUS_PRECEDENCE[rmr_status] >= _STATUS_PRECEDENCE[activity_status]
        else activity_status
    )


def _is_non_finite(value: int | float) -> bool:
    """Check if a numeric value is NaN, +Infinity, or -Infinity."""
    return math.isnan(value) or math.isinf(value)


def calculate_tdee(input_data: TDEEInput) -> TDEEResult:
    """Calculate TDEE from validated TDEEInput.

    Execution order:
        1. Check upstream statuses → short-circuit if non-OK
        2. Domain validation → check field presence and numeric safety
        3. Decimal conversion → string boundary for float precision
        4. Multiply → raw TDEE
        5. Round → ROUND_HALF_UP to integer
        6. Return TDEEResult with traceability

    Args:
        input_data: Validated TDEEInput with both upstream results.

    Returns:
        TDEEResult with status, tdee_kcal, and traceability.
    """
    rmr = input_data.rmr_result
    activity = input_data.activity_result

    # Step 1: Map and resolve upstream statuses
    # RMRStatus values (OK, INCOMPLETE, INVALID, ERROR) map directly to TDEEStatus.
    # ActivityClassificationStatus uses CONFLICT instead of INVALID, so requires mapping.
    rmr_tdee_status = TDEEStatus(rmr.status.value)
    act_tdee_status = _map_activity_status(activity.status)

    resolved_status = _resolve_status(rmr_tdee_status, act_tdee_status)

    if resolved_status != TDEEStatus.OK:
        issues = _aggregate_issues(rmr, activity, rmr_tdee_status, act_tdee_status)
        return TDEEResult(
            status=resolved_status,
            issues=issues,
            policy_version=TDEE_POLICY_VERSION,
        )

    # Step 2: Domain validation — both upstream are OK
    domain_issues = _validate_domain(rmr, activity)
    if domain_issues:
        # Determine status from domain issues
        domain_status = _resolve_domain_status(domain_issues)
        return TDEEResult(
            status=domain_status,
            issues=domain_issues,
            policy_version=TDEE_POLICY_VERSION,
        )

    # Step 3: Decimal conversion via string boundary
    rmr_dec = Decimal(rmr.rmr_kcal)
    factor_dec = Decimal(str(activity.activity_factor))

    # Step 4: Multiply
    raw_tdee = rmr_dec * factor_dec

    # Step 5: Round with ROUND_HALF_UP
    final_tdee = int(raw_tdee.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    # Step 6: Build traceability
    traceability = TDEETraceability(
        rmr_kcal_used=rmr.rmr_kcal,
        activity_factor_used=str(factor_dec),
        raw_tdee_unrounded=str(raw_tdee),
        formula_expression="TDEE = RMR * ActivityFactor",
        rounding_mode="ROUND_HALF_UP",
        policy_version=TDEE_POLICY_VERSION,
    )

    return TDEEResult(
        status=TDEEStatus.OK,
        issues=[],
        tdee_kcal=final_tdee,
        rmr_kcal_used=rmr.rmr_kcal,
        activity_factor_used=factor_dec,
        activity_category_used=activity.activity_category,
        policy_version=TDEE_POLICY_VERSION,
        traceability=traceability,
    )


def _aggregate_issues(
    rmr: "RMRResult",
    activity: "ActivityClassificationResult",
    rmr_status: TDEEStatus,
    act_status: TDEEStatus,
) -> list[str]:
    """Aggregate issue codes from non-OK upstream results.

    Preserves insertion order, removes duplicates.
    """
    issues: list[str] = []

    if rmr_status != TDEEStatus.OK:
        issues.append("UPSTREAM_RMR_NOT_OK")
    if act_status != TDEEStatus.OK:
        issues.append("UPSTREAM_ACTIVITY_NOT_OK")

    # Inherit upstream issues
    for issue in rmr.issues:
        if issue not in issues:
            issues.append(issue)
    for issue in activity.issues:
        if issue not in issues:
            issues.append(issue)

    return issues


def _validate_domain(
    rmr: "RMRResult",
    activity: "ActivityClassificationResult",
) -> list[str]:
    """Validate domain-level numeric safety when both upstream are OK.

    Returns:
        List of issue codes. Empty list means valid.
    """
    issues: list[str] = []

    # VAL-001: rmr_kcal presence
    if rmr.rmr_kcal is None:
        issues.append("MISSING_RMR_VALUE")

    # VAL-002: activity_factor presence
    if activity.activity_factor is None:
        issues.append("MISSING_ACTIVITY_FACTOR_VALUE")

    # If missing values, return early (can't check non-positive/non-finite)
    if issues:
        return issues

    # VAL-003: rmr_kcal positive
    if rmr.rmr_kcal <= 0:
        issues.append("RMR_VALUE_NON_POSITIVE")

    # VAL-004: activity_factor positive
    if activity.activity_factor <= 0.0:
        issues.append("ACTIVITY_FACTOR_NON_POSITIVE")

    # VAL-005: non-finite check
    if _is_non_finite(float(rmr.rmr_kcal)):
        issues.append("NON_FINITE_INPUT")
    if _is_non_finite(activity.activity_factor):
        issues.append("NON_FINITE_INPUT")

    return issues


def _resolve_domain_status(issues: list[str]) -> TDEEStatus:
    """Resolve status from domain validation issues.

    ERROR issues → ERROR
    INVALID issues → INVALID
    """
    error_codes = {"MISSING_RMR_VALUE", "MISSING_ACTIVITY_FACTOR_VALUE", "NON_FINITE_INPUT"}
    invalid_codes = {"RMR_VALUE_NON_POSITIVE", "ACTIVITY_FACTOR_NON_POSITIVE"}

    has_error = any(issue in error_codes for issue in issues)
    has_invalid = any(issue in invalid_codes for issue in issues)

    if has_error:
        return TDEEStatus.ERROR
    if has_invalid:
        return TDEEStatus.INVALID
    return TDEEStatus.ERROR
