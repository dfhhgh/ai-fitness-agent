"""Client Profile and ProfilePatch module.

Contains models, schema contracts, validation, merging, and state machine definitions.
"""

from app.profile.models import (
    ClientProfile,
    GoalInfo,
    HealthInfo,
    InBodyInfo,
    NutritionPreferences,
    PersonalInfo,
    ProfileMetadata,
    ProfilePatch,
    TrainingInfo,
)

__all__ = [
    "ClientProfile",
    "GoalInfo",
    "HealthInfo",
    "InBodyInfo",
    "NutritionPreferences",
    "PersonalInfo",
    "ProfileMetadata",
    "ProfilePatch",
    "TrainingInfo",
]
