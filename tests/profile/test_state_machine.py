"""Tests for app.profile.state_machine -- interview state machine."""

import pytest

from app.profile.missing_fields import REQUIRED_ONBOARDING_FIELDS
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import (
    InterviewState,
    InterviewStatus,
    get_interview_status,
)
from app.profile.validator import ProfileValidationError


class TestGetInterviewStatus:
    """Deterministic interview state machine test suite."""

    def test_1_empty_profile_interviewing_gender(self):
        """1. Empty profile -> INTERVIEWING, next_field == personal.gender."""
        profile = ClientProfile()
        status = get_interview_status(profile)
        assert status.state == InterviewState.INTERVIEWING
        assert status.next_field == "personal.gender"
        assert status.missing_fields == REQUIRED_ONBOARDING_FIELDS
        assert status.conflicts == []

    def test_2_partial_profile_interviewing_first_missing(self):
        """2. Partially completed profile -> INTERVIEWING, next_field == first missing."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.INTERVIEWING
        assert status.next_field == "personal.height_cm"
        assert "personal.height_cm" in status.missing_fields

    def test_3_fully_complete_profile_ready(self):
        """3. Fully completed profile -> READY_FOR_PLAN."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.next_field is None
        assert status.missing_fields == []
        assert status.conflicts == []

    def test_4_missing_fields_deterministic_order(self):
        """4. Missing fields are returned in deterministic required order."""
        profile = ClientProfile()
        status = get_interview_status(profile)
        assert status.missing_fields == REQUIRED_ONBOARDING_FIELDS
        assert status.missing_fields[0] == "personal.gender"

    def test_5_complete_profile_no_patch_ready(self):
        """5. Complete profile with no patch -> READY_FOR_PLAN."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 30, "height_cm": 170.0, "weight_kg": 70.0},
            goal={"type": "maintenance"},
            training={
                "days_per_week": 3,
                "duration": "45 min",
                "experience": "beginner",
                "activity_description": "home workouts",
            },
            health={"injuries": []},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.next_field is None

    def test_6_existing_contradiction_waiting(self):
        """6. Contradiction between profile and patch -> WAITING_FOR_CLARIFICATION."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert status.next_field is None
        assert len(status.conflicts) == 1
        assert status.conflicts[0].path == "personal.age"

    def test_7_conflict_takes_priority_over_missing(self):
        """7. Conflict takes priority even if fields are missing."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25},
        )
        patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert status.next_field is None
        assert "personal.height_cm" in status.missing_fields
        assert len(status.conflicts) == 1

    def test_8_conflict_with_complete_profile(self):
        """8. Conflict on complete profile -> WAITING_FOR_CLARIFICATION."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={"personal.gender": "امرأة"},
            unknown_fields=[],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert status.next_field is None
        assert len(status.conflicts) == 1
        assert status.conflicts[0].path == "personal.gender"

    def test_9_non_conflicting_patch_no_merge(self):
        """9. Non-conflicting patch does not merge. Original profile unchanged."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        original_dump = profile.model_dump()
        patch = ProfilePatch(
            updates={"personal.weight_kg": 82.0},
            unknown_fields=[],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.conflicts == []
        # Profile must not be mutated
        assert profile.model_dump() == original_dump

    def test_10_empty_patch_behaves_like_no_patch(self):
        """10. Empty patch behaves like patch=None."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={},
            unknown_fields=[],
            conflicts=[],
        )
        status_no_patch = get_interview_status(profile)
        status_empty_patch = get_interview_status(profile, patch)
        assert status_no_patch.state == status_empty_patch.state
        assert status_no_patch.next_field == status_empty_patch.next_field
        assert status_no_patch.missing_fields == status_empty_patch.missing_fields
        assert status_no_patch.conflicts == status_empty_patch.conflicts

    def test_11_llm_provided_conflicts_ignored(self):
        """11. LLM-provided conflicts list is ignored. Deterministic detector is authoritative."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        # LLM claims conflict but deterministic detector should not find one (same value)
        patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[{"path": "personal.age", "reason": "llm_says_so"}],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.conflicts == []

    def test_12_unknown_fields_no_wait(self):
        """12. Unknown fields do not cause WAITING_FOR_CLARIFICATION."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={},
            unknown_fields=["random.field", "another.field"],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.conflicts == []

    def test_13_patch_validation_error_propagates(self):
        """13. Invalid patch raises ProfileValidationError."""
        profile = ClientProfile()
        invalid_patch = {
            "updates": {"invalid.path": "value"},
            "unknown_fields": [],
            "conflicts": [],
        }
        with pytest.raises(ProfileValidationError):
            get_interview_status(profile, invalid_patch)

    def test_14_injuries_none_interview_continues(self):
        """14. injuries=None means interview continues (field is missing)."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": None},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.INTERVIEWING
        assert status.next_field == "health.injuries"
        assert "health.injuries" in status.missing_fields

    def test_15_injuries_empty_list_complete(self):
        """15. injuries=[] means injuries field is complete."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert "health.injuries" not in status.missing_fields

    def test_16_ready_only_when_no_conflicts_and_no_missing(self):
        """16. READY_FOR_PLAN only when no conflicts AND no missing required fields."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        status = get_interview_status(profile)
        assert status.state == InterviewState.READY_FOR_PLAN
        assert status.missing_fields == []
        assert status.conflicts == []

    def test_17_next_field_none_for_ready(self):
        """17. next_field is None for READY_FOR_PLAN."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        status = get_interview_status(profile)
        assert status.next_field is None

    def test_18_next_field_none_for_waiting(self):
        """18. next_field is None for WAITING_FOR_CLARIFICATION."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        status = get_interview_status(profile, patch)
        assert status.next_field is None

    def test_19_profile_immutability_without_patch(self):
        """19. Profile is not mutated when called without a patch."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        before = profile.model_dump()
        get_interview_status(profile)
        after = profile.model_dump()
        assert before == after

    def test_20_profile_immutability_with_patch(self):
        """20. Profile is not mutated when called with a patch."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "60 min",
                "experience": "intermediate",
                "activity_description": " gym",
            },
            health={"injuries": []},
        )
        patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        before = profile.model_dump()
        get_interview_status(profile, patch)
        after = profile.model_dump()
        assert before == after

    def test_interview_status_is_frozen_dataclass(self):
        """InterviewStatus is a frozen (immutable) dataclass."""
        profile = ClientProfile()
        status = get_interview_status(profile)
        with pytest.raises(AttributeError):
            status.state = InterviewState.READY_FOR_PLAN

    def test_interview_state_enum_values(self):
        """InterviewState enum has the expected string values."""
        assert InterviewState.INTERVIEWING.value == "INTERVIEWING"
        assert InterviewState.WAITING_FOR_CLARIFICATION.value == "WAITING_FOR_CLARIFICATION"
        assert InterviewState.READY_FOR_PLAN.value == "READY_FOR_PLAN"
