"""Tests for app.profile.validator — deterministic validation for ProfilePatch."""

import pytest

from app.profile.models import ProfilePatch
from app.profile.validator import (
    ProfileValidationError,
    validate_patch,
    validate_profile_patch,
)


class TestValidateProfilePatch:
    """Test suite for deterministic ProfilePatch validation."""

    def test_valid_empty_patch(self):
        """Empty updates, unknown_fields, conflicts is valid."""
        patch = ProfilePatch()
        validate_profile_patch(patch)
        validate_patch(patch)

    def test_valid_dict_patch(self):
        """Dict input with valid fields passes."""
        patch_dict = {
            "updates": {
                "personal.age": 30,
                "personal.gender": "female",
                "personal.height_cm": 165.5,
                "personal.weight_kg": 60.0,
                "goal.type": "maintenance",
                "goal.target_weight_kg": 60.0,
                "goal.weight_change_target_kg": 0.0,
                "training.days_per_week": 3,
                "training.duration": 45,
                "training.experience": "beginner",
                "training.activity_description": "active",
                "health.injuries": ["none"],
                "nutrition.food_preferences": ["salad"],
                "nutrition.disliked_foods": ["dairy"],
                "nutrition.disliked_activities": ["swimming"],
            },
            "unknown_fields": ["some_unasked"],
            "conflicts": [{"field": "personal.age", "values": [25, 30]}],
        }
        validate_profile_patch(patch_dict)

    def test_invalid_input_type(self):
        """Passing non-patch/non-dict raises ProfileValidationError."""
        with pytest.raises(ProfileValidationError, match="Expected ProfilePatch or dict"):
            validate_profile_patch("invalid_string_input")

    def test_reject_arbitrary_paths(self):
        """Arbitrary paths are rejected with clear error."""
        for bad_path in ["unknown", "user.name", "personal.eye_color", "nutrition.calories"]:
            patch = ProfilePatch(updates={bad_path: "val"})
            with pytest.raises(ProfileValidationError, match="Arbitrary paths are strictly forbidden"):
                validate_profile_patch(patch)

    def test_reject_inbody_paths(self):
        """InBody paths are explicitly rejected as not allowed in ProfilePatch."""
        inbody_fields = [
            "inbody.weight_kg",
            "inbody.body_fat_percent",
            "inbody.fat_mass_kg",
            "inbody.skeletal_muscle_mass_kg",
            "inbody.bmi",
            "inbody.visceral_fat_level",
        ]
        for field in inbody_fields:
            patch = ProfilePatch(updates={field: 25.0})
            with pytest.raises(ProfileValidationError, match="InBody fields cannot be updated via ProfilePatch"):
                validate_profile_patch(patch)

    def test_personal_age_validation(self):
        """personal.age must be non-negative integer (not bool)."""
        # None is allowed
        validate_profile_patch(ProfilePatch(updates={"personal.age": None}))
        # Valid int
        validate_profile_patch(ProfilePatch(updates={"personal.age": 25}))

        # String
        with pytest.raises(ProfileValidationError, match="must be an integer"):
            validate_profile_patch(ProfilePatch(updates={"personal.age": "25"}))
        # Boolean
        with pytest.raises(ProfileValidationError, match="must be an integer"):
            validate_profile_patch(ProfilePatch(updates={"personal.age": True}))
        # Float
        with pytest.raises(ProfileValidationError, match="must be an integer"):
            validate_profile_patch(ProfilePatch(updates={"personal.age": 25.5}))
        # Negative
        with pytest.raises(ProfileValidationError, match="must be non-negative"):
            validate_profile_patch(ProfilePatch(updates={"personal.age": -1}))

    def test_numeric_measurements_validation(self):
        """height_cm, weight_kg, and target_weight_kg must be positive numbers."""
        for field in ["personal.height_cm", "personal.weight_kg", "goal.target_weight_kg"]:
            # Valid float and int
            validate_profile_patch(ProfilePatch(updates={field: 170}))
            validate_profile_patch(ProfilePatch(updates={field: 170.5}))

            # Zero or negative
            with pytest.raises(ProfileValidationError, match="must be greater than 0"):
                validate_profile_patch(ProfilePatch(updates={field: 0}))
            with pytest.raises(ProfileValidationError, match="must be greater than 0"):
                validate_profile_patch(ProfilePatch(updates={field: -5}))

            # Boolean
            with pytest.raises(ProfileValidationError, match="must be a numeric value"):
                validate_profile_patch(ProfilePatch(updates={field: True}))
            # String
            with pytest.raises(ProfileValidationError, match="must be a numeric value"):
                validate_profile_patch(ProfilePatch(updates={field: "170"}))

    def test_training_days_validation(self):
        """training.days_per_week must be an int between 0 and 7."""
        validate_profile_patch(ProfilePatch(updates={"training.days_per_week": 0}))
        validate_profile_patch(ProfilePatch(updates={"training.days_per_week": 7}))

        with pytest.raises(ProfileValidationError, match="must be between 0 and 7"):
            validate_profile_patch(ProfilePatch(updates={"training.days_per_week": -1}))
        with pytest.raises(ProfileValidationError, match="must be between 0 and 7"):
            validate_profile_patch(ProfilePatch(updates={"training.days_per_week": 8}))
        with pytest.raises(ProfileValidationError, match="must be an integer"):
            validate_profile_patch(ProfilePatch(updates={"training.days_per_week": True}))
        with pytest.raises(ProfileValidationError, match="must be an integer"):
            validate_profile_patch(ProfilePatch(updates={"training.days_per_week": "4"}))

    def test_training_duration_validation(self):
        """training.duration preserves string or number contract."""
        validate_profile_patch(ProfilePatch(updates={"training.duration": "2 months"}))
        validate_profile_patch(ProfilePatch(updates={"training.duration": 45}))
        validate_profile_patch(ProfilePatch(updates={"training.duration": 60.5}))

        # Boolean rejected
        with pytest.raises(ProfileValidationError, match="must be a string or number"):
            validate_profile_patch(ProfilePatch(updates={"training.duration": False}))
        # List rejected
        with pytest.raises(ProfileValidationError, match="must be a string or number"):
            validate_profile_patch(ProfilePatch(updates={"training.duration": [1, 2]}))

    def test_string_fields_validation(self):
        """String fields (gender, goal.type, experience, activity_description)."""
        for field in ["personal.gender", "goal.type", "training.experience", "training.activity_description"]:
            validate_profile_patch(ProfilePatch(updates={field: "sample text"}))
            validate_profile_patch(ProfilePatch(updates={field: None}))

            with pytest.raises(ProfileValidationError, match="must be a string or null"):
                validate_profile_patch(ProfilePatch(updates={field: 123}))

    def test_list_of_strings_validation(self):
        """List fields must be lists containing only strings."""
        for field in [
            "health.injuries",
            "nutrition.food_preferences",
            "nutrition.disliked_foods",
            "nutrition.disliked_activities",
        ]:
            validate_profile_patch(ProfilePatch(updates={field: ["item1", "item2"]}))
            validate_profile_patch(ProfilePatch(updates={field: []}))

            # Non-list
            with pytest.raises(ProfileValidationError, match="must be a list"):
                validate_profile_patch(ProfilePatch(updates={field: "single item"}))

            # List with non-string
            with pytest.raises(ProfileValidationError, match="must be strings"):
                validate_profile_patch(ProfilePatch(updates={field: ["ok", 123]}))

    def test_unknown_fields_and_conflicts_validation(self):
        """unknown_fields and conflicts structure validation."""
        # Non-string in unknown_fields
        with pytest.raises(ProfileValidationError, match="Items in 'unknown_fields' must be strings"):
            validate_profile_patch({
                "updates": {},
                "unknown_fields": [123],
                "conflicts": [],
            })

        # Non-dict in conflicts
        with pytest.raises(ProfileValidationError, match="Items in 'conflicts' must be dicts"):
            validate_profile_patch({
                "updates": {},
                "unknown_fields": [],
                "conflicts": ["not_a_dict"],
            })
