"""Interview controller coordinating one iteration of the onboarding conversation.

Orchestrates:
    user message -> LLM extraction -> ProfilePatch -> validate -> conflict detection
    -> merge if safe -> re-evaluate interview state.

Does NOT:
- call the LLM directly (uses injected ProfileExtractor)
- generate natural-language questions
- resolve conflicts
- calculate nutrition / workouts
- persist profiles
"""

from typing import Any, Dict, Union

from app.interview.models import InterviewTurnResult
from app.llm.extractor import ProfileExtractor
from app.profile.conflicts import detect_conflicts
from app.profile.merger import merge_profile
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState, get_interview_status


class InterviewController:
    """Orchestrates a single turn of the onboarding interview.

    Dependencies are injected, never created internally.
    """

    def __init__(self, extractor: ProfileExtractor) -> None:
        self._extractor = extractor

    def process_message(
        self,
        profile: ClientProfile,
        user_message: str,
    ) -> InterviewTurnResult:
        """Process one user message and return the turn result.

        Steps:
            1. Extract a ProfilePatch from the user message via the LLM extractor.
            2. Detect conflicts between the current profile and the patch.
            3. If conflicts exist: do NOT merge, return WAITING_FOR_CLARIFICATION.
            4. If no conflicts: merge the patch, re-evaluate interview state.

        Args:
            profile: The current client profile (must not be mutated).
            user_message: Raw text from the user.

        Returns:
            An InterviewTurnResult with the updated state and profile.

        Raises:
            LLMExtractionError: If the extractor cannot produce a valid patch.
            ProfileValidationError: If the patch fails deterministic validation.
        """
        # Step 1: Extract patch via LLM
        patch = self._extractor.extract(user_message)

        # Step 2: Detect conflicts against the ORIGINAL profile
        conflicts = detect_conflicts(profile, patch)

        # Step 3: If conflicts exist — do NOT merge
        if conflicts:
            status = get_interview_status(profile)
            return InterviewTurnResult(
                profile=profile,
                patch=patch,
                state=InterviewState.WAITING_FOR_CLARIFICATION,
                next_field=None,
                missing_fields=status.missing_fields,
                conflicts=conflicts,
                merged=False,
            )

        # Step 4: No conflicts — merge the patch
        updated_profile = merge_profile(profile, patch)

        # Step 5: Re-evaluate interview state on the updated profile
        status = get_interview_status(updated_profile)

        # Determine if any actual update occurred
        has_updates = bool(patch.updates)

        return InterviewTurnResult(
            profile=updated_profile,
            patch=patch,
            state=status.state,
            next_field=status.next_field,
            missing_fields=status.missing_fields,
            conflicts=[],
            merged=has_updates,
        )
