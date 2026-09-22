"""End-to-end tests verifying the complete clarification lifecycle.

Tests the integrated flow:
    Conflict → ClarificationGenerator → User Answer → ClarificationResolver
    → ProfilePatch → validate_profile_patch → ProfileMerger → Updated Profile

Does NOT call the LLM. Uses deterministic components only.
"""

import pytest

from app.interview.clarification_generator import ClarificationGenerator
from app.interview.clarification_resolver import (
    REASON_AMBIGUOUS,
    REASON_INVALID,
    REASON_NO_CANDIDATE,
    ClarificationResolver,
)
from app.profile.conflicts import Conflict, detect_conflicts
from app.profile.merger import ProfileMerger
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState, get_interview_status
from app.profile.validator import ProfileValidationError, validate_profile_patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(**overrides) -> ClientProfile:
    """Create a realistic profile with sensible defaults, overridden as needed."""
    defaults = dict(
        client_id="test-client",
        personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
        goal={"type": "weight_loss", "target_weight_kg": 75.0, "weight_change_target_kg": 10.0},
        training={
            "days_per_week": 4,
            "duration": "2 months",
            "experience": "beginner",
            "activity_description": "مكتبي",
        },
        health={"injuries": []},
    )
    defaults.update(overrides)
    return ClientProfile(**defaults)


def _snapshot(profile: ClientProfile) -> dict:
    """Capture a deep snapshot of every field for immutability checks."""
    return {
        "personal.age": profile.personal.age,
        "personal.gender": profile.personal.gender,
        "personal.height_cm": profile.personal.height_cm,
        "personal.weight_kg": profile.personal.weight_kg,
        "goal.type": profile.goal.type,
        "goal.target_weight_kg": profile.goal.target_weight_kg,
        "goal.weight_change_target_kg": profile.goal.weight_change_target_kg,
        "training.days_per_week": profile.training.days_per_week,
        "training.duration": profile.training.duration,
        "training.experience": profile.training.experience,
        "training.activity_description": profile.training.activity_description,
        "health.injuries": list(profile.health.injuries) if profile.health.injuries is not None else None,
    }


def _assert_profiles_differ_only(profile_before, profile_after, changed_path):
    """Assert that profile_after differs from profile_before ONLY at changed_path."""
    before_snap = _snapshot(profile_before)
    after_snap = _snapshot(profile_after)
    for key in before_snap:
        if key == changed_path:
            assert before_snap[key] != after_snap[key], (
                f"Expected {key} to change, but it remained {before_snap[key]}"
            )
        else:
            assert before_snap[key] == after_snap[key], (
                f"Unexpected change at {key}: {before_snap[key]!r} → {after_snap[key]!r}"
            )


def _e2e_resolve(profile, conflict, user_answer):
    """Run the full clarification lifecycle and return (resolution, merged_profile, status).

    Steps:
        1. Generate clarification question (verify it works).
        2. Resolve user answer.
        3. If resolved: validate patch, merge, re-evaluate status.
        4. If unresolved: return profile unchanged, current status.
    """
    # Step 1: Generate question
    generator = ClarificationGenerator()
    question = generator.generate(conflict)
    assert isinstance(question, str) and question.strip()

    # Step 2: Resolve
    resolver = ClarificationResolver()
    resolution = resolver.resolve(conflict, user_answer)

    # Step 3: Validate + merge or skip
    if resolution.resolved:
        validate_profile_patch(resolution.patch)
        merged_profile = ProfileMerger.merge(profile, resolution.patch)
        status = get_interview_status(merged_profile)
    else:
        merged_profile = profile
        status = get_interview_status(profile)

    return resolution, merged_profile, status


# ---------------------------------------------------------------------------
# 2. Happy Path — Existing Value Is Correct
# ---------------------------------------------------------------------------

class TestHappyPathExistingValue:
    """User confirms the existing value is correct."""

    def test_age_existing_value_preserved(self):
        """Age conflict resolved to existing value — profile unchanged."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"
        assert conflicts[0].existing_value == 25
        assert conflicts[0].incoming_value == 26

        resolution, merged, status = _e2e_resolve(
            profile, conflicts[0], "القديم هو الصح"
        )

        assert resolution.resolved is True
        assert resolution.patch.updates["personal.age"] == 25
        assert merged.personal.age == 25
        _assert_profiles_differ_only(profile, merged, None)  # nothing changed
        assert status.missing_fields == get_missing_fields(profile)

    def test_height_existing_value_preserved(self):
        """Height conflict resolved to existing value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.height_cm": 180.0})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1

        resolution, merged, status = _e2e_resolve(
            profile, conflicts[0], "القديم هو الصح"
        )

        assert resolution.resolved is True
        assert merged.personal.height_cm == 175.0
        _assert_profiles_differ_only(profile, merged, None)


