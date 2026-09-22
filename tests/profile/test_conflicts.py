"""Tests for app.profile.conflicts -- deterministic conflict detection."""

import pytest

from app.profile.conflicts import (
    Conflict,
    detect_conflicts,
    _is_contradiction_sensitive,
    _is_list_field,
    _is_mutable_field,
)
from app.profile.models import (
    ClientProfile,
    GoalInfo,
    PersonalInfo,
    ProfilePatch,
    TrainingInfo,
)
from app.profile.policies import (
    ALLOWED_UPDATE_PATHS,
    CONTRADICTION_SENSITIVE_FIELDS,
    LIST_FIELDS,
    MUTABLE_FIELDS,
)
from app.profile.validator import ProfileValidationError


class TestDetectConflicts:
    """Deterministic conflict detection test suite."""

    def test_empty_patch_no_conflicts(self):
        """1. Empty patch produces no conflicts."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch()
        assert detect_conflicts(profile, patch) == []

    def test_new_field_with_existing_none(self):
        """2. Setting a field that was previously None is not a conflict."""
        profile = ClientProfile(personal=PersonalInfo(age=None))
        patch = ProfilePatch(updates={"personal.age": 25})
        assert detect_conflicts(profile, patch) == []

    def test_same_scalar_value(self):
        """3. Identical existing and incoming values produce no conflict."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(updates={"personal.age": 25})
        assert detect_conflicts(profile, patch) == []

    def test_contradictory_age(self):
        """4. Contradictory age produces a conflict."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(updates={"personal.age": 27})
        conflicts = detect_conflicts(profile, patch)

        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"
        assert conflicts[0].existing_value == 25
        assert conflicts[0].incoming_value == 27
        assert conflicts[0].reason == "existing_value_conflicts_with_incoming_value"

    def test_contradictory_gender(self):
        """5. Contradictory gender produces a conflict."""
        profile = ClientProfile(personal=PersonalInfo(gender="رجل"))
        patch = ProfilePatch(updates={"personal.gender": "امرأة"})
        conflicts = detect_conflicts(profile, patch)

        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.gender"
        assert conflicts[0].existing_value == "رجل"
        assert conflicts[0].incoming_value == "امرأة"

    def test_contradictory_height(self):
        """6. Contradictory height produces a conflict."""
        profile = ClientProfile(personal=PersonalInfo(height_cm=175.0))
        patch = ProfilePatch(updates={"personal.height_cm": 160.0})
        conflicts = detect_conflicts(profile, patch)

        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.height_cm"
        assert conflicts[0].existing_value == 175.0
        assert conflicts[0].incoming_value == 160.0

    def test_weight_update_no_conflict(self):
        """7. Weight update on a mutable field produces no conflict."""
        profile = ClientProfile(personal=PersonalInfo(weight_kg=85.0))
        patch = ProfilePatch(updates={"personal.weight_kg": 82.0})
        assert detect_conflicts(profile, patch) == []

    def test_multiple_updates_returns_all_conflicts(self):
        """8. Multiple updates return all detected conflicts."""
        profile = ClientProfile(
            personal=PersonalInfo(age=25, gender="رجل", height_cm=175.0, weight_kg=85.0)
        )
        patch = ProfilePatch(
            updates={
                "personal.age": 27,
                "personal.height_cm": 160.0,
                "personal.weight_kg": 82.0,
            }
        )
        conflicts = detect_conflicts(profile, patch)

        paths = [c.path for c in conflicts]
        assert "personal.age" in paths
        assert "personal.height_cm" in paths
        assert "personal.weight_kg" not in paths
        assert len(conflicts) == 2

    def test_llm_conflicts_ignored(self):
        """9. LLM-reported conflicts are ignored; deterministic detection is authoritative."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(
            updates={"personal.age": 27},
            conflicts=[],
        )
        conflicts = detect_conflicts(profile, patch)

        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"

    def test_false_llm_conflict_ignored(self):
        """10. LLM claims a conflict for a normal weight update; deterministic result has none."""
        profile = ClientProfile(personal=PersonalInfo(weight_kg=85.0))
        patch = ProfilePatch(
            updates={"personal.weight_kg": 82.0},
            conflicts=[{
                "field": "personal.weight_kg",
                "values": [85, 82],
                "message": "User contradicted weight",
            }],
        )
        conflicts = detect_conflicts(profile, patch)
        assert conflicts == []

    def test_invalid_update_path_raises_error(self):
        """11. Invalid update path raises ProfileValidationError."""
        profile = ClientProfile()
        patch_dict = {
            "updates": {"some.invalid.path": "value"},
            "unknown_fields": [],
            "conflicts": [],
        }
        with pytest.raises(ProfileValidationError):
            detect_conflicts(profile, patch_dict)

    def test_inbody_path_rejected_safely(self):
        """12. InBody path is rejected safely via validation."""
        profile = ClientProfile()
        patch_dict = {
            "updates": {"inbody.weight_kg": 75.0},
            "unknown_fields": [],
            "conflicts": [],
        }
        with pytest.raises(ProfileValidationError, match="InBody fields cannot be updated"):
            detect_conflicts(profile, patch_dict)

    def test_original_profile_not_mutated(self):
        """13. Conflict detection does not modify the original profile."""
        profile = ClientProfile(
            personal=PersonalInfo(age=25, gender="رجل", height_cm=175.0, weight_kg=85.0)
        )
        patch = ProfilePatch(
            updates={
                "personal.age": 27,
                "personal.height_cm": 160.0,
            }
        )
        detect_conflicts(profile, patch)

        assert profile.personal.age == 25
        assert profile.personal.gender == "رجل"
        assert profile.personal.height_cm == 175.0
        assert profile.personal.weight_kg == 85.0

    def test_conflict_result_structure(self):
        """14. Conflict result contains path, existing_value, incoming_value, and reason."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(updates={"personal.age": 27})
        conflicts = detect_conflicts(profile, patch)

        assert len(conflicts) == 1
        c = conflicts[0]
        assert isinstance(c, Conflict)
        assert c.path == "personal.age"
        assert c.existing_value == 25
        assert c.incoming_value == 27
        assert c.reason == "existing_value_conflicts_with_incoming_value"

        d = c.to_dict()
        assert d == {
            "path": "personal.age",
            "existing_value": 25,
            "incoming_value": 27,
            "reason": "existing_value_conflicts_with_incoming_value",
        }

    def test_full_realistic_onboarding_sequence(self):
        """15. Full onboarding sequence: initial profile + incoming patch."""
        profile = ClientProfile(
            personal=PersonalInfo(
                age=25,
                gender="رجل",
                height_cm=175.0,
                weight_kg=85.0,
            )
        )

        patch = ProfilePatch(
            updates={
                "personal.age": 27,
                "personal.weight_kg": 82.0,
                "training.days_per_week": 4,
            }
        )

        conflicts = detect_conflicts(profile, patch)

        paths = [c.path for c in conflicts]
        assert "personal.age" in paths
        assert "personal.weight_kg" not in paths
        assert "training.days_per_week" not in paths

        age_conflict = [c for c in conflicts if c.path == "personal.age"][0]
        assert age_conflict.existing_value == 25
        assert age_conflict.incoming_value == 27


class TestConflictPolicySemantics:
    """Regression tests documenting the current onboarding conflict policy.

    These tests codify the expected behavior per field category so that
    future refactors cannot accidentally change semantics without updating
    the policy first.
    """

    def test_age_contradiction_is_conflict(self):
        """Age 25 -> 26 is a conflict under current onboarding policy.

        NOTE: This is current interview behavior, not a claim that age can
        never change. A future profile-update workflow with temporal context
        may reclassify age as mutable.
        """
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(updates={"personal.age": 26})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"

    def test_age_same_value_no_conflict(self):
        """Age 25 -> 25 is identical, no conflict."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(updates={"personal.age": 25})
        assert detect_conflicts(profile, patch) == []

    def test_age_none_to_value_no_conflict(self):
        """Age None -> 25 is filling a missing field, not a contradiction."""
        profile = ClientProfile(personal=PersonalInfo(age=None))
        patch = ProfilePatch(updates={"personal.age": 25})
        assert detect_conflicts(profile, patch) == []

    def test_weight_update_no_conflict(self):
        """Weight 85 -> 82 is a normal update on a mutable field."""
        profile = ClientProfile(personal=PersonalInfo(weight_kg=85.0))
        patch = ProfilePatch(updates={"personal.weight_kg": 82.0})
        assert detect_conflicts(profile, patch) == []

    def test_goal_target_change_is_conflict(self):
        """Goal target 75 -> 70 is a conflict under current onboarding policy.

        NOTE: This is current interview behavior. A future profile-update
        workflow may treat goal.target_weight_kg as mutable when temporal
        context is available.
        """
        profile = ClientProfile(goal=GoalInfo(target_weight_kg=75.0))
        patch = ProfilePatch(updates={"goal.target_weight_kg": 70.0})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "goal.target_weight_kg"
        assert conflicts[0].existing_value == 75.0
        assert conflicts[0].incoming_value == 70.0

    def test_training_days_change_is_conflict(self):
        """Training days 4 -> 5 is a conflict under current onboarding policy.

        NOTE: This is current interview behavior. A future profile-update
        workflow may reclassify training.days_per_week as mutable.
        """
        profile = ClientProfile(training=TrainingInfo(days_per_week=4))
        patch = ProfilePatch(updates={"training.days_per_week": 5})
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "training.days_per_week"
        assert conflicts[0].existing_value == 4
        assert conflicts[0].incoming_value == 5

    def test_list_replacement_no_conflict(self):
        """List field replacement is handled by the merger, not conflict detection."""
        profile = ClientProfile()
        profile.nutrition.food_preferences = ["فراخ"]
        patch = ProfilePatch(updates={"nutrition.food_preferences": ["سمك"]})
        assert detect_conflicts(profile, patch) == []

    def test_llm_provided_conflicts_still_ignored(self):
        """LLM-generated conflicts are never used by the deterministic detector."""
        profile = ClientProfile(personal=PersonalInfo(age=25))
        patch = ProfilePatch(
            updates={"personal.age": 27},
            conflicts=[{"field": "personal.age", "values": [25, 27]}],
        )
        conflicts = detect_conflicts(profile, patch)
        assert len(conflicts) == 1
        assert conflicts[0].path == "personal.age"


