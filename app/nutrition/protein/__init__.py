"""Protein Calculator — deterministic protein targets (protein-v1).

This package provides the isolated Layer A protein calculator for the
Nutrition Core pipeline, plus minimal Layer B adapter/binding helpers.

Responsibilities (Layer A):
- Daily protein target (integer grams) from current weight + goal
- Locked factors: MAINTENANCE 1.2; WEIGHT_LOSS / WEIGHT_GAIN /
  MUSCLE_GAIN 1.6 (MUSCLE_GAIN explicitly supported at 1.6)
- Engineering weight domain: 0.5 <= weight <= 500.0
- Rounding: Decimal ROUND_HALF_UP to integer grams (string Decimal
  boundary; never Python bankes rounding)
- Four-state status: OK, INCOMPLETE, INVALID, ERROR
- Strict contracts: strict=True, frozen=True, extra="forbid"

Does NOT (Layer A):
- Apply clinical g/kg safety thresholds (Layer B Safety Policy only —
  mathematically unreachable under locked factors)
- Screen medical conditions (renal, pregnancy, pediatric, eating
  disorder, hepatic — all Layer B)
- Compute or consume RMR, TDEE, calories, activity, FFM/InBody
- Call LLM, network, database, system clock, or random state

Layer B helpers exported here:
- map_goal_to_protein_goal: shared GoalType -> ProteinGoal (1:1)
- build_protein_input: extract/normalize weight + goal into ProteinInput
- bind_protein_target: bind protein_g into NutritionTargets only on OK

Architecture:

    ProteinInput ──► calculate_protein() ──► ProteinResult
                                                │
                          Layer B bind (OK only)│
                                                ▼
                                         NutritionTargets.protein_g

Policy version: protein-v1 (Rev 1.1)
"""

from app.nutrition.protein.calculator import (
    GOAL_FACTORS,
    PROTEIN_FACTOR_DEFAULT,
    PROTEIN_FACTOR_MAINTENANCE,
    PROTEIN_POLICY_VERSION,
    WEIGHT_DOMAIN_MAX_KG,
    WEIGHT_DOMAIN_MIN_KG,
    bind_protein_target,
    build_protein_input,
    calculate_protein,
    get_protein_factor,
    map_goal_to_protein_goal,
)
from app.nutrition.protein.models import (
    ProteinGoal,
    ProteinInput,
    ProteinIssueCode,
    ProteinResult,
    ProteinStatus,
)

__all__ = [
    "GOAL_FACTORS",
    "PROTEIN_FACTOR_DEFAULT",
    "PROTEIN_FACTOR_MAINTENANCE",
    "PROTEIN_POLICY_VERSION",
    "WEIGHT_DOMAIN_MAX_KG",
    "WEIGHT_DOMAIN_MIN_KG",
    "ProteinGoal",
    "ProteinInput",
    "ProteinIssueCode",
    "ProteinResult",
    "ProteinStatus",
    "bind_protein_target",
    "build_protein_input",
    "calculate_protein",
    "get_protein_factor",
    "map_goal_to_protein_goal",
]