# ---------------------------------------------------------------------------
# 3. Happy Path — Incoming Value Is Correct
# ---------------------------------------------------------------------------

class TestHappyPathIncomingValue:
    """User confirms the incoming value is correct."""

    def test_age_incoming_value_merged(self):
        """Age conflict resolved to incoming value — profile updates."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].existing_value == 25
        assert conflicts[0].incoming_value == 26

        resolution, merged, status = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert resolution.patch.updates["personal.age"] == 26
        assert merged.personal.age == 26
        _assert_profiles_differ_only(profile, merged, "personal.age")
        assert status.missing_fields == get_missing_fields(profile)

    def test_height_incoming_value_merged(self):
        """Height conflict resolved to incoming value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.height_cm": 180.0})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.personal.height_cm == 180.0
        _assert_profiles_differ_only(profile, merged, "personal.height_cm")


# ---------------------------------------------------------------------------
# 4. Explicit Value Answer
# ---------------------------------------------------------------------------

class TestExplicitValueAnswer:
    """User provides a new explicit value not equal to either existing or incoming."""

    def test_age_explicit_new_value(self):
        """User says '27 سنة' — resolves to 27, not 25 or 26."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "أنا عندي 27 سنة"
        )

        assert resolution.resolved is True
        assert resolution.patch.updates["personal.age"] == 27
        assert merged.personal.age == 27
        _assert_profiles_differ_only(profile, merged, "personal.age")

    def test_height_explicit_new_value(self):
        """User says '178 سم' — resolves to 178."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.height_cm": 180.0})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "178 سم"
        )

        assert resolution.resolved is True
        assert merged.personal.height_cm == 178.0
        _assert_profiles_differ_only(profile, merged, "personal.height_cm")


# ---------------------------------------------------------------------------
# 5. Multi-Numeric Semantic Boundary
# ---------------------------------------------------------------------------

class TestMultiNumericSemanticBoundary:
    """Numbers from the wrong field must not resolve the conflict."""

    def test_age_conflict_with_days_answer(self):
        """'أنا بتمرن 4 أيام' must NOT resolve age conflict."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "أنا بتمرن 4 أيام في الأسبوع"
        )

        assert resolution.resolved is False
        assert merged.personal.age == 25
        _assert_profiles_differ_only(profile, merged, None)

    def test_days_conflict_with_age_answer(self):
        """'أنا 26 سنة' must NOT resolve days_per_week conflict."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"training.days_per_week": 3})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].path == "training.days_per_week"

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "أنا 26 سنة"
        )

        assert resolution.resolved is False
        assert merged.training.days_per_week == 4
        _assert_profiles_differ_only(profile, merged, None)


# ---------------------------------------------------------------------------
# 6. Ambiguous Reference
# ---------------------------------------------------------------------------

class TestAmbiguousReference:
    """Both existing and incoming referenced in the same message."""

    def test_both_references_ambiguous(self):
        """'القديم لا، الجديد هو الصح' → unresolved."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "القديم لا، الجديد هو الصح"
        )

        assert resolution.resolved is False
        assert resolution.reason == REASON_AMBIGUOUS
        assert merged.personal.age == 25
        _assert_profiles_differ_only(profile, merged, None)

    def test_both_references_reversed(self):
        """'الجديد لا، القديم هو الصح' → unresolved."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد لا، القديم هو الصح"
        )

        assert resolution.resolved is False
        assert resolution.reason == REASON_AMBIGUOUS


# ---------------------------------------------------------------------------
# 7. Invalid Value
# ---------------------------------------------------------------------------

class TestInvalidValue:
    """User provides a value that fails validation."""

    def test_age_invalid_negative(self):
        """'عمري -5 سنة' → unresolved (validation rejects negative age)."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "عمري -5 سنة"
        )

        assert resolution.resolved is False
        assert merged.personal.age == 25
        _assert_profiles_differ_only(profile, merged, None)

    def test_days_invalid_over_seven(self):
        """'10 أيام' → unresolved (days must be 0-7)."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"training.days_per_week": 2})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "10 أيام"
        )

        assert resolution.resolved is False
        assert merged.training.days_per_week == 4
        _assert_profiles_differ_only(profile, merged, None)


