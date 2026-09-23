"""TDEE Calculator contracts — input, result, and traceability models.

These models define the structured inputs and outputs of the
TDEECalculator. They are Pydantic v2 BaseModel with extra="forbid"
for type safety and JSON serialization.

Architecture:

    ActivityClassificationResult ──┐
                                   ├──► TDEEInput
    RMRResult ─────────────────────┘
                                       │
                                       ▼
                                  TDEECalculator
                                       │
                                       ▼
                                  TDEEResult
                                       │
                                       ▼
                            Calorie Target Engine

Policy version: tdee-v1
"""

from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.nutrition.activity.activity_models import ActivityClassificationResult
from app.nutrition.models import ActivityCategory
from app.nutrition.rmr.rmr_models import RMRResult


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TDEEStatus(str, Enum):
    """TDEE calculation status.

    Four-tier status model consistent with platform standards.

    Values:
        OK: All upstream results OK, calculation completed.
        INCOMPLETE: Upstream result(s) incomplete.
        INVALID: Upstream result(s) invalid or domain validation failed.
        ERROR: Upstream error(s) or arithmetic/domain error.
    """

    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Input Contract
# ---------------------------------------------------------------------------


class TDEEInput(BaseModel):
    """Strict input contract for TDEE calculation.

    Contains the two required upstream result objects and optional
    metadata. Extra fields are forbidden.

    Schema validation (Layer A) is enforced by Pydantic.
    Missing/wrong-type fields raise ValidationError — NOT TDEEResult.

    Attributes:
        rmr_result: Authoritative result from RMRCalculator.
        activity_result: Authoritative result from ActivityClassifier.
        correlation_id: Optional tracking identifier (metadata only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rmr_result: RMRResult = Field(
        description="Authoritative result from RMRCalculator (rmr-v1)"
    )
    activity_result: ActivityClassificationResult = Field(
        description="Authoritative result from ActivityClassifier (activity-v1)"
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Optional tracking identifier (metadata only)",
    )


# ---------------------------------------------------------------------------
# Traceability Contract
# ---------------------------------------------------------------------------


class TDEETraceability(BaseModel):
    """Structured audit trail for TDEE calculation.

    Contains deterministic calculation parameters for clinical
    auditing and automated verification. No timestamps or
    mutable runtime state.

    Attributes:
        rmr_kcal_used: Exact integer RMR consumed.
        activity_factor_used: String representation of Decimal factor.
        raw_tdee_unrounded: Unrounded decimal product string.
        formula_expression: Literal mathematical formula.
        rounding_mode: Quantization strategy applied.
        policy_version: Policy version identifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rmr_kcal_used: int = Field(description="Exact integer RMR consumed")
    activity_factor_used: str = Field(
        description="String representation of Decimal factor used"
    )
    raw_tdee_unrounded: str = Field(
        description="Unrounded decimal product string"
    )
    formula_expression: str = Field(
        default="TDEE = RMR * ActivityFactor",
        description="Literal mathematical formula expression",
    )
    rounding_mode: str = Field(
        default="ROUND_HALF_UP",
        description="Quantization strategy applied",
    )
    policy_version: str = Field(
        default="tdee-v1",
        description="Policy version identifier string",
    )


# ---------------------------------------------------------------------------
# Result Contract
# ---------------------------------------------------------------------------


class TDEEResult(BaseModel):
    """Structured TDEE calculation result.

    On success (status = OK):
        - tdee_kcal populated with integer kcal/day
        - rmr_kcal_used populated
        - activity_factor_used populated as Decimal string
        - activity_category_used populated
        - traceability populated

    On failure (INCOMPLETE, INVALID, ERROR):
        - All calculation fields are None
        - issues contain aggregated issue codes

    Attributes:
        status: Calculation status (OK, INCOMPLETE, INVALID, ERROR).
        tdee_kcal: Calculated TDEE in integer kcal/day (null on failure).
        rmr_kcal_used: Integer RMR consumed (null on failure).
        activity_factor_used: Decimal activity factor (null on failure).
        activity_category_used: ActivityCategory enum (null on failure).
        issues: Aggregated issue code strings.
        policy_version: Policy version identifier ("tdee-v1").
        traceability: Structured audit trail (null on failure).
    """

    model_config = ConfigDict(extra="forbid")

    status: TDEEStatus
    issues: List[str] = Field(default_factory=list)

    # --- Calculation output (populated only when status == OK) ---
    tdee_kcal: Optional[int] = Field(default=None, ge=0)
    rmr_kcal_used: Optional[int] = Field(default=None, ge=0)
    activity_factor_used: Optional[Decimal] = None
    activity_category_used: Optional[ActivityCategory] = None

    # --- Metadata ---
    policy_version: str = Field(default="tdee-v1")
    traceability: Optional[TDEETraceability] = None