class TestPolicyCoherence:
    """Verify policy sets are internally consistent and aligned with ALLOWED_UPDATE_PATHS."""

    def test_all_contradiction_sensitive_are_allowed(self):
        """Every contradiction-sensitive field must be an allowed update path."""
        assert CONTRADICTION_SENSITIVE_FIELDS.issubset(ALLOWED_UPDATE_PATHS)

    def test_all_mutable_are_allowed(self):
        """Every mutable field must be an allowed update path."""
        assert MUTABLE_FIELDS.issubset(ALLOWED_UPDATE_PATHS)

    def test_all_list_are_allowed(self):
        """Every list field must be an allowed update path."""
        assert LIST_FIELDS.issubset(ALLOWED_UPDATE_PATHS)

    def test_no_field_in_both_mutable_and_contradiction_sensitive(self):
        """Mutable and contradiction-sensitive sets must not overlap."""
        overlap = MUTABLE_FIELDS & CONTRADICTION_SENSITIVE_FIELDS
        assert overlap == set(), f"Overlapping fields: {overlap}"

    def test_no_field_in_both_list_and_mutable(self):
        """List and mutable sets must not overlap."""
        overlap = LIST_FIELDS & MUTABLE_FIELDS
        assert overlap == set(), f"Overlapping fields: {overlap}"

    def test_no_field_in_both_list_and_contradiction_sensitive(self):
        """List and contradiction-sensitive sets must not overlap."""
        overlap = LIST_FIELDS & CONTRADICTION_SENSITIVE_FIELDS
        assert overlap == set(), f"Overlapping fields: {overlap}"

    def test_all_allowed_paths_are_classified(self):
        """Every allowed path belongs to exactly one conflict category."""
        classified = CONTRADICTION_SENSITIVE_FIELDS | MUTABLE_FIELDS | LIST_FIELDS
        unclassified = ALLOWED_UPDATE_PATHS - classified
        assert unclassified == set(), f"Unclassified paths: {unclassified}"

    def test_helpers_match_set_membership(self):
        """Classification helpers are consistent with the policy sets."""
        for path in ALLOWED_UPDATE_PATHS:
            assert _is_contradiction_sensitive(path) == (path in CONTRADICTION_SENSITIVE_FIELDS)
            assert _is_mutable_field(path) == (path in MUTABLE_FIELDS)
            assert _is_list_field(path) == (path in LIST_FIELDS)
