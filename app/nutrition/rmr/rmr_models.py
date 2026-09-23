"""RMR Calculator contracts — input, result, and status models.

These models define the structured inputs and outputs of the
RMRCalculator. They are Pydantic v2 BaseModel with extra="forbid"
for type safety and JSON serialization.

Architecture:

    NutritionAssessmentInput
            ↓
        RMRMapper
            ↓
          RMRInput
            ↓
      RMRCalculator
            ↓
         RMRResult
            ↓
      future TDEECalculator

Policy version: rmr-v1
Active method: Mifflin-St Jeor
"""

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RMRStatus(str, Enum):
    """RMR calculation status.

    Four-tier status model consistent with platform standards.

    Values:
        OK: All required inputs valid, calculation completed.
        INCOMPLETE: Required fields are null/missing.
        INVALID: Inputs violate domain validation bounds.
        ERROR: Structural/numeric type errors or non-finite floats.
    """

    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    ERROR = "ERROR"


class RMRMethod(str, Enum):
    """RMR calculation method.

    MIFFLIN_ST_JEOR is the sole active method for rmr-v1.
    CUNNINGHAM is retained in the enum for future expansion but
    is NOT implemented as an active method.
    """

    MIFFLIN_ST_JEOR = "MIFFLIN_ST_JEOR"
    CUNNINGHAM = "CUNNINGHAM"


class BiologicalSex(str, Enum):
    """Normalized biological sex for Mifflin-St Jeor.

    The calculator accepts only these two values.
    Inference from names, pronouns, or measurements is forbidden.
    """

    MALE = "MALE"
    FEMALE = "FEMALE"


# ---------------------------------------------------------------------------
# Input Contract
# ---------------------------------------------------------------------------


class RMRInput(BaseModel):
    """Strict 4-field input contract for RMR calculation.

    Contains ONLY the four attributes required for baseline metabolic
    calculation. Arbitrary extra fields are not accepted.

    Pydantic enforces STRUCTURAL and TYPE safety only.
    RANGE validation is performed by the RMRCalculator.

    Attributes:
        age: Age in years (18–120 validated by calculator).
        gender: Normalized biological sex ("MALE" or "FEMALE").
        height_cm: Height in centimeters (50–250 validated by calculator).
        weight_kg: Weight in kilograms (20–350 validated by calculator).
    """

    model_config = ConfigDict(extra="forbid")

    age: Optional[Union[int, float]] = Field(
        default=None,
        description="Age in years (18–120 validated by calculator)",
    )
    gender: Optional[str] = Field(
        default=None,
        description="Normalized biological sex: 'MALE' or 'FEMALE'",
    )
    height_cm: Optional[float] = Field(
        default=None,
        description="Height in centimeters (50–250 validated by calculator)",
    )
    weight_kg: Optional[float] = Field(
        default=None,
        description="Weight in kilograms (20–350 validated by calculator)",
    )


# ---------------------------------------------------------------------------
# Result Contract
# ---------------------------------------------------------------------------


class RMRResult(BaseModel):
    """Structured RMR calculation result.

    On success (status = OK):
        - rmr_kcal contains integer result
        - rmr_method = "MIFFLIN_ST_JEOR"
        - issues = []

    On failure (INCOMPLETE, INVALID, ERROR):
        - rmr_kcal = null
        - rmr_method = null
        - issues contain the relevant error codes

    Attributes:
        status: Calculation status (OK, INCOMPLETE, INVALID, ERROR).
        issues: Structured issue codes for programmatic handling.
        rmr_kcal: Calculated RMR in kcal/day (integer, null on failure).
        rmr_method: Active calculation method (null on failure).
        policy_version: Policy tracking string ("rmr-v1").
    """

    model_config = ConfigDict(extra="forbid")

    status: RMRStatus
    issues: List[str] = Field(default_factory=list)

    # --- Calculation output (populated only when status == OK) ---
    rmr_kcal: Optional[int] = Field(default=None, ge=0)
    rmr_method: Optional[RMRMethod] = None

    # --- Metadata ---
    policy_version: str = Field(default="rmr-v1")
