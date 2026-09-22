"""Unit tests for app.profile.merger — deterministic ProfileMerger."""

import pytest

from app.profile.merger import ProfileMerger, merge_profile, merge_profile_patch
from app.profile.models import ClientProfile, HealthInfo, PersonalInfo, ProfilePatch
from app.profile.validator import ProfileValidationError


class TestProfileMerger:
    """Deterministic profile merger test suite."""

    def test_empty_patch_leaves_profile_unchanged(self):
        """A. Empty patch preserves existing profile completely."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, gender="رجل", height_cm=175.0, weight_kg=85.0),
            health=HealthInfo(injuries=["knee pain"]),
        )
        patch = ProfilePatch()
        result = merge_profile(initial, patch)

        assert result.personal.age == 25
        assert result.personal.gender == "رجل"
        assert result.personal.height_cm == 175.0
        assert result.personal.weight_kg == 85.0
        assert result.health.injuries == ["knee pain"]

    def test_single_scalar_update(self):
        """B. Single scalar update modifies only that field."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, gender="رجل", height_cm=175.0, weight_kg=85.0)
        )
        patch = ProfilePatch(updates={"personal.age": 26})
        result = merge_profile(initial, patch)

        assert result.personal.age == 26
        # Unchanged fields
        assert result.personal.gender == "رجل"
        assert result.personal.height_cm == 175.0
        assert result.personal.weight_kg == 85.0

    def test_multiple_updates_same_section(self):
        """C. Multiple updates across same section update together."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, gender="رجل", height_cm=175.0, weight_kg=85.0)
        )
        patch = ProfilePatch(updates={
            "personal.age": 26,
            "personal.height_cm": 176.0,
            "personal.weight_kg": 83.0,
        })
        result = merge_profile(initial, patch)

        assert result.personal.age == 26
        assert result.personal.height_cm == 176.0
        assert result.personal.weight_kg == 83.0
        assert result.personal.gender == "رجل"

    def test_nested_updates_across_sections(self):
        """D. Nested updates across multiple sections apply correctly."""
        initial = ClientProfile()
        patch = ProfilePatch(updates={
            "goal.type": "weight_loss",
            "goal.target_weight_kg": 75.0,
            "goal.weight_change_target_kg": -10.0,
            "training.days_per_week": 4,
            "training.duration": "45 min",
            "training.experience": "intermediate",
            "training.activity_description": "مكتبي",
        })
        result = merge_profile(initial, patch)

        assert result.goal.type == "weight_loss"
        assert result.goal.target_weight_kg == 75.0
        assert result.goal.weight_change_target_kg == -10.0
        assert result.training.days_per_week == 4
        assert result.training.duration == "45 min"
        assert result.training.experience == "intermediate"
        assert result.training.activity_description == "مكتبي"

    def test_health_injuries_update(self):
        """E. health.injuries updates correctly preserving semantic distinction."""
        initial = ClientProfile()
        assert initial.health.injuries is None  # unasked

        # Explicitly reported no injuries
        patch_none = ProfilePatch(updates={"health.injuries": []})
        res1 = merge_profile(initial, patch_none)
        assert res1.health.injuries == []

        # Reported specific injuries
        patch_injured = ProfilePatch(updates={"health.injuries": ["shoulder impingement"]})
        res2 = merge_profile(res1, patch_injured)
        assert res2.health.injuries == ["shoulder impingement"]

    def test_list_field_replacement_not_append(self):
        """F. List fields are replaced, not appended or deduplicated."""
        initial = ClientProfile()
        initial.nutrition.food_preferences = ["فراخ", "رز"]

        patch = ProfilePatch(updates={"nutrition.food_preferences": ["بطاطس"]})
        result = merge_profile(initial, patch)

        # Must be replaced, NOT ["فراخ", "رز", "بطاطس"]
        assert result.nutrition.food_preferences == ["بطاطس"]

    def test_omitted_fields_preserved(self):
        """G. Patch changing weight must not erase age, height, gender, etc."""
        initial = ClientProfile(
            personal=PersonalInfo(age=28, gender="أنثى", height_cm=162.0, weight_kg=68.0),
        )
        initial.nutrition.disliked_foods = ["سمك"]
        initial.training.days_per_week = 3

        patch = ProfilePatch(updates={"personal.weight_kg": 65.0})
        result = merge_profile(initial, patch)

        assert result.personal.weight_kg == 65.0
        assert result.personal.age == 28
        assert result.personal.gender == "أنثى"
        assert result.personal.height_cm == 162.0
        assert result.nutrition.disliked_foods == ["سمك"]
        assert result.training.days_per_week == 3

    def test_explicit_none_applied_to_nullable_field(self):
        """H. Explicit None update for a nullable field applies None."""
        initial = ClientProfile(
            personal=PersonalInfo(age=30, gender="رجل", height_cm=180.0, weight_kg=80.0)
        )
        patch = ProfilePatch(updates={"personal.gender": None})
        result = merge_profile(initial, patch)

        assert result.personal.gender is None
        assert result.personal.age == 30

    def test_reject_invalid_path(self):
        """I. Merger rejects paths not in ALLOWED_UPDATE_PATHS."""
        initial = ClientProfile()
        # Direct dict patch with arbitrary path
        bad_patch = {
            "updates": {"some.random.path": "value"},
            "unknown_fields": [],
            "conflicts": [],
        }
        with pytest.raises(ProfileValidationError, match="Arbitrary paths are strictly forbidden"):
            merge_profile(initial, bad_patch)

    def test_reject_inbody_paths(self):
        """J. Merger defensively rejects inbody.* paths."""
        initial = ClientProfile()
        inbody_patch = {
            "updates": {"inbody.weight_kg": 75.0},
            "unknown_fields": [],
            "conflicts": [],
        }
        with pytest.raises(ProfileValidationError, match="InBody fields cannot be updated via ProfilePatch"):
            merge_profile(initial, inbody_patch)

    def test_original_profile_not_mutated(self):
        """K. Merging returns a new instance and does NOT mutate the original."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, weight_kg=85.0)
        )
        initial.nutrition.food_preferences = ["تفاح"]

        patch = ProfilePatch(updates={
            "personal.weight_kg": 80.0,
            "nutrition.food_preferences": ["موز"],
        })
        result = merge_profile(initial, patch)

        # Result has new values
        assert result.personal.weight_kg == 80.0
        assert result.nutrition.food_preferences == ["موز"]

        # Original remains completely unchanged
        assert initial.personal.weight_kg == 85.0
        assert initial.nutrition.food_preferences == ["تفاح"]
        assert result is not initial

    def test_unknown_fields_do_not_affect_profile(self):
        """L. unknown_fields in patch do not alter profile state."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, weight_kg=85.0)
        )
        patch = ProfilePatch(
            updates={"personal.weight_kg": 84.0},
            unknown_fields=["personal.height_cm", "training.experience"],
        )
        result = merge_profile(initial, patch)

        assert result.personal.weight_kg == 84.0
        assert result.personal.age == 25
        assert result.personal.height_cm is None

    def test_conflicts_do_not_affect_profile(self):
        """M. conflicts in patch are passed through without triggering resolution."""
        initial = ClientProfile(
            personal=PersonalInfo(age=25, weight_kg=85.0)
        )
        patch = ProfilePatch(
            updates={"personal.weight_kg": 85.0},
            conflicts=[{
                "field": "personal.weight_kg",
                "values": [85, 90],
                "message": "User contradicted themselves",
            }],
        )
        result = merge_profile(initial, patch)

        assert result.personal.weight_kg == 85.0
        assert result.personal.age == 25

    def test_full_realistic_onboarding_example(self):
        """N. Comprehensive realistic onboarding flow test."""
        # Initial profile with personal info
        initial = ClientProfile(
            personal=PersonalInfo(
                age=25,
                gender="رجل",
                height_cm=175.0,
                weight_kg=85.0,
            )
        )

        # Patch arrives with updates across multiple domains
        patch = ProfilePatch(updates={
            "personal.weight_kg": 82.0,
            "training.days_per_week": 4,
            "goal.type": "weight_loss",
            "nutrition.food_preferences": ["فراخ", "رز"],
        })

        merged = merge_profile_patch(initial, patch)

        # Updated fields
        assert merged.personal.weight_kg == 82.0
        assert merged.training.days_per_week == 4
        assert merged.goal.type == "weight_loss"
        assert merged.nutrition.food_preferences == ["فراخ", "رز"]

        # Intact preserved fields
        assert merged.personal.age == 25
        assert merged.personal.gender == "رجل"
        assert merged.personal.height_cm == 175.0

        # Unmodified default sections
        assert merged.health.injuries is None
        assert merged.nutrition.disliked_foods == []
        assert merged.metadata.profile_status == "INCOMPLETE"

        # Verification via ProfileMerger class directly
        class_merged = ProfileMerger.merge(initial, patch)
        assert class_merged.personal.weight_kg == 82.0