# ---------------------------------------------------------------------------
# 8. Unrelated Answer
# ---------------------------------------------------------------------------

class TestUnrelatedAnswer:
    """User provides an answer that does not address the conflict."""

    def test_age_conflict_unrelated(self):
        """'أنا بتمرن 4 أيام' does not resolve age conflict."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "أنا بتمرن 4 أيام في الأسبوع"
        )

        assert resolution.resolved is False
        assert merged.personal.age == 25
        _assert_profiles_differ_only(profile, merged, None)

    def test_empty_message(self):
        """Empty message → unresolved."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(profile, conflicts[0], "")

        assert resolution.resolved is False
        assert merged.personal.age == 25


# ---------------------------------------------------------------------------
# 9. Text Field Clarification
# ---------------------------------------------------------------------------

class TestTextFieldClarification:
    """Clarification for text-based contradiction-sensitive fields."""

    def test_experience_incoming(self):
        """Experience conflict resolved to incoming value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"training.experience": "intermediate"})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].path == "training.experience"

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.training.experience == "intermediate"
        _assert_profiles_differ_only(profile, merged, "training.experience")

    def test_experience_existing(self):
        """Experience conflict resolved to existing value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"training.experience": "intermediate"})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "القديم هو الصح"
        )

        assert resolution.resolved is True
        assert merged.training.experience == "beginner"
        _assert_profiles_differ_only(profile, merged, None)

    def test_activity_description_incoming(self):
        """Activity description conflict resolved to incoming."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"training.activity_description": "active"})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.training.activity_description == "active"
        _assert_profiles_differ_only(profile, merged, "training.activity_description")


# ---------------------------------------------------------------------------
# 10. Goal Type Clarification
# ---------------------------------------------------------------------------

class TestGoalTypeClarification:
    """Clarification for goal.type with internal-to-Arabic mapping."""

    def test_goal_type_incoming(self):
        """Goal type conflict resolved to incoming value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.type": "muscle_gain"})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].path == "goal.type"

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.goal.type == "muscle_gain"
        _assert_profiles_differ_only(profile, merged, "goal.type")

    def test_goal_type_existing(self):
        """Goal type conflict resolved to existing value."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.type": "muscle_gain"})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "القديم هو الصح"
        )

        assert resolution.resolved is True
        assert merged.goal.type == "weight_loss"

    def test_goal_type_explicit_arabic(self):
        """'عايز أخس' resolves goal type to weight_loss."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.type": "muscle_gain"})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "عايز أخس"
        )

        assert resolution.resolved is True
        assert merged.goal.type == "weight_loss"
        # goal.type stays weight_loss (same as existing), so no field differs
        _assert_profiles_differ_only(profile, merged, None)


# ---------------------------------------------------------------------------
# 11. Target Weight / Weight Change
# ---------------------------------------------------------------------------

class TestTargetWeightClarification:
    """Clarification for goal.target_weight_kg."""

    def test_target_weight_incoming(self):
        """Target weight conflict resolved to incoming."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.target_weight_kg": 70.0})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].path == "goal.target_weight_kg"

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.goal.target_weight_kg == 70.0
        # personal.weight_kg must not be touched
        assert merged.personal.weight_kg == 85.0
        _assert_profiles_differ_only(profile, merged, "goal.target_weight_kg")

    def test_target_weight_explicit_value(self):
        """Explicit target weight via '72 كيلو'."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.target_weight_kg": 70.0})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "72 كيلو"
        )

        assert resolution.resolved is True
        assert merged.goal.target_weight_kg == 72.0
        assert merged.personal.weight_kg == 85.0


class TestWeightChangeClarification:
    """Clarification for goal.weight_change_target_kg."""

    def test_weight_change_incoming(self):
        """Weight change target conflict resolved to incoming."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.weight_change_target_kg": 15.0})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts[0].path == "goal.weight_change_target_kg"

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        assert merged.goal.weight_change_target_kg == 15.0
        assert merged.personal.weight_kg == 85.0
        _assert_profiles_differ_only(profile, merged, "goal.weight_change_target_kg")

    def test_weight_change_explicit_value(self):
        """Explicit weight change via '12 كيلو'."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"goal.weight_change_target_kg": 15.0})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "12 كيلو"
        )

        assert resolution.resolved is True
        assert merged.goal.weight_change_target_kg == 12.0
        assert merged.personal.weight_kg == 85.0


