"""Tests for app.interview.controller — InterviewController with a fake extractor.

All tests use a FakeExtractor to avoid any network calls or real LLM invocations.
"""

import pytest

from app.interview.controller import InterviewController
from app.interview.models import InterviewTurnResult
from app.llm.exceptions import LLMExtractionError
from app.profile.conflicts import Conflict
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState


# ---------------------------------------------------------------------------
# Fake extractor
# ---------------------------------------------------------------------------


class FakeExtractor:
    """Deterministic extractor that returns a predetermined ProfilePatch."""

    def __init__(self, patch: ProfilePatch) -> None:
        self._patch = patch

    def extract(self, user_message: str) -> ProfilePatch:  # noqa: D401
        return self._patch


class RaisingExtractor:
    """Extractor that always raises LLMExtractionError."""

    def extract(self, user_message: str) -> ProfilePatch:
        raise LLMExtractionError("LLM extraction failed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_patch() -> ProfilePatch:
    return ProfilePatch(updates={}, unknown_fields=[], conflicts=[])


def _patch(**updates: object) -> ProfilePatch:
    return ProfilePatch(updates=updates, unknown_fields=[], conflicts=[])


def _complete_profile() -> ClientProfile:
    """Return a fully complete onboarding profile."""
    return ClientProfile(
        personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
        goal={"type": "weight_loss"},
        training={
            "days_per_week": 4,
            "duration": "2 months",
            "experience": "beginner",
            "activity_description": "مكتبي",
        },
        health={"injuries": []},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInterviewController:
    """InterviewController orchestration test suite."""

    def test_1_empty_profile_basic_message(self):
        """1. Empty profile + basic user message -> patch extracted, merged, INTERVIEWING."""
        profile = ClientProfile()
        patch = _patch(**{"personal.age": 25, "personal.gender": "رجل"})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 25 سنة وراجل")

        assert isinstance(result, InterviewTurnResult)
        assert result.merged is True
        assert result.state == InterviewState.INTERVIEWING
        assert result.profile.personal.age == 25
        assert result.profile.personal.gender == "رجل"
        assert result.conflicts == []

    def test_2_single_field_update(self):
        """2. User message updates one field -> profile updated, original unchanged."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": None, "weight_kg": 85.0}
        )
        patch = _patch(**{"personal.height_cm": 175.0})
        controller = InterviewController(FakeExtractor(patch))

        original_dump = profile.model_dump()
        result = controller.process_message(profile, "طولي 175 سم")

        assert result.merged is True
        assert result.profile.personal.height_cm == 175.0
        # Original profile unchanged
        assert profile.model_dump() == original_dump

    def test_3_multi_field_message(self):
        """3. User message updates multiple fields -> all updates merged atomically."""
        profile = ClientProfile()
        patch = _patch(
            **{
                "personal.age": 25,
                "personal.gender": "رجل",
                "personal.height_cm": 175.0,
                "personal.weight_kg": 85.0,
            }
        )
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 25 سنة، راجل، طولي 175 ووزني 85")

        assert result.merged is True
        assert result.profile.personal.age == 25
        assert result.profile.personal.gender == "رجل"
        assert result.profile.personal.height_cm == 175.0
        assert result.profile.personal.weight_kg == 85.0

    def test_4_complete_profile_non_conflicting_patch(self):
        """4. Complete profile + non-conflicting patch -> READY_FOR_PLAN."""
        profile = _complete_profile()
        # personal.weight_kg is mutable, so updating it is not a conflict
        patch = _patch(**{"personal.weight_kg": 82.0})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "وزني 82 كيلو")

        assert result.merged is True
        assert result.state == InterviewState.READY_FOR_PLAN
        assert result.next_field is None
        assert result.profile.personal.weight_kg == 82.0

    def test_5_empty_patch_preserves_profile(self):
        """5. Empty patch -> original profile preserved, no merge, state from current profile."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "beginner",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        controller = InterviewController(FakeExtractor(_empty_patch()))
        original_dump = profile.model_dump()

        result = controller.process_message(profile, "مرحبا")

        assert result.merged is False
        assert result.profile.model_dump() == original_dump
        assert result.state == InterviewState.READY_FOR_PLAN

    def test_6_unknown_only_patch(self):
        """6. Unknown-only patch -> original profile preserved, no merge."""
        profile = ClientProfile(personal={"age": 25})
        patch = ProfilePatch(
            updates={},
            unknown_fields=["personal.age"],
            conflicts=[],
        )
        controller = InterviewController(FakeExtractor(patch))
        original_dump = profile.model_dump()

        result = controller.process_message(profile, "مش عارف وزني")

        assert result.merged is False
        assert result.profile.model_dump() == original_dump

    def test_7_existing_contradiction(self):
        """7. Existing contradiction -> WAITING_FOR_CLARIFICATION, profile unchanged, merged=False."""
        profile = ClientProfile(personal={"age": 25})
        patch = _patch(**{"personal.age": 26})
        controller = InterviewController(FakeExtractor(patch))
        original_dump = profile.model_dump()

        result = controller.process_message(profile, "لا أنا 26 سنة")

        assert result.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert result.merged is False
        assert result.next_field is None
        assert result.profile.model_dump() == original_dump
        assert len(result.conflicts) == 1
        assert result.conflicts[0].path == "personal.age"

    def test_8_conflict_plus_valid_update_no_merge(self):
        """8. Conflict + another valid update -> NOTHING merged, atomicity preserved."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": None, "weight_kg": 85.0}
        )
        # Age conflicts, height is new (None -> value is NOT a conflict)
        # But atomicity means nothing merges
        patch = _patch(**{"personal.age": 26, "personal.height_cm": 180.0})
        controller = InterviewController(FakeExtractor(patch))
        original_dump = profile.model_dump()

        result = controller.process_message(profile, "أنا 26 سنة وطولي 180")

        assert result.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert result.merged is False
        assert len(result.conflicts) == 1
        assert result.conflicts[0].path == "personal.age"
        # Height must NOT have been merged
        assert result.profile.model_dump() == original_dump

    def test_9_no_conflict_patch_merged(self):
        """9. No conflict -> patch is merged."""
        profile = ClientProfile(personal={"age": 25})
        patch = _patch(**{"personal.height_cm": 175.0})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "طولي 175 سم")

        assert result.merged is True
        assert result.profile.personal.height_cm == 175.0
        assert result.profile.personal.age == 25  # preserved

    def test_10_profile_immutability_with_merge(self):
        """10. Original profile immutability with successful merge."""
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": None, "weight_kg": 85.0}
        )
        patch = _patch(**{"personal.height_cm": 175.0})
        controller = InterviewController(FakeExtractor(patch))

        before = profile.model_dump()
        controller.process_message(profile, "طولي 175 سم")
        after = profile.model_dump()

        assert before == after

    def test_11_profile_immutability_with_conflict(self):
        """11. Original profile immutability with conflict."""
        profile = ClientProfile(personal={"age": 25})
        patch = _patch(**{"personal.age": 26})
        controller = InterviewController(FakeExtractor(patch))

        before = profile.model_dump()
        controller.process_message(profile, "أنا 26 سنة")
        after = profile.model_dump()

        assert before == after

    def test_12_next_field_from_get_interview_status(self):
        """12. next_field comes from get_interview_status(), not manually calculated."""
        profile = ClientProfile(personal={"gender": "رجل", "age": 25})
        patch = _patch(**{"personal.height_cm": 175.0})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "طولي 175 سم")

        # After merge, profile has gender, age, height_cm — missing weight_kg next
        from app.profile.missing_fields import get_missing_fields
        expected_missing = get_missing_fields(result.profile)
        assert result.missing_fields == expected_missing
        assert result.next_field == expected_missing[0] if expected_missing else None

    def test_13_llm_conflicts_ignored_no_deterministic_conflict(self):
        """13. LLM-provided conflicts are ignored if deterministic detector finds none."""
        profile = ClientProfile(personal={"weight_kg": 85.0})
        # LLM claims a conflict but weight_kg is mutable — deterministic detector finds none
        patch = ProfilePatch(
            updates={"personal.weight_kg": 82.0},
            unknown_fields=[],
            conflicts=[{"field": "personal.weight_kg", "values": [85, 82]}],
        )
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "وزني 82 كيلو")

        assert result.merged is True
        assert result.conflicts == []

    def test_14_llm_conflicts_cannot_suppress_real_conflict(self):
        """14. LLM-provided conflicts cannot suppress a real deterministic conflict."""
        profile = ClientProfile(personal={"age": 25})
        # LLM says conflicts=[] but deterministic detector should find the age contradiction
        patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 26 سنة")

        assert result.merged is False
        assert result.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert len(result.conflicts) == 1
        assert result.conflicts[0].path == "personal.age"

    def test_15_extractor_error_propagates(self):
        """15. Extractor errors propagate."""
        profile = ClientProfile()
        controller = InterviewController(RaisingExtractor())

        with pytest.raises(LLMExtractionError, match="LLM extraction failed"):
            controller.process_message(profile, "أي رسالة")

    def test_16_validation_error_propagates(self):
        """16. Validation errors propagate."""
        profile = ClientProfile()
        # Patch with an invalid path that will fail validation inside detect_conflicts
        bad_patch = ProfilePatch(
            updates={"invalid.path": "bad"},
            unknown_fields=[],
            conflicts=[],
        )
        controller = InterviewController(FakeExtractor(bad_patch))

        from app.profile.validator import ProfileValidationError

        with pytest.raises(ProfileValidationError):
            controller.process_message(profile, "test")

    def test_17_result_is_frozen(self):
        """17. Returned InterviewTurnResult is frozen."""
        profile = ClientProfile()
        patch = _patch(**{"personal.age": 25})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 25 سنة")

        with pytest.raises(AttributeError):
            result.merged = False

    def test_18_empty_profile_multi_field_advances(self):
        """18. Empty profile + multi-field message advances to the correct next field."""
        profile = ClientProfile()
        patch = _patch(
            **{
                "personal.gender": "رجل",
                "personal.age": 25,
                "personal.height_cm": 175.0,
                "personal.weight_kg": 85.0,
            }
        )
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا راجل 25 سنة طولي 175 وزني 85")

        assert result.merged is True
        assert result.state == InterviewState.INTERVIEWING
        # After gender, age, height, weight — next missing is health.injuries
        assert result.next_field == "health.injuries"

    def test_19_empty_patch_incomplete_profile(self):
        """19. Empty patch on incomplete profile -> INTERVIEWING."""
        profile = ClientProfile(personal={"age": 25})
        controller = InterviewController(FakeExtractor(_empty_patch()))

        result = controller.process_message(profile, "مرحبا")

        assert result.merged is False
        assert result.state == InterviewState.INTERVIEWING
        assert result.next_field == "personal.gender"

    def test_20_empty_patch_complete_profile(self):
        """20. Empty patch on complete profile -> READY_FOR_PLAN."""
        profile = _complete_profile()
        controller = InterviewController(FakeExtractor(_empty_patch()))

        result = controller.process_message(profile, "تمام")

        assert result.merged is False
        assert result.state == InterviewState.READY_FOR_PLAN
        assert result.next_field is None

    def test_21_partial_conflict_no_partial_merge(self):
        """21. Partial conflict patch does not partially merge."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0}
        )
        # age conflicts, height_cm is new, weight_kg is mutable update
        patch = _patch(**{"personal.age": 26, "personal.height_cm": 180.0, "personal.weight_kg": 82.0})
        controller = InterviewController(FakeExtractor(patch))
        original_dump = profile.model_dump()

        result = controller.process_message(profile, "أنا 26 سنة وطولي 180 ووزني 82")

        assert result.merged is False
        assert result.profile.model_dump() == original_dump

    def test_22_successful_patch_returns_empty_conflicts(self):
        """22. Successful patch returns conflicts=[]."""
        profile = ClientProfile(personal={"age": 25})
        patch = _patch(**{"personal.height_cm": 175.0})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "طولي 175 سم")

        assert result.merged is True
        assert result.conflicts == []

    def test_23_conflict_patch_returns_detected_conflicts(self):
        """23. Conflict patch returns the detected conflicts."""
        profile = ClientProfile(personal={"age": 25, "gender": "رجل"})
        patch = _patch(**{"personal.age": 26, "personal.gender": "امرأة"})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 26 سنة وست")

        assert result.merged is False
        assert len(result.conflicts) == 2
        paths = {c.path for c in result.conflicts}
        assert "personal.age" in paths
        assert "personal.gender" in paths

    def test_24_result_patch_is_extracted_patch(self):
        """24. Result.patch is exactly the extracted patch."""
        profile = ClientProfile()
        patch = _patch(**{"personal.age": 25})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 25 سنة")

        assert result.patch is patch

    def test_25_weight_update_no_conflict(self):
        """25. Weight (mutable field) update never conflicts."""
        profile = ClientProfile(personal={"weight_kg": 90.0})
        patch = _patch(**{"personal.weight_kg": 82.0})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "وزني 82 كيلو")

        assert result.merged is True
        assert result.conflicts == []
        assert result.profile.personal.weight_kg == 82.0

    def test_26_result_missing_fields_match_profile(self):
        """26. result.missing_fields matches get_missing_fields on the result profile."""
        profile = ClientProfile(personal={"gender": "رجل"})
        patch = _patch(**{"personal.age": 25})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا 25 سنة")

        assert result.missing_fields == get_missing_fields(result.profile)

    def test_27_interviewing_state_next_field_not_none(self):
        """27. When state is INTERVIEWING, next_field is the first missing field."""
        profile = ClientProfile()
        patch = _patch(**{"personal.gender": "رجل"})
        controller = InterviewController(FakeExtractor(patch))

        result = controller.process_message(profile, "أنا راجل")

        assert result.state == InterviewState.INTERVIEWING
        assert result.next_field is not None
        assert result.next_field in result.missing_fields
        assert result.next_field == result.missing_fields[0]
