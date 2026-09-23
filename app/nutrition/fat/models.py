"""Fat Calculator contracts — input, result, status, and issue models.

These models define the structured inputs and outputs of the Layer A
FatCalculator. They are Pydantic v2 BaseModel with strict=True,
frozen=True, and extra="forbid" for type safety.

Architecture:

    target_calories / goal
               │
               ▼
          FatInput
               │
               ▼
        calculate_fat()
               │
               ▼
          FatResult

Policy version: fat-v1-rev1
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FatStatus(str, Enum):
    """Status of the Layer A fat calculation.

    Four-state model (no REVIEW_REQUIRED — clinical review is Layer B).

    Values:
        OK: Calculation completed; fat fields populated.
        INCOMPLETE: Required input missing (target_calories or goal is None).
        INVALID: Input present but violates domain rules.
        ERROR: Unexpected system-level failure during calculation.
    """

    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    ERROR = "ERROR"


class FatGoal(str, Enum):
    """Layer A local goal enumeration.

    Mapped 1:1 from shared core GoalType by the Layer B orchestrator:
        GoalType.MAINTENANCE -> FatGoal.MAINTENANCE
        GoalType.WEIGHT_LOSS -> FatGoal.WEIGHT_LOSS
        GoalType.WEIGHT_GAIN -> FatGoal.WEIGHT_GAIN
        GoalType.MUSCLE_GAIN -> FatGoal.MUSCLE_GAIN

    Values are UPPERCASE and case-sensitive (distinct from shared
    GoalType's lowercase values — an explicit adapter is required).

    Goal invariance: all four goals use the same 25% fat energy fraction.
    """

    MAINTENANCE = "MAINTENANCE"
    WEIGHT_LOSS = "WEIGHT_LOSS"
    WEIGHT_GAIN = "WEIGHT_GAIN"
    MUSCLE_GAIN = "MUSCLE_GAIN"


class FatIssueCode(str, Enum):
    """Operational issue codes for fat calculation failures.

    When status == OK, issues is guaranteed empty ().
    """

    MISSING_TARGET_CALORIES = "MISSING_TARGET_CALORIES"
    INVALID_TARGET_CALORIES = "INVALID_TARGET_CALORIES"
    OUT_OF_RANGE_TARGET_CALORIES = "OUT_OF_RANGE_TARGET_CALORIES"
    MISSING_GOAL = "MISSING_GOAL"
    UNSUPPORTED_GOAL = "UNSUPPORTED_GOAL"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class FatInput(BaseModel):
    """Strict input contract for Layer A fat calculation.

    Structural validation (Layer A schema) is enforced by Pydantic with
    strict=True (no silent numeric coercion), frozen=True, and
    extra="forbid". Missing/wrong-type/boolean/string/extra fields raise
    ValidationError — NOT FatResult.

    Domain validation (presence, calorie lower bound, goal resolution)
    is performed by the calculator after a valid FatInput exists.

    Attributes:
        target_calories: Authoritative daily target energy intake in kcal.
            Optional at the schema level so missing value yields
            INCOMPLETE / MISSING_TARGET_CALORIES rather than ValidationError.
            Engineering domain: target_calories >= 1 (enforced in calculator).
        goal: Nutritional target goal (FatGoal). Optional at the schema
            level so missing goal yields INCOMPLETE / MISSING_GOAL rather
            than ValidationError.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    target_calories: Optional[int] = Field(
        default=None,
        description=(
            "Authoritative daily target energy intake in kcal. "
            "Valid domain: target_calories >= 1"
        ),
    )
    goal: Optional[FatGoal] = Field(
        default=None,
        description="Target fitness goal enumeration mapped 1:1 from GoalType.",
    )


class FatResult(BaseModel):
    """Frozen Layer A fat calculation result.

    State-based nullability:
        - status == OK: fat_g, fat_calories, target_fat_percentage, and
          effective_fat_percentage non-null; issues == ().
        - status != OK: all calculation fields are None; issues contains
          one or more failure codes; valid input echoes are preserved
          where domain-valid.
        - target_calories echoes input when domain-valid, else None.
        - goal echoes input when valid, else None.
        - policy_version always equals "fat-v1-rev1".

    Nested mutability:
        - issues is an immutable tuple[FatIssueCode, ...] so in-place
          mutation (append/pop/extend/...) is impossible even though the
          model itself is also frozen.

    Attributes:
        status: Execution status (OK, INCOMPLETE, INVALID, ERROR).
        fat_g: Daily fat target in rounded integer grams (None if != OK).
        fat_calories: Realized energy from rounded fat mass (None if != OK).
        target_fat_percentage: Configured energy fraction 0.25 (None if != OK).
        effective_fat_percentage: Realized energy percentage rounded to
            6 decimal places (None if != OK).
        target_calories: Echoed input calories if domain-valid, else None.
        goal: Echoed input goal if valid, else None.
        issues: Immutable operational issue codes (empty when OK).
        policy_version: Always "fat-v1-rev1".
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    status: FatStatus = Field(
        description="Execution status of the calculator component."
    )
    fat_g: Optional[int] = Field(
        default=None,
        description=(
            "Calculated target daily fat in rounded integer grams. "
            "Non-null if status == OK."
        ),
    )
    fat_calories: Optional[int] = Field(
        default=None,
        description=(
            "Realized energy from rounded fat mass (fat_g * 9). "
            "Non-null if status == OK."
        ),
    )
    target_fat_percentage: Optional[float] = Field(
        default=None,
        description=(
            "Configured energy target fraction (0.25). Non-null if status == OK."
        ),
    )
    effective_fat_percentage: Optional[float] = Field(
        default=None,
        description=(
            "Realized percentage of calories from rounded fat quantized "
            "to 6 decimal places. Non-null if status == OK."
        ),
    )
    target_calories: Optional[int] = Field(
        default=None,
        description="Echoed input target calories if domain-valid, else None.",
    )
    goal: Optional[FatGoal] = Field(
        default=None,
        description="Echoed input goal enum if schema-valid, else None.",
    )
    issues: tuple[FatIssueCode, ...] = Field(
        default=(),
        description=(
            "Immutable tuple of validation or execution issues. "
            "Guaranteed empty tuple () if status == OK."
        ),
    )
    policy_version: str = Field(
        default="fat-v1-rev1",
        description="Policy version identifier.",
    )