# ---------------------------------------------------------------------------
# 12. Atomicity
# ---------------------------------------------------------------------------

class TestAtomicity:
    """Unresolved conflict leaves profile completely unchanged."""

    def test_unresolved_no_partial_merge(self):
        """Unresolved conflict — no field changes at all."""
        profile = _make_profile()
        before = _snapshot(profile)
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "مش عارف"
        )

        assert resolution.resolved is False
        after = _snapshot(merged)
        assert before == after, "Profile was partially mutated despite unresolved conflict"

    def test_resolved_only_target_field_changes(self):
        """Resolved conflict — only the target field changes."""
        profile = _make_profile()
        before = _snapshot(profile)
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        resolution, merged, _ = _e2e_resolve(
            profile, conflicts[0], "الجديد هو الصح"
        )

        assert resolution.resolved is True
        after = _snapshot(merged)
        for key in before:
            if key == "personal.age":
                assert before[key] != after[key]
            else:
                assert before[key] == after[key], f"Unexpected change at {key}"

    def test_profile_object_not_mutated(self):
        """Original profile object is never mutated by the resolver or merger."""
        profile = _make_profile()
        original_age = profile.personal.age
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)

        _e2e_resolve(profile, conflicts[0], "الجديد هو الصح")

        assert profile.personal.age == original_age


# ---------------------------------------------------------------------------
# 13. Full Realistic Multi-Turn Scenario
# ---------------------------------------------------------------------------

