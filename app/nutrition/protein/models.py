"""Protein Calculator contracts — input, result, status, and issue models.

These models define the structured inputs and outputs of the Layer A
ProteinCalculator. They are Pydantic v2 BaseModel with strict=True,
frozen=True, and extra="forbid" for type safety.

Architecture:

    current_weight_kg / goal
               │
               ▼
         ProteinInput
               │
               ▼
        calculate_protein()
               │
               ▼
         ProteinResult

Policy version: protein-v1 (Rev 1.1)
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProteinStatus(str, Enum):
    """Status of the Layer A protein calculation.

    Four-state model (no REVIEW_REQUIRED — clinical review is Layer B).

    Values:
        OK: Calculation completed; protein_g and factor populated.
        INCOMPLETE: Required input missing (weight or goal is None).
        INVALID: Input present but violates domain/type/finiteness rules.
        ERROR: Unexpected system-level failure during calculation.
    """

    OK = "OK"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    ERROR = "ERROR"


class ProteinGoal(str, Enum):
    """Layer A local goal enumeration.

    Mapped 1:1 from shared core GoalType by the Layer B orchestrator:
        GoalType.MAINTENANCE -> ProteinGoal.MAINTENANCE
        GoalType.WEIGHT_LOSS -> ProteinGoal.WEIGHT_LOSS
        GoalType.WEIGHT_GAIN -> ProteinGoal.WEIGHT_GAIN
        GoalType.MUSCLE_GAIN -> ProteinGoal.MUSCLE_GAIN

    Values are UPPERCASE and case-sensitive (distinct from shared
    GoalType's lowercase values — an explicit adapter is required).
    """

    MAINTENANCE = "MAINTENANCE"
    WEIGHT_LOSS = "WEIGHT_LOSS"
    WEIGHT_GAIN = "WEIGHT_GAIN"
    MUSCLE_GAIN = "MUSCLE_GAIN"


class ProteinIssueCode(str, Enum):
    """Operational issue codes for protein calculation failures.

    When status == OK, issues is guaranteed empty ().
    """

    MISSING_WEIGHT = "MISSING_WEIGHT"
    INVALID_WEIGHT = "INVALID_WEIGHT"
    OUT_OF_RANGE_WEIGHT = "OUT_OF_RANGE_WEIGHT"
    MISSING_GOAL = "MISSING_GOAL"
    UNSUPPORTED_GOAL = "UNSUPPORTED_GOAL"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ProteinInput(BaseModel):
    """Strict input contract for Layer A protein calculation.

    Structural validation (Layer A schema) is enforced by Pydantic with
    strict=True (no silent numeric coercion), frozen=True, and
    extra="forbid". Missing/wrong-type/boolean/string/extra fields raise
    ValidationError — NOT ProteinResult.

    Domain validation (presence, finiteness, engineering weight range,
    goal resolution) is performed by the calculator after a valid
    ProteinInput exists.

    Attributes:
        current_weight_kg: Current actual body weight in kg. Optional at
            the schema level so missing weight yields INCOMPLETE /
            MISSING_WEIGHT rather than ValidationError. Engineering
            domain: 0.5 <= weight <= 500.0 (enforced in calculator).
        goal: Nutritional target goal (ProteinGoal). Optional at the
            schema level so missing goal yields INCOMPLETE /
            MISSING_GOAL rather than ValidationError.
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    current_weight_kg: Optional[float] = Field(
        default=None,
        description=(
            "Current actual body weight in kilograms. "
            "Engineering Domain: 0.5 <= val <= 500.0"
        ),
    )
    goal: Optional[ProteinGoal] = Field(
        default=None,
        description="Nutritional target goal.",
    )


class ProteinResult(BaseModel):
    """Frozen Layer A protein calculation result.

    State-based nullability:
        - status == OK: protein_g and protein_factor_g_per_kg non-null;
          current_weight_kg and goal echo inputs; issues == ().
        - status != OK: protein_g and protein_factor_g_per_kg are None;
          issues contains one or more failure codes; valid input echoes
          are preserved where schema-valid.
        - policy_version always equals "protein-v1".

    Nested mutability:
        - issues is an immutable tuple[ProteinIssueCode, ...] so
          in-place mutation (append/pop/extend/...) is impossible even
          though the model itself is also frozen.

    Attributes:
        status: Execution status (OK, INCOMPLETE, INVALID, ERROR).
        protein_g: Daily protein target in integer grams (None if != OK).
        protein_factor_g_per_kg: Exact factor applied (None if != OK).
        current_weight_kg: Echoed input weight if schema-valid, else None.
        goal: Echoed input goal if valid, else None.
        issues: Immutable operational issue codes (empty when OK).
        policy_version: Always "protein-v1".
    """

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
    )

    status: ProteinStatus = Field(
        description="Execution status of the calculation."
    )
    protein_g: Optional[int] = Field(
        default=None,
        description=(
            "Calculated daily protein target in integer grams. "
            "Non-null if status == OK."
        ),
    )
    protein_factor_g_per_kg: Optional[float] = Field(
        default=None,
        description=(
            "Factor applied (g/kg). Non-null if status == OK."
        ),
    )
    current_weight_kg: Optional[float] = Field(
        default=None,
        description="Echoed input weight if schema-valid, else None.",
    )
    goal: Optional[ProteinGoal] = Field(
        default=None,
        description="Echoed input goal if valid, else None.",
    )
    issues: tuple[ProteinIssueCode, ...] = Field(
        default=(),
        description=(
            "Immutable validation/execution issues. "
            "Empty tuple if status == OK."
        ),
    )
    policy_version: str = Field(
        default="protein-v1",
        description="Policy specification version identifier.",
    )
