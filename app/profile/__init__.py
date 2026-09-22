"""Client Profile and ProfilePatch module.

Contains models, schema contracts, validation, merging, conflict detection,
and state machine definitions.
"""

from app.profile.conflicts import Conflict, detect_conflicts
from app.profile.missing_fields import (
    REQUIRED_ONBOARDING_FIELDS,
    get_missing_fields,
    is_profile_complete,
)
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
from app.profile.merger import (
    ProfileMerger,
    merge_profile,
    merge_profile_patch,
)
from app.profile.policies import (
    ALLOWED_UPDATE_PATHS,
    CONTRADICTION_SENSITIVE_FIELDS,
    LIST_FIELDS,
    MUTABLE_FIELDS,
)
from app.profile.state_machine import (
    InterviewState,
    InterviewStatus,
    get_interview_status,
)
from app.profile.validator import (
    ProfileValidationError,
    validate_patch,
    validate_profile_patch,
)

__all__ = [
    "ALLOWED_UPDATE_PATHS",
    "CONTRADICTION_SENSITIVE_FIELDS",
    "ClientProfile",
    "Conflict",
    "GoalInfo",
    "HealthInfo",
    "InBodyInfo",
    "InterviewState",
    "InterviewStatus",
    "LIST_FIELDS",
    "MUTABLE_FIELDS",
    "NutritionPreferences",
    "PersonalInfo",
    "ProfileMerger",
    "ProfileMetadata",
    "ProfilePatch",
    "ProfileValidationError",
    "REQUIRED_ONBOARDING_FIELDS",
    "TrainingInfo",
    "detect_conflicts",
    "get_interview_status",
    "get_missing_fields",
    "is_profile_complete",
    "merge_profile",
    "merge_profile_patch",
    "validate_patch",
    "validate_profile_patch",
]