class TestFullMultiTurnScenario:
    """Simulate a realistic multi-turn clarification flow."""

    def test_full_lifecycle_age_conflict(self):
        """Complete lifecycle: profile → conflict → question → answer → resolve → merge → status."""
        # Turn 1: Existing profile (all required fields present → READY_FOR_PLAN)
        profile = _make_profile()
        initial_status = get_interview_status(profile)
        assert initial_status.state == InterviewState.READY_FOR_PLAN
        assert initial_status.missing_fields == []

        # Turn 2: Incoming patch produces age conflict
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"

        # Turn 3: System generates clarification question
        generator = ClarificationGenerator()
        question = generator.generate(conflicts[0])
        assert "25" in question
        assert "26" in question
        assert "؟" in question

        # Turn 4: User answers "الجديد هو الصح"
        resolver = ClarificationResolver()
        resolution = resolver.resolve(conflicts[0], "الجديد هو الصح")
        assert resolution.resolved is True
        assert resolution.patch.updates["personal.age"] == 26

        # Turn 5-6: Validate patch
        validate_profile_patch(resolution.patch)

        # Turn 7: Merge
        merged_profile = ProfileMerger.merge(profile, resolution.patch)
        assert merged_profile.personal.age == 26
        assert merged_profile.personal.gender == "رجل"
        assert merged_profile.personal.height_cm == 175.0
        assert merged_profile.personal.weight_kg == 85.0
        assert merged_profile.goal.type == "weight_loss"

        # Turn 8: Re-evaluate status — still READY_FOR_PLAN (all fields present)
        final_status = get_interview_status(merged_profile)
        assert final_status.state == InterviewState.READY_FOR_PLAN
        assert final_status.missing_fields == []

    def test_full_lifecycle_conflict_disappears_after_resolution(self):
        """After resolving a conflict, detect_conflicts returns empty."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1

        # Resolve
        resolver = ClarificationResolver()
        resolution = resolver.resolve(conflicts[0], "الجديد هو الصح")
        merged = ProfileMerger.merge(profile, resolution.patch)

        # After merge, the same patch no longer conflicts
        new_conflicts = detect_conflicts(merged, patch)
        assert new_conflicts == []

    def test_full_lifecycle_multiple_fields_independent(self):
        """Resolving one conflict does not affect other fields."""
        profile = _make_profile()
        before = _snapshot(profile)

        # Conflict on age
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        resolver = ClarificationResolver()
        resolution = resolver.resolve(conflicts[0], "الجديد هو الصح")
        merged = ProfileMerger.merge(profile, resolution.patch)

        # Verify only age changed
        after = _snapshot(merged)
        for key in before:
            if key == "personal.age":
                assert after[key] == 26
            else:
                assert after[key] == before[key]


# ---------------------------------------------------------------------------
# 14. Clarification Question Generation Integration
# ---------------------------------------------------------------------------

class TestClarificationQuestionIntegration:
    """Verify the clarification generator produces correct questions for each field."""

    def test_all_numeric_fields_generate_questions(self):
        """Every numeric field gets a clarification question with both values."""
        numeric_fields = [
            ("personal.age", 25, 26),
            ("personal.height_cm", 175.0, 180.0),
            ("goal.target_weight_kg", 75.0, 70.0),
            ("goal.weight_change_target_kg", 10.0, 15.0),
            ("training.days_per_week", 4, 3),
        ]
        generator = ClarificationGenerator()
        for field, existing, incoming in numeric_fields:
            conflict = Conflict(
                path=field, existing_value=existing,
                incoming_value=incoming, reason="test"
            )
            question = generator.generate(conflict)
            assert isinstance(question, str) and "؟" in question, f"Bad question for {field}"

    def test_all_text_fields_generate_questions(self):
        """Every text field gets a clarification question."""
        text_fields = [
            ("personal.gender", "رجل", "ست"),
            ("training.experience", "beginner", "intermediate"),
            ("training.duration", "2 months", "6 months"),
            ("training.activity_description", "مكتبي", "active"),
        ]
        generator = ClarificationGenerator()
        for field, existing, incoming in text_fields:
            conflict = Conflict(
                path=field, existing_value=existing,
                incoming_value=incoming, reason="test"
            )
            question = generator.generate(conflict)
            assert isinstance(question, str) and "؟" in question, f"Bad question for {field}"

    def test_goal_type_generates_arabic_labels(self):
        """Goal type clarification question shows Arabic labels, not internal values."""
        generator = ClarificationGenerator()
        conflict = Conflict(
            path="goal.type", existing_value="weight_loss",
            incoming_value="muscle_gain", reason="test"
        )
        question = generator.generate(conflict)
        assert "خسارة الوزن" in question
        assert "بناء العضلات" in question
        assert "weight_loss" not in question
        assert "muscle_gain" not in question


# ---------------------------------------------------------------------------
# 15. Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_patch_no_conflict(self):
        """Empty patch produces no conflicts — normal flow."""
        profile = _make_profile()
        patch = ProfilePatch(updates={})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts == []
        status = get_interview_status(profile, patch)
        assert status.state == InterviewState.READY_FOR_PLAN

    def test_same_value_no_conflict(self):
        """Patch with same value as existing — no conflict."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 25})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts == []

    def test_mutable_field_no_conflict(self):
        """weight_kg is mutable — different value does not produce conflict."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.weight_kg": 80.0})
        conflicts = detect_conflicts(profile, patch)
        assert conflicts == []
        merged = ProfileMerger.merge(profile, patch)
        assert merged.personal.weight_kg == 80.0

    def test_multiple_conflicts_in_patch(self):
        """Multiple conflicts — each is resolved independently."""
        profile = _make_profile()
        patch = ProfilePatch(updates={"personal.age": 26, "personal.height_cm": 180.0})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 2

        # Resolve age
        resolver = ClarificationResolver()
        age_conflict = [c for c in conflicts if c.path == "personal.age"][0]
        r1 = resolver.resolve(age_conflict, "الجديد هو الصح")
        assert r1.resolved is True
        merged1 = ProfileMerger.merge(profile, r1.patch)

        # Resolve height on the merged profile
        height_conflict_list = detect_conflicts(merged1, patch)
        height_conflict = [c for c in height_conflict_list if c.path == "personal.height_cm"][0]
        r2 = resolver.resolve(height_conflict, "الجديد هو الصح")
        assert r2.resolved is True
        final = ProfileMerger.merge(merged1, r2.patch)

        assert final.personal.age == 26
        assert final.personal.height_cm == 180.0

    def test_unsupported_field_returns_unsupported(self):
        """Non-contradiction-sensitive field → resolver returns unsupported."""
        from app.interview.clarification_resolver import REASON_UNSUPPORTED
        conflict = Conflict(
            path="personal.weight_kg", existing_value=85.0,
            incoming_value=80.0, reason="test"
        )
        resolver = ClarificationResolver()
        resolution = resolver.resolve(conflict, "80")
        assert resolution.resolved is False
        assert resolution.reason == REASON_UNSUPPORTED
