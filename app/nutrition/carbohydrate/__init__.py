"""Carbohydrate Calculator — deterministic residual-macro processor (carb-v1).

This package provides the isolated Layer A carbohydrate calculator for
the Nutrition Core pipeline.

Responsibilities (Layer A):
- Daily carbohydrate target (integer grams) from residual energy
- Residual = target_calories - (protein_g * 4) - fat_calories
- Rounding: Decimal ROUND_HALF_UP to integer grams (never Python
  banker's rounding)
- Two-state status: OK, INVALID
- Single domain issue: NEGATIVE_CARBOHYDRATE_RESIDUAL
- Strict contracts: strict=True, frozen=True, extra="forbid"

Does NOT (Layer A):
- Subtract fiber (total carbohydrate, not net)
- Enforce 130g/day carbohydrate floor
- Enforce AMDR 45–65% range
- Classify carbohydrate quality or glycemic index
- Distribute carbs across meals
- Reconstruct fat energy from fat_g * 9 (consumes fat_calories directly)
- Apply clinical review or medical screening (Layer B)
- Compute or consume RMR, TDEE, calories, activity, protein, fat
- Call LLM, network, database, system clock, or random state

Architecture:

    CarbInput ──► calculate_carbohydrates() ──► CarbResult

Policy version: carb-v1
"""

from app.nutrition.carbohydrate.calculator import (
    CARB_KCAL_PER_G,
    CARB_POLICY_VERSION,
    PROTEIN_KCAL_PER_G,
    calculate_carbohydrates,
)
from app.nutrition.carbohydrate.models import (
    CarbInput,
    CarbIssueCode,
    CarbResult,
    CarbStatus,
)

__all__ = [
    "CARB_KCAL_PER_G",
    "CARB_POLICY_VERSION",
    "PROTEIN_KCAL_PER_G",
    "CarbInput",
    "CarbIssueCode",
    "CarbResult",
    "CarbStatus",
    "calculate_carbohydrates",
]
