"""Weight Target Determination — deterministic weight targets
(weight-target-v1-rev1).

This package provides the isolated weight target determination layer
for the Nutrition Core pipeline.

Responsibilities:
- Reference weight range from age band + height (BMI-based reference
  bounds — NOT a medical diagnosis; NOT "ideal/healthy weight")
- Goals supported: WEIGHT_LOSS, WEIGHT_GAIN, MAINTENANCE only
  (MUSCLE_GAIN rejected at contract boundary — no V1 semantic)
- Initial weight milestone:
  - WEIGHT_LOSS: max(current * 0.95, reference_min) when no review gate
  - WEIGHT_GAIN: current * 1.05 when no review gate (engineering pacing
    decision, not clinical consensus; not clamped to reference_max)
  - MAINTENANCE: current weight
- Safety review gates (all evaluated; any hit → REVIEW_REQUIRED and
  milestone = None):
  - CURRENT_WEIGHT_BELOW_REFERENCE_MIN (loss)
  - OLDER_ADULT_LOW_BMI_WEIGHT_LOSS (loss, age >= 65 and BMI < 25)
  - HIGH_BMI_WEIGHT_GAIN_REQUEST (gain, BMI >= 30)
- User-target validation flags (informational only; never alter
  milestone math or reference range):
  - USER_TARGET_BELOW_REFERENCE_RANGE
  - USER_TARGET_ABOVE_REFERENCE_RANGE
- Output rounding: Decimal ROUND_HALF_UP to 1 decimal place only at
  serialization; internal math/comparisons use full float64 precision

Does NOT:
- Calculate or recalculate RMR, TDEE, calories, or macros
- Classify activity
- Diagnose medical conditions
- Produce a final "recommended target" / "ideal weight" field
- Include WHtR, waist, body-fat, InBody, pregnancy, eating-disorder,
  or medical-history logic (outside V1)
- Call LLM or external APIs
- Use system clock or random state
- Mutate RMR/TDEE/calorie/protein inputs (weight remains independent)

Architecture:

    WeightTargetInput
           │
           ▼
    determine_weight_targets()
           │
           ▼
    WeightTargetResult ──► NutritionAssessment ──► PlanningContext
                                              ──► LLM (read-only)

Policy version: weight-target-v1-rev1
"""

from app.nutrition.weight_target.calculator import (
    WEIGHT_LOSS_MILESTONE_FACTOR,
    WEIGHT_GAIN_MILESTONE_FACTOR,
    WEIGHT_TARGET_POLICY_VERSION,
    determine_weight_targets,
    _round_weight,
)
from app.nutrition.weight_target.models import (
    ReviewFlag,
    ValidationFlag,
    WeightTargetGoal,
    WeightTargetInput,
    WeightTargetResult,
    WeightTargetStatus,
)

# Resolve forward references now that WeightTargetResult exists so
# NutritionAssessment / NutritionPlanningContext can validate the
# optional weight_target field regardless of import order.
from app.nutrition.models import (  # noqa: E402
    NutritionAssessment,
    NutritionPlanningContext,
)

NutritionAssessment.model_rebuild()
NutritionPlanningContext.model_rebuild()

__all__ = [
    "WEIGHT_GAIN_MILESTONE_FACTOR",
    "WEIGHT_LOSS_MILESTONE_FACTOR",
    "WEIGHT_TARGET_POLICY_VERSION",
    "ReviewFlag",
    "ValidationFlag",
    "WeightTargetGoal",
    "WeightTargetInput",
    "WeightTargetResult",
    "WeightTargetStatus",
    "determine_weight_targets",
]
