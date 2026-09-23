"""TDEE Calculator — deterministic TDEE calculation (tdee-v1).

This package provides the isolated TDEE calculation layer
for the Nutrition Core pipeline.

Responsibilities:
- TDEE = RMR × ActivityFactor
- Decimal arithmetic with ROUND_HALF_UP rounding
- Upstream status propagation (ERROR > INVALID > INCOMPLETE)
- Domain validation (field presence, numeric safety)

Does NOT:
- Calculate RMR
- Recalculate RMR
- Classify activity
- Select activity factor
- Apply calorie deficit/surplus
- Calculate macronutrients
- Access InBody directly
- Call LLM or external APIs
- Use system clock or random state

Architecture:

    ActivityClassificationResult ──┐
                                   ├──► TDEEInput
    RMRResult ─────────────────────┘
                                       │
                                       ▼
                                  TDEECalculator
                                       │
                                       ▼
                                  TDEEResult
                                       │
                                       ▼
                            Calorie Target Engine

Policy version: tdee-v1
"""

from app.nutrition.tdee.tdee_calculator import TDEE_POLICY_VERSION, calculate_tdee
from app.nutrition.tdee.tdee_models import (
    TDEEInput,
    TDEEResult,
    TDEEStatus,
    TDEETraceability,
)

__all__ = [
    "TDEEInput",
    "TDEEResult",
    "TDEEStatus",
    "TDEETraceability",
    "TDEE_POLICY_VERSION",
    "calculate_tdee",
]
