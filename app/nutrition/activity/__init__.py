"""Activity classification policy and factor lookup.

This package provides the deterministic activity classification layer
for the Nutrition Core pipeline.

Responsibilities:
- Activity factor lookup by category
- Policy constants (factors, version)
- Classification logic (PENDING — see classifier.py)

Does NOT:
- Interpret Egyptian Arabic
- Inspect free-form text
- Calculate nutrition
- Calculate TDEE
- Access ClientProfile directly

Architecture:

ClientProfile.training.activity_description
        ↓
future normalization/classification boundary
        ↓
structured activity inputs
        ↓
ActivityClassifier (PENDING — policy ambiguous)
        ↓
ActivityCategory
        ↓
get_activity_factor() → float
"""

from app.nutrition.activity.classifier import ActivityClassifier
from app.nutrition.activity.policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    get_activity_factor,
)

__all__ = [
    "ACTIVITY_FACTORS",
    "ACTIVITY_POLICY_VERSION",
    "ActivityClassifier",
    "get_activity_factor",
]
