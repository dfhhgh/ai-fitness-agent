"""Fat Calculator — deterministic fat targets (fat-v1-rev1).

This package provides the isolated Layer A fat calculator for the
Nutrition Core pipeline, plus minimal Layer B adapter/binding helpers.

Responsibilities (Layer A):
- Daily fat target (integer grams) from target calories + goal
- Goal-invariant 25% energy fraction (midpoint of 20–35% AMDR)
- Atwater conversion factor 9 kcal/g
- Calorie engineering domain: target_calories >= 1
- Rounding: Decimal ROUND_HALF_UP to integer grams (string Decimal
  boundary; never Python banker's rounding)
- effective_fat_percentage quantized to 6 decimal places (ROUND_HALF_UP)
- Four-state status: OK, INCOMPLETE, INVALID, ERROR
- Strict contracts: strict=True, frozen=True, extra="forbid"

Does NOT (Layer A):
- Enforce a body-weight minimum fat floor (Layer B Safety Policy only)
- Screen medical conditions (lipids, pancreatitis, gallbladder,
  pediatric, pregnancy/lactation — all Layer B)
- Compute or consume RMR, TDEE, calories, activity, protein/carbs
- Allocate fatty acid subtypes (saturated/MUFA/PUFA/Omega — downstream)
- Call LLM, network, database, system clock, or random state

Layer B helpers exported here:
- map_goal_to_fat_goal: shared GoalType -> FatGoal (1:1)
- build_fat_input: extract/normalize calories + goal into FatInput
- bind_fat_target: bind fat_g into NutritionTargets only on OK

Architecture:

    FatInput ──► calculate_fat() ──► FatResult
                                         │
                     Layer B bind (OK only)│
                                           ▼
                                    NutritionTargets.fat_g

Policy version: fat-v1-rev1
"""

from app.nutrition.fat.calculator import (
    ATWATER_FACTOR,
    FAT_ENERGY_FRACTION,
    FAT_POLICY_VERSION,
    FAT_FRACTION_DECIMAL,
    PERCENTAGE_QUANTUM,
    TARGET_CALORIES_DOMAIN_MIN,
    bind_fat_target,
    build_fat_input,
    calculate_fat,
    get_fat_energy_fraction,
    map_goal_to_fat_goal,
)
from app.nutrition.fat.models import (
    FatGoal,
    FatInput,
    FatIssueCode,
    FatResult,
    FatStatus,
)

__all__ = [
    "ATWATER_FACTOR",
    "FAT_ENERGY_FRACTION",
    "FAT_FRACTION_DECIMAL",
    "FAT_POLICY_VERSION",
    "PERCENTAGE_QUANTUM",
    "TARGET_CALORIES_DOMAIN_MIN",
    "FatGoal",
    "FatInput",
    "FatIssueCode",
    "FatResult",
    "FatStatus",
    "bind_fat_target",
    "build_fat_input",
    "calculate_fat",
    "get_fat_energy_fraction",
    "map_goal_to_fat_goal",
]
