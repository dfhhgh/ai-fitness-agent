"""RMR Calculator — deterministic Mifflin-St Jeor (rmr-v1).

This package provides the isolated RMR calculation layer
for the Nutrition Core pipeline.

Responsibilities:
- RMR calculation using Mifflin-St Jeor equation
- Input validation (missing data, gender, ranges, non-finite)
- Mapper boundary (extracts from NutritionAssessmentInput)
- Half-up rounding to integer kcal/day

Does NOT:
- Calculate TDEE
- Calculate calorie targets
- Calculate macronutrients
- Access activity factors
- Access InBody values
- Call LLM or external APIs

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

from app.nutrition.rmr.rmr_calculator import RMRCalculator, RMR_POLICY_VERSION
from app.nutrition.rmr.rmr_mapper import RMRMapper
from app.nutrition.rmr.rmr_models import (
    BiologicalSex,
    RMRInput,
    RMRMethod,
    RMRResult,
    RMRStatus,
)

__all__ = [
    "BiologicalSex",
    "RMRMapper",
    "RMRInput",
    "RMRMethod",
    "RMRCalculator",
    "RMRResult",
    "RMRStatus",
    "RMR_POLICY_VERSION",
]
