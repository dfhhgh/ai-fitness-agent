"""Weight Target Determination contracts — input, result, and flag models.

These models define the structured inputs and outputs of the
Weight Target Determination module. They are Pydantic v2 BaseModel with
strict=True, frozen=True, and extra="forbid" for type safety.

Architecture:

    Age / Height / Weight / Goal / Optional user target
                         │
                         ▼
                  WeightTargetInput
                         │
                         ▼
               determine_weight_targets()
                         │
                         ▼
                 WeightTargetResult

Policy version: weight-target-v1-rev1
"""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.nutrition.models import GoalType

# Goals explicitly supported by weight-target-v1-rev1.
# MUSCLE_GAIN is intentionally excluded — no Weight Target semantic is
# defined for it in V1, and it must not silently fall through to
# MAINTENANCE behavior.
WeightTargetGoal = Literal[
    GoalType.WEIGHT_LOSS,
    GoalType.WEIGHT_GAIN,
    GoalType.MAINTENANCE,
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WeightTargetStatus(str, Enum):
    """Status of weight target determination.

    Values:
        OK: Determination completed; initial milestone is populated.
        REVIEW_REQUIRED: One or more safety/review gates fired;
            initial milestone is null.
        ERROR: Contract-level failure path (reserved; Pydantic raises
            ValidationError for structural failures).
    """

    OK = "OK"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"


class ValidationFlag(str, Enum):
    """Informational user-target validation flags.

    These flags MUST NOT change milestone mathematics or status
    (unless an independent review flag exists).
    """

    USER_TARGET_BELOW_REFERENCE_RANGE = "USER_TARGET_BELOW_REFERENCE_RANGE"
    USER_TARGET_ABOVE_REFERENCE_RANGE = "USER_TARGET_ABOVE_REFERENCE_RANGE"


class ReviewFlag(str, Enum):
    """Safety/routing review flags.

    When one or more review flags are present:
        status = REVIEW_REQUIRED
        initial_milestone_weight_kg = None
    """

    CURRENT_WEIGHT_BELOW_REFERENCE_MIN = "CURRENT_WEIGHT_BELOW_REFERENCE_MIN"
    OLDER_ADULT_LOW_BMI_WEIGHT_LOSS = "OLDER_ADULT_LOW_BMI_WEIGHT_LOSS"
    HIGH_BMI_WEIGHT_GAIN_REQUEST = "HIGH_BMI_WEIGHT_GAIN_REQUEST"


# ---------------------------------------------------------------------------
# Input Contract
# ---------------------------------------------------------------------------


class WeightTargetInput(BaseModel):
    """Strict input contract for weight target determination.

    Structural validation (Layer A) is enforced by Pydantic with
    strict=True (no silent numeric coercion), frozen=True, and
    extra="forbid". Missing/wrong-type/zero/negative fields raise
    ValidationError — NOT WeightTargetResult.

    Attributes:
        age_years: Age in years (> 0).
        height_cm: Height in centimeters (> 0).
        current_weight_kg: Current body weight in kg (> 0).
        goal: Fitness goal limited to WEIGHT_LOSS, WEIGHT_GAIN, or
            MAINTENANCE (weight-target-v1-rev1). MUSCLE_GAIN is rejected
            at the contract boundary — it has no Weight Target semantic
            in V1 and must not fall through to maintenance behavior.
        user_requested_target_weight_kg: Optional user-requested target
            weight in kg (> 0). Preserved as input; never mutates
            reference range, milestone, or review gates.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    age_years: int = Field(gt=0, description="Age in years")
    height_cm: float = Field(gt=0.0, description="Height in centimeters")
    current_weight_kg: float = Field(gt=0.0, description="Current weight in kg")
    goal: WeightTargetGoal = Field(
        description=(
            "Fitness goal: WEIGHT_LOSS, WEIGHT_GAIN, or MAINTENANCE only "
            "(weight-target-v1-rev1)"
        )
    )
    user_requested_target_weight_kg: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional user-requested target weight in kg",
    )


# ---------------------------------------------------------------------------
# Result Contract
# ---------------------------------------------------------------------------


class WeightTargetResult(BaseModel):
    """Structured weight target determination result.

    On success (status = OK):
        - reference range always populated (rounded output)
        - initial_milestone_weight_kg populated (not None)
        - validation_flags and review_flags populated (may be empty)

    On review (status = REVIEW_REQUIRED):
        - reference range still populated
        - initial_milestone_weight_kg is None (no milestone calculated)
        - review_flags contains one or more ReviewFlag values

    Attributes:
        status: Determination status (OK, REVIEW_REQUIRED, ERROR).
        current_weight_kg: Echo of input current weight (output-rounded).
        user_requested_target_weight_kg: Echo of optional user target
            (output-rounded; None if not provided).
        reference_weight_range_min_kg: Reference range lower bound (kg).
        reference_weight_range_max_kg: Reference range upper bound (kg).
        initial_milestone_weight_kg: Initial milestone weight (kg);
            None when status != OK.
        validation_flags: Informational user-target range flags.
        review_flags: Safety/routing review flags.
        policy_version: Policy version identifier
            ("weight-target-v1-rev1").
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    status: WeightTargetStatus
    current_weight_kg: float
    user_requested_target_weight_kg: Optional[float] = None
    reference_weight_range_min_kg: float
    reference_weight_range_max_kg: float
    initial_milestone_weight_kg: Optional[float] = None
    validation_flags: List[ValidationFlag] = Field(default_factory=list)
    review_flags: List[ReviewFlag] = Field(default_factory=list)
    policy_version: str = Field(default="weight-target-v1-rev1")
