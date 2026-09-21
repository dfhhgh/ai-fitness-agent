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
from app.profile.policies import ALLOWED_UPDATE_PATHS
from app.profile.validator import (
    ProfileValidationError,
    validate_patch,
    validate_profile_patch,
)

__all__ = [
    "ALLOWED_UPDATE_PATHS",
    "ClientProfile",
    "GoalInfo",
    "HealthInfo",
    "InBodyInfo",
    "NutritionPreferences",
    "PersonalInfo",
    "ProfileMetadata",
    "ProfilePatch",
    "ProfileValidationError",
    "TrainingInfo",
    "validate_patch",
    "validate_profile_patch",
]
