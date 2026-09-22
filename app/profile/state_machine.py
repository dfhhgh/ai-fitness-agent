"""Interview state machine coordinating the onboarding flow.

Determines current interview state, next required field, and whether the
profile is ready for plan generation. Read-only: never mutates the profile.

Does NOT call the LLM, generate questions, merge patches, or resolve conflicts.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from app.profile.conflicts import Conflict, detect_conflicts
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch


class InterviewState(Enum):
    """Current state of the onboarding interview."""

    INTERVIEWING = "INTERVIEWING"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    READY_FOR_PLAN = "READY_FOR_PLAN"


@dataclass(frozen=True)
class InterviewStatus:
    """Immutable snapshot of the interview state.

    Attributes:
        state: Current interview state.
        next_field: The next required field to request, or None.
        missing_fields: All required fields still missing from the profile.
        conflicts: Detected conflicts between the profile and an incoming patch.
    """

    state: InterviewState
    next_field: Optional[str]
    missing_fields: List[str]
    conflicts: List[Conflict]


def get_interview_status(
    profile: ClientProfile,
    patch: Union[ProfilePatch, Dict[str, Any], None] = None,
) -> InterviewStatus:
    """Determine the current interview status for a profile.

    Evaluates conflicts (if a patch is provided) and missing fields to decide
    the interview state. Never mutates the profile or merges the patch.

    Args:
        profile: The current client profile.
        patch: An optional incoming patch to check for conflicts.

    Returns:
        An InterviewStatus with the current state, next field, and details.

    Raises:
        ProfileValidationError: If the patch fails deterministic validation.
    """
    if patch is not None:
        conflicts = detect_conflicts(profile, patch)
    else:
        conflicts = []

    missing_fields = get_missing_fields(profile)

    if conflicts:
        state = InterviewState.WAITING_FOR_CLARIFICATION
        next_field = None
    elif missing_fields:
        state = InterviewState.INTERVIEWING
        next_field = missing_fields[0]
    else:
        state = InterviewState.READY_FOR_PLAN
        next_field = None

    return InterviewStatus(
        state=state,
        next_field=next_field,
        missing_fields=missing_fields,
        conflicts=conflicts,
    )
