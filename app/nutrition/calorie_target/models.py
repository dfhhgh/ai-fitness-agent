"""Calorie Target Calculator contracts — input, result, and traceability models.

These models define the structured inputs and outputs of the
CalorieTargetCalculator. They are Pydantic v2 BaseModel with extra="forbid"
for type safety and JSON serialization.

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

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.nutrition.models import GoalType
from app.nutrition.tdee.tdee_models import TDEEResult


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CalorieTargetStatus(str, Enum):
    """Calorie target calculation status.

    Four-tier status model consistent with platform standards
    (RMRStatus, TDEEStatus).

    Values:
        OK: Upstream TDEE OK, calculation completed.
        INCOMPLETE: Upstream TDEE incomplete.
        INVALID: Upstream TDEE invalid.
        ERROR: Upstream TDEE error or domain validation failed.
    """

    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Input Contract
# ---------------------------------------------------------------------------


class CalorieTargetInput(BaseModel):
    """Strict input contract for calorie target calculation.

    Contains the required upstream TDEE result, the required goal type,
    and optional metadata. Extra fields are forbidden.

    Schema validation (Layer A) is enforced by Pydantic.
    Missing/wrong-type fields raise ValidationError — NOT CalorieTargetResult.

    Attributes:
        tdee_result: Authoritative result from TDEECalculator (tdee-v1).
        goal_type: User-defined fitness goal (GoalType).
        correlation_id: Optional tracking identifier (metadata only).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tdee_result: TDEEResult = Field(
        description="Authoritative result from TDEECalculator (tdee-v1)"
    )
    goal_type: GoalType = Field(
        description="Target goal type; absence is a structural error"
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Optional tracking identifier (metadata only)",
    )


# ---------------------------------------------------------------------------
# Traceability Contract
# ---------------------------------------------------------------------------


class CalorieTargetTraceability(BaseModel):
    """Structured audit trail for calorie target calculation.

    Contains deterministic calculation parameters for auditing and
    automated verification. No timestamps or mutable runtime state.

    Attributes:
        correlation_id: Optional tracking identifier propagated from input.
        formula_expression: Literal mathematical formula.
        arithmetic_mode: Integer arithmetic mode marker.
        policy_version: Policy version identifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: Optional[str] = Field(
        default=None,
        description="Optional tracking identifier propagated from input",
    )
    formula_expression: str = Field(
        default="Target Calories = TDEE + Goal Adjustment",
        description="Literal mathematical formula expression",
    )
    arithmetic_mode: str = Field(
        default="integer",
        description="Arithmetic mode (integer only; no Decimal, no rounding)",
    )
    policy_version: str = Field(
        default="calorie-v1",
        description="Policy version identifier string",
    )


# ---------------------------------------------------------------------------
# Result Contract
# ---------------------------------------------------------------------------


class CalorieTargetResult(BaseModel):
    """Structured calorie target calculation result.

    On success (status = OK):
        - target_calories_kcal populated with integer kcal/day
        - tdee_kcal_used populated
        - goal_type_used populated
        - calorie_adjustment_kcal populated
        - safety_flags may contain LOW_CALORIE_REVIEW_REQUIRED
        - traceability populated

    On failure (INCOMPLETE, INVALID, ERROR):
        - target_calories_kcal is None
        - tdee_kcal_used is None
        - goal_type_used and calorie_adjustment_kcal echo input-derived values
        - issues contain Layer B issue codes
        - safety_flags is empty
        - traceability populated (metadata only)

    Attributes:
        status: Calculation status (OK, INCOMPLETE, INVALID, ERROR).
        target_calories_kcal: Daily calorie goal (null on failure).
        tdee_kcal_used: TDEE value consumed (null on failure).
        goal_type_used: Goal type received from input.
        calorie_adjustment_kcal: Fixed goal adjustment from mapping.
        policy_version: Policy version identifier ("calorie-v1").
        issues: Layer B issue codes (if any).
        safety_flags: Safety flags (e.g. LOW_CALORIE_REVIEW_REQUIRED).
        traceability: Deterministic audit trail (no timestamps).
    """

    model_config = ConfigDict(extra="forbid")

    status: CalorieTargetStatus
    issues: List[str] = Field(default_factory=list)
    safety_flags: List[str] = Field(default_factory=list)

    # --- Calculation output (populated only when status == OK) ---
    target_calories_kcal: Optional[int] = None
    tdee_kcal_used: Optional[int] = None

    # --- Input-derived echo (always populated) ---
    goal_type_used: GoalType
    calorie_adjustment_kcal: int

    # --- Metadata ---
    policy_version: str = Field(default="calorie-v1")
    traceability: Optional[CalorieTargetTraceability] = None
