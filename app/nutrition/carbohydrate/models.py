"""Carbohydrate Calculator contracts — input, result, status, and issue models.

These models define the structured inputs and outputs of the Layer A
CarbohydrateCalculator. They are Pydantic v2 BaseModel with strict=True,
frozen=True, and extra="forbid" for type safety.

Architecture:

    target_calories / protein_g / fat_calories
               │
               ▼
          CarbInput
               │
               ▼
        calculate_carbohydrates()
               │
               ▼
          CarbResult

Policy version: carb-v1
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CarbStatus(str, Enum):
    """Status of the Layer A carbohydrate calculation.

    Two-state model — the only domain-level failure is a negative
    residual. Schema violations (missing/wrong-type/extra fields) are
    intercepted by Pydantic ValidationError before calculator logic runs.

    Values:
        OK: Calculation completed; carbohydrate fields populated.
        INVALID: Negative carbohydrate residual detected.
    """

    OK = "OK"
    INVALID = "INVALID"


class CarbIssueCode(str, Enum):
    """Operational issue codes for carbohydrate calculation failures.

    When status == OK, issues is guaranteed empty ().
    """

    NEGATIVE_CARBOHYDRATE_RESIDUAL = "NEGATIVE_CARBOHYDRATE_RESIDUAL"


class CarbInput(BaseModel):
    """Strict input contract for Layer A carbohydrate calculation.

    Structural validation (Layer A schema) is enforced by Pydantic with
    strict=True (no silent numeric coercion), frozen=True, and
    extra="forbid". Missing/wrong-type/boolean/string/extra fields raise
    ValidationError — NOT CarbResult.

    All three fields are required (no Optional, no defaults). Negative
    values are rejected by Pydantic (ge=0).

    Attributes:
        target_calories: Authoritative daily target energy intake in kcal.
        protein_g: Authoritative daily protein target in integer grams
            (from ProteinResult.protein_g).
        fat_calories: Authoritative realized energy from fat allocation
            (from FatResult.fat_calories). Never fat_g — no fat_g field
            exists on this model.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    target_calories: int = Field(..., ge=0)
    protein_g: int = Field(..., ge=0)
    fat_calories: int = Field(..., ge=0)


class CarbResult(BaseModel):
    """Frozen Layer A carbohydrate calculation result.

    State-based nullability:
        - status == OK: carbohydrates_g and carbohydrate_calories
          non-null; residual_calories non-null (>= 0); issues == ().
        - status == INVALID: carbohydrates_g and carbohydrate_calories
          are None; residual_calories non-null (negative); issues
          contains (NEGATIVE_CARBOHYDRATE_RESIDUAL,).
        - residual_calories is NEVER None on either status.
        - policy_version always equals "carb-v1".

    Nested mutability:
        - issues is an immutable tuple[CarbIssueCode, ...] so
          in-place mutation (append/pop/extend/...) is impossible even
          though the model itself is also frozen.

    Attributes:
        status: Execution status (OK or INVALID).
        carbohydrates_g: Calculated daily carbohydrate target in integer
            grams (None if status == INVALID).
        carbohydrate_calories: Realized energy from rounded carbohydrate
            mass (carbohydrates_g * 4). None if status == INVALID.
        residual_calories: Residual energy after subtracting protein and
            fat energy from target calories. Always populated, may be
            negative on INVALID.
        issues: Immutable operational issue codes (empty when OK).
        policy_version: Always "carb-v1".
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
    )

    status: CarbStatus = Field(
        description="Execution status of the calculation."
    )
    carbohydrates_g: Optional[int] = Field(
        default=None,
        description=(
            "Calculated daily carbohydrate target in integer grams. "
            "Non-null if status == OK."
        ),
    )
    carbohydrate_calories: Optional[int] = Field(
        default=None,
        description=(
            "Realized energy from rounded carbohydrate mass "
            "(carbohydrates_g * 4). Non-null if status == OK."
        ),
    )
    residual_calories: int = Field(
        description=(
            "Residual energy after protein and fat energy subtraction. "
            "Always populated; may be negative on INVALID."
        ),
    )
    issues: tuple[CarbIssueCode, ...] = Field(
        default=(),
        description=(
            "Immutable validation/execution issues. "
            "Empty tuple if status == OK."
        ),
    )
    policy_version: str = Field(
        default="carb-v1",
        description="Policy specification version identifier.",
    )
