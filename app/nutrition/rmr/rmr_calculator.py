"""Deterministic RMR calculator — Mifflin-St Jeor (rmr-v1).

This module implements the complete deterministic RMR calculation
using the Mifflin-St Jeor (1990) equation.

Policy version: rmr-v1
Active method: Mifflin-St Jeor only

Algorithm:
    1. Validate inputs (missing data, gender, ranges, non-finite)
    2. Calculate RMR using Mifflin-St Jeor
    3. Apply half-up rounding to nearest integer
    4. Return RMRResult

This module is deterministic and side-effect free:
- No LLM calls
- No database access
- No external APIs
- No inference of missing data
- No activity/TDEE/calorie calculations
"""

import math

from app.nutrition.rmr.rmr_models import (
    BiologicalSex,
    RMRInput,
    RMRMethod,
    RMRResult,
    RMRStatus,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

RMR_POLICY_VERSION: str = "rmr-v1"

# Mifflin-St Jeor biological sex constants
# Male: s = +5
# Female: s = -161
SEX_CONSTANT_MALE: int = 5
SEX_CONSTANT_FEMALE: int = -161

# Engineering validation bounds
AGE_MIN: int = 18
AGE_MAX: int = 120
HEIGHT_MIN_CM: float = 50.0
HEIGHT_MAX_CM: float = 250.0
WEIGHT_MIN_KG: float = 20.0
WEIGHT_MAX_KG: float = 350.0


def _half_up_round(value: float) -> int:
    """Round a non-negative float to nearest integer using half-up logic.

    Half-up rounding: ties at exactly x.5 round upward in magnitude.
    This is NOT Python's default round-to-even (banker's rounding).

    Args:
        value: Non-negative float value to round.

    Returns:
        Rounded integer.
    """
    return int(math.floor(value + 0.5))


def _is_non_finite(value: float) -> bool:
    """Check if a float value is NaN, +Infinity, or -Infinity.

    Args:
        value: Float value to check.

    Returns:
        True if the value is non-finite.
    """
    return math.isnan(value) or math.isinf(value)


class RMRCalculator:
    """Deterministic RMR calculator — Mifflin-St Jeor.

    The calculator accepts a typed RMRInput and returns an RMRResult.
    It is stateless and side-effect free.

    Mifflin-St Jeor equation:
        RMR_raw = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + s

    Where:
        s = +5 for males
        s = -161 for females
    """

    def calculate(self, inputs: RMRInput) -> RMRResult:
        """Calculate RMR from structured input.

        Validation order:
            1. Missing-data check → INCOMPLETE
            2. Gender validation → INVALID
            3. Non-finite check → ERROR
            4. Range validation → INVALID
            5. Calculation → OK

        Args:
            inputs: Typed RMR input with exactly 4 fields.

        Returns:
            RMRResult with status, rmr_kcal, rmr_method, and policy_version.
        """
        # Step 1: Missing-data check
        missing_issues = self._check_missing(inputs)
        if missing_issues:
            return RMRResult(
                status=RMRStatus.INCOMPLETE,
                issues=missing_issues,
                policy_version=RMR_POLICY_VERSION,
            )

        # Step 2: Gender validation
        gender_issues = self._validate_gender(inputs.gender)
        if gender_issues:
            return RMRResult(
                status=RMRStatus.INVALID,
                issues=gender_issues,
                policy_version=RMR_POLICY_VERSION,
            )

        # Step 3: Non-finite check
        non_finite_issues = self._check_non_finite(inputs)
        if non_finite_issues:
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=non_finite_issues,
                policy_version=RMR_POLICY_VERSION,
            )

        # Step 4: Range validation
        range_issues = self._validate_ranges(inputs)
        if range_issues:
            return RMRResult(
                status=RMRStatus.INVALID,
                issues=range_issues,
                policy_version=RMR_POLICY_VERSION,
            )

        # Step 5: Calculate RMR
        rmr_raw = self._compute_mifflin_st_jeor(inputs)

        # Step 6: Half-up rounding
        rmr_kcal = _half_up_round(rmr_raw)

        return RMRResult(
            status=RMRStatus.OK,
            issues=[],
            rmr_kcal=rmr_kcal,
            rmr_method=RMRMethod.MIFFLIN_ST_JEOR,
            policy_version=RMR_POLICY_VERSION,
        )

    def _check_missing(self, inputs: RMRInput) -> list[str]:
        """Check for missing required fields.

        Returns:
            List of issue codes. Empty list means complete.
        """
        issues: list[str] = []

        if inputs.age is None:
            issues.append("MISSING_RMR_DATA")
        if inputs.gender is None:
            issues.append("MISSING_RMR_DATA")
        if inputs.height_cm is None:
            issues.append("MISSING_RMR_DATA")
        if inputs.weight_kg is None:
            issues.append("MISSING_RMR_DATA")

        return issues

    def _validate_gender(self, gender: str) -> list[str]:
        """Validate gender is a supported biological sex value.

        Returns:
            List of issue codes. Empty list means valid.
        """
        try:
            BiologicalSex(gender)
        except ValueError:
            return ["UNSUPPORTED_GENDER"]
        return []

    def _check_non_finite(self, inputs: RMRInput) -> list[str]:
        """Check for non-finite numeric values (NaN, Infinity).

        Returns:
            List of issue codes. Empty list means all finite.
        """
        issues: list[str] = []

        if _is_non_finite(float(inputs.age)):
            issues.append("NUMERIC_OUT_OF_RANGE")
        if _is_non_finite(inputs.height_cm):
            issues.append("NUMERIC_OUT_OF_RANGE")
        if _is_non_finite(inputs.weight_kg):
            issues.append("NUMERIC_OUT_OF_RANGE")

        return issues

    def _validate_ranges(self, inputs: RMRInput) -> list[str]:
        """Validate engineering input bounds.

        Age: 18–120
        Height: 50–250 cm
        Weight: 20–350 kg

        Returns:
            List of issue codes. Empty list means valid.
        """
        issues: list[str] = []

        age = inputs.age
        if age < 0:
            issues.append("INVALID_AGE")
        elif age < AGE_MIN:
            issues.append("UNDERAGE_NOT_SUPPORTED")
        elif age > AGE_MAX:
            issues.append("INVALID_AGE")

        if inputs.height_cm < HEIGHT_MIN_CM or inputs.height_cm > HEIGHT_MAX_CM:
            issues.append("INVALID_HEIGHT")

        if inputs.weight_kg < WEIGHT_MIN_KG or inputs.weight_kg > WEIGHT_MAX_KG:
            issues.append("INVALID_WEIGHT")

        return issues

    def _compute_mifflin_st_jeor(self, inputs: RMRInput) -> float:
        """Compute RMR using the Mifflin-St Jeor equation.

        RMR_raw = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + s

        No intermediate rounding. Full 64-bit double precision.

        Args:
            inputs: Validated RMR input.

        Returns:
            Raw RMR value in kcal/day (float, before rounding).
        """
        sex_constant = (
            SEX_CONSTANT_MALE
            if inputs.gender == BiologicalSex.MALE
            else SEX_CONSTANT_FEMALE
        )

        return (
            (10.0 * inputs.weight_kg)
            + (6.25 * inputs.height_cm)
            - (5.0 * inputs.age)
            + sex_constant
        )
