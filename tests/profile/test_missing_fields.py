"""Tests for app.profile.missing_fields -- deterministic missing field detection."""

import pytest

from app.profile.missing_fields import (
    REQUIRED_ONBOARDING_FIELDS,
    get_missing_fields,
    is_profile_complete,
)
from app.profile.models import ClientProfile


class TestGetMissingFields:
    """Deterministic missing field detection test suite."""

    def test_completely_empty_profile(self):
        """1. Empty profile has all required fields missing."""
        profile = ClientProfile()
        missing = get_missing_fields(profile)
        assert missing == REQUIRED_ONBOARDING_FIELDS
        assert len(missing) == 10

    def test_fully_complete_profile(self):
        """2. Fully populated profile returns no missing fields."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        assert get_missing_fields(profile) == []

    def test_partial_profile(self):
        """3. Partial profile returns exactly the missing fields in required order."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": None, "weight_kg": 85.0},
            goal={"type": None},
            training={
                "days_per_week": 4,
                "duration": None,
                "experience": "beginner",
                "activity_description": "مكتبي",
            },
            health={"injuries": None},
        )
        missing = get_missing_fields(profile)
        assert missing == [
            "personal.height_cm",
            "health.injuries",
            "training.duration",
            "goal.type",
        ]

    def test_none_scalar_values_are_missing(self):
        """4. None values for scalar fields are treated as missing."""
        profile = ClientProfile(
            personal={"age": None, "gender": None, "height_cm": None, "weight_kg": None},
        )
        missing = get_missing_fields(profile)
        assert "personal.age" in missing
        assert "personal.gender" in missing
        assert "personal.height_cm" in missing
        assert "personal.weight_kg" in missing

    def test_injuries_none_is_missing(self):
        """5. health.injuries = None means not yet asked => missing."""
        profile = ClientProfile(health={"injuries": None})
        missing = get_missing_fields(profile)
        assert "health.injuries" in missing

    def test_injuries_empty_list_is_not_missing(self):
        """6. health.injuries = [] means explicitly reported no injuries => present."""
        profile = ClientProfile(health={"injuries": []})
        missing = get_missing_fields(profile)
        assert "health.injuries" not in missing

    def test_injuries_populated_is_not_missing(self):
        """7. health.injuries = ["knee pain"] means reported injuries => present."""
        profile = ClientProfile(health={"injuries": ["knee pain"]})
        missing = get_missing_fields(profile)
        assert "health.injuries" not in missing

    def test_optional_target_weight_absent(self):
        """8. Absent optional target_weight_kg does not appear in missing fields."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss", "target_weight_kg": None},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        missing = get_missing_fields(profile)
        assert "goal.target_weight_kg" not in missing
        assert missing == []

    def test_optional_food_preferences_absent(self):
        """9. Absent optional food_preferences does not appear in missing fields."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
            nutrition={"food_preferences": [], "disliked_foods": [], "disliked_activities": []},
        )
        missing = get_missing_fields(profile)
        assert "nutrition.food_preferences" not in missing
        assert missing == []

    def test_inbody_absent_does_not_affect_completeness(self):
        """10. Entirely absent InBody does not affect onboarding completeness."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
            inbody={"weight_kg": None, "body_fat_percent": None},
        )
        missing = get_missing_fields(profile)
        assert missing == []

    def test_empty_string_is_missing(self):
        """11. Empty string for a required string field is treated as missing."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": ""},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        missing = get_missing_fields(profile)
        assert "goal.type" in missing

    def test_whitespace_only_string_is_missing(self):
        """12. Whitespace-only string for a required string field is treated as missing."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "   "},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        missing = get_missing_fields(profile)
        assert "goal.type" in missing

    def test_numeric_zero_not_treated_as_missing(self):
        """13. Numeric zero for a required numeric field is NOT treated as missing."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 0,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        missing = get_missing_fields(profile)
        assert "training.days_per_week" not in missing
        assert missing == []

    def test_exact_deterministic_ordering(self):
        """14. Missing fields are returned in the exact required onboarding order."""
        profile = ClientProfile()  # everything missing
        missing = get_missing_fields(profile)
        assert missing == [
            "personal.gender",
            "personal.age",
            "personal.height_cm",
            "personal.weight_kg",
            "health.injuries",
            "training.experience",
            "training.days_per_week",
            "training.duration",
            "training.activity_description",
            "goal.type",
        ]

    def test_profile_immutability(self):
        """15. Detecting missing fields does not modify the profile."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        before = profile.model_dump()
        _ = get_missing_fields(profile)
        after = profile.model_dump()
        assert before == after

    def test_is_profile_complete_true(self):
        """16. is_profile_complete returns True when all required fields are present."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        assert is_profile_complete(profile) is True

    def test_is_profile_complete_false(self):
        """16b. is_profile_complete returns False when required fields are missing."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل"},
        )
        assert is_profile_complete(profile) is False

    def test_required_field_policy_constant(self):
        """17. REQUIRED_ONBOARDING_FIELDS contains exactly the intended required fields."""
        assert REQUIRED_ONBOARDING_FIELDS == [
            "personal.gender",
            "personal.age",
            "personal.height_cm",
            "personal.weight_kg",
            "health.injuries",
            "training.experience",
            "training.days_per_week",
            "training.duration",
            "training.activity_description",
            "goal.type",
        ]

    def test_no_optional_fields_in_result(self):
        """18. Optional fields never appear in missing fields even when absent."""
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss", "target_weight_kg": None, "weight_change_target_kg": None},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "intermediate",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
            nutrition={"food_preferences": [], "disliked_foods": [], "disliked_activities": []},
            inbody={},
        )
        missing = get_missing_fields(profile)
        optional_paths = [
            "goal.target_weight_kg",
            "goal.weight_change_target_kg",
            "nutrition.food_preferences",
            "nutrition.disliked_foods",
            "nutrition.disliked_activities",
            "inbody.weight_kg",
            "inbody.body_fat_percent",
            "inbody.fat_mass_kg",
            "inbody.skeletal_muscle_mass_kg",
            "inbody.bmi",
            "inbody.visceral_fat_level",
        ]
        for opt in optional_paths:
            assert opt not in missing
        assert missing == []
