"""Activity classification policy, factor lookup, and classifier.

This package provides the deterministic activity classification layer
for the Nutrition Core pipeline.

Responsibilities:
- Activity factor lookup by category
- Occupation baseline scores
- Exercise intensity weights
- WES upgrade thresholds
- Policy constants (factors, baselines, weights, version)
- Classification logic (Revision 3)

Does NOT:
- Interpret Egyptian Arabic
- Inspect free-form text
- Calculate nutrition
- Calculate TDEE
- Access ClientProfile directly

Architecture:

    ClientProfile.training fields
            ↓
    Mapper (normalizes to structured enums)
            ↓
    ActivityClassificationInput
            ↓
    ActivityClassifier (deterministic)
            ↓
    ActivityClassificationResult
            ↓
    ActivityCategory → get_activity_factor() → float
"""

from app.nutrition.activity.activity_classifier import ActivityClassifier
from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.activity.activity_policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    INTENSITY_WEIGHTS,
    OCCUPATION_BASELINES,
    WES_UPGRADE_THRESHOLDS,
    get_activity_factor,
)

__all__ = [
    "ACTIVITY_FACTORS",
    "ACTIVITY_POLICY_VERSION",
    "INTENSITY_WEIGHTS",
    "OCCUPATION_BASELINES",
    "WES_UPGRADE_THRESHOLDS",
    "ActivityClassificationInput",
    "ActivityClassificationResult",
    "ActivityClassifier",
    "get_activity_factor",
]
