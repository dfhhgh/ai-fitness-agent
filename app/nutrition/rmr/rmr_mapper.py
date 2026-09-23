"""RMR Mapper — extracts RMR inputs from broader nutrition data.

This module provides the mapping boundary between
NutritionAssessmentInput and RMRInput. It is responsible for:

1. Extracting only the 4 required RMR fields
2. Normalizing biological sex to "MALE" or "FEMALE"
3. Translating raw type errors into INVALID_NUMERIC_TYPE

Type validation rules:
- None for any field → pass through to calculator (INCOMPLETE / MISSING_RMR_DATA)
- Non-numeric type (str/bool/list/dict) for age/height/weight → ERROR / INVALID_NUMERIC_TYPE
- Non-string type (int/float/bool/list/dict) for gender → ERROR / INVALID_NUMERIC_TYPE
- String gender but unsupported value ("OTHER", "M", etc.) → INVALID / UNSUPPORTED_GENDER
- String gender "male"/"female" → normalize to "MALE"/"FEMALE"

Architecture:

    NutritionAssessmentInput (broader data)
            ↓
        RMRMapper
            ↓
         RMRInput (strict 4-field)
            ↓
      RMRCalculator
            ↓
         RMRResult

Non-RMR fields have ZERO effect on the result.
"""

from typing import Any, Optional, Union

from app.nutrition.rmr.rmr_models import (
    RMRInput,
    RMRResult,
    RMRStatus,
)

RMR_POLICY_VERSION: str = "rmr-v1"


def _is_valid_numeric_type(value: Any) -> bool:
    """Check if a value is a valid numeric type (int or float), or None.

    None is considered valid here because it represents missing data,
    which the calculator handles as INCOMPLETE / MISSING_RMR_DATA.

    Rejects:
    - str (including numeric strings like "80")
    - bool (subclass of int, but not valid for RMR)
    - list, dict, etc.

    Accepts:
    - None (missing data, passed through to calculator)
    - int (but not bool)
    - float (but not NaN, Inf — those are checked later by calculator)

    Args:
        value: Value to check.

    Returns:
        True if the value is None or a valid numeric type.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def _normalize_gender(raw_gender: Any) -> tuple[Optional[str], Optional[RMRResult]]:
    """Normalize raw gender value and detect type errors.

    Returns:
        Tuple of (normalized_gender, error_result).
        - On success: ("MALE" or "FEMALE", None)
        - On missing data: (None, None) — calculator handles INCOMPLETE
        - On type error: (None, RMRResult with ERROR/INVALID_NUMERIC_TYPE)
        - On unsupported string: (raw value, None) — calculator handles INVALID/UNSUPPORTED_GENDER
    """
    if raw_gender is None:
        return None, None

    if isinstance(raw_gender, bool):
        return None, RMRResult(
            status=RMRStatus.ERROR,
            issues=["INVALID_NUMERIC_TYPE"],
            policy_version=RMR_POLICY_VERSION,
        )

    if not isinstance(raw_gender, str):
        return None, RMRResult(
            status=RMRStatus.ERROR,
            issues=["INVALID_NUMERIC_TYPE"],
            policy_version=RMR_POLICY_VERSION,
        )

    normalized = raw_gender.upper().strip()
    if normalized in ("MALE", "FEMALE"):
        return normalized, None

    # Unsupported string value — let calculator handle INVALID/UNSUPPORTED_GENDER
    return raw_gender, None


class RMRMapper:
    """Maps broader nutrition data to strict RMR input.

    The mapper extracts exactly 4 fields from NutritionAssessmentInput
    and normalizes them for the RMRCalculator.

    Type validation happens HERE, not in the calculator.
    Missing data and value validation happen in the calculator.
    """

    def map_from_assessment(self, assessment: Any) -> Union[RMRInput, RMRResult]:
        """Map NutritionAssessmentInput to RMRInput.

        Extracts age, gender, height_cm, weight_kg.
        Validates raw types before constructing RMRInput.
        None values pass through for calculator INCOMPLETE handling.

        Args:
            assessment: A NutritionAssessmentInput or compatible object.

        Returns:
            RMRInput on success, RMRResult on type validation failure.
        """
        raw_age = getattr(assessment, "age", None)
        raw_gender = getattr(assessment, "gender", None)
        raw_height = getattr(assessment, "height_cm", None)
        raw_weight = getattr(assessment, "weight_kg", None)

        # Type validation for numeric fields (None is valid — missing data)
        if not _is_valid_numeric_type(raw_age):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )
        if not _is_valid_numeric_type(raw_height):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )
        if not _is_valid_numeric_type(raw_weight):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )

        # Normalize gender (handles type errors and unsupported values)
        normalized_gender, gender_error = _normalize_gender(raw_gender)
        if gender_error is not None:
            return gender_error

        return RMRInput(
            age=raw_age,
            gender=normalized_gender,
            height_cm=raw_height,
            weight_kg=raw_weight,
        )

    def map_from_dict(self, data: dict) -> Union[RMRInput, RMRResult]:
        """Map a dictionary to RMRInput.

        Validates raw types before constructing RMRInput.
        None values pass through for calculator INCOMPLETE handling.

        Args:
            data: Dictionary containing at least age, gender,
                height_cm, weight_kg.

        Returns:
            RMRInput on success, RMRResult on type validation failure.
        """
        raw_age = data.get("age")
        raw_gender = data.get("gender")
        raw_height = data.get("height_cm")
        raw_weight = data.get("weight_kg")

        # Type validation for numeric fields (None is valid — missing data)
        if not _is_valid_numeric_type(raw_age):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )
        if not _is_valid_numeric_type(raw_height):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )
        if not _is_valid_numeric_type(raw_weight):
            return RMRResult(
                status=RMRStatus.ERROR,
                issues=["INVALID_NUMERIC_TYPE"],
                policy_version=RMR_POLICY_VERSION,
            )

        # Normalize gender (handles type errors and unsupported values)
        normalized_gender, gender_error = _normalize_gender(raw_gender)
        if gender_error is not None:
            return gender_error

        return RMRInput(
            age=raw_age,
            gender=normalized_gender,
            height_cm=raw_height,
            weight_kg=raw_weight,
        )
