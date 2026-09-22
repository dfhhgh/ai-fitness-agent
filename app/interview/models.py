"""Immutable result model for a single interview turn."""

from dataclasses import dataclass
from typing import List

from app.profile.conflicts import Conflict
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState


@dataclass(frozen=True)
class InterviewTurnResult:
    """Frozen result of processing one user message through the interview controller.

    Attributes:
        profile: The resulting profile after a successful non-conflicting merge.
            Equal to the original profile when no merge occurred.
        patch: The deterministic ProfilePatch extracted from the user message.
        state: Current InterviewState after processing the turn.
        next_field: Next missing field path when state == INTERVIEWING, else None.
        missing_fields: All required fields still missing from the returned profile.
        conflicts: Deterministic conflicts detected against the ORIGINAL profile.
            Empty list when no conflicts exist.
        merged: True only if the patch was safely merged into the profile.
    """

    profile: ClientProfile
    patch: ProfilePatch
    state: InterviewState
    next_field: str | None
    missing_fields: List[str]
    conflicts: List[Conflict]
    merged: bool
