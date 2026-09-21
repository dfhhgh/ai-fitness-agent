"""Initial contract, schema, and model instantiation tests for Phase 1.1."""

import json
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
import pytest

from app.profile.models import (
    ClientProfile,
    GoalInfo,
    HealthInfo,
    InBodyInfo,
    NutritionPreferences,
    PersonalInfo,
    ProfileMetadata,
    ProfilePatch,
    TrainingInfo,
)
from app.profile.policies import ALLOWED_UPDATE_PATHS
from app.profile.schemas import (
    get_client_profile_schema,
    get_fitness_plan_schema,
    get_profile_patch_schema,
)
from app.profile.validator import ProfileValidationError, validate_profile_patch



def test_models_import_and_instantiation():
    """Verify all Pydantic models can be imported and instantiated with defaults."""
    personal = PersonalInfo()
    assert personal.age is None
    assert personal.gender is None

    goal = GoalInfo()
    assert goal.type is None

    training = TrainingInfo()
    assert training.days_per_week is None

    health = HealthInfo()
    assert health.injuries is None  # Distinct from []

    nutrition = NutritionPreferences()
    assert nutrition.food_preferences == []
    assert nutrition.disliked_foods == []
    assert nutrition.disliked_activities == []

    inbody = InBodyInfo()
    assert inbody.weight_kg is None

    metadata = ProfileMetadata()
    assert metadata.profile_status == "INCOMPLETE"
    assert metadata.missing_fields == []
    assert metadata.last_updated is None

    profile = ClientProfile()
    assert profile.client_id is None
    assert profile.personal.age is None
    assert profile.health.injuries is None
    assert profile.metadata.profile_status == "INCOMPLETE"

    patch = ProfilePatch()
    assert patch.updates == {}
    assert patch.unknown_fields == []
    assert patch.conflicts == []


def test_health_injuries_semantics():
    """Verify health.injuries semantic distinction between null, empty list, and reported injuries."""
    # 1. Unasked
    unasked = HealthInfo(injuries=None)
    assert unasked.injuries is None

    # 2. Explicitly no injuries
    no_injuries = HealthInfo(injuries=[])
    assert no_injuries.injuries == []
    assert no_injuries.injuries is not None

    # 3. Reported injuries
    reported = HealthInfo(injuries=["lower back pain", "shoulder impingement"])
    assert reported.injuries == ["lower back pain", "shoulder impingement"]


def test_schemas_are_valid_draft202012():
    """Verify that all JSON schemas are syntactically valid JSON Schema Draft 2020-12."""
    client_profile_schema = get_client_profile_schema()
    Draft202012Validator.check_schema(client_profile_schema)

    profile_patch_schema = get_profile_patch_schema()
    Draft202012Validator.check_schema(profile_patch_schema)

    fitness_plan_schema = get_fitness_plan_schema()
    Draft202012Validator.check_schema(fitness_plan_schema)


def test_client_profile_schema_validation():
    """Verify ClientProfile model dump validates against client_profile.schema.json."""
    profile = ClientProfile()
    profile_dict = profile.model_dump(mode="json")

    schema = get_client_profile_schema()
    validator = Draft202012Validator(schema)
    validator.validate(profile_dict)


def test_profile_patch_schema_valid_and_invalid():
    """Verify ProfilePatch schema enforces allowed keys and types."""
    schema = get_profile_patch_schema()
    validator = Draft202012Validator(schema)

    # Valid patch
    valid_patch = {
        "updates": {
            "personal.age": 25,
            "personal.weight_kg": 85.5,
            "training.days_per_week": 4,
            "health.injuries": ["knee pain"],
            "nutrition.food_preferences": ["chicken", "rice"],
        },
        "unknown_fields": [],
        "conflicts": [],
    }
    validator.validate(valid_patch)

    # Invalid patch: unknown path key
    invalid_patch_key = {
        "updates": {
            "arbitrary.key": "not_allowed",
        },
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ValidationError):
        validator.validate(invalid_patch_key)

    # Invalid patch: wrong type for personal.age (string instead of int/null)
    invalid_patch_type = {
        "updates": {
            "personal.age": "twenty five",
        },
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ValidationError):
        validator.validate(invalid_patch_type)


def test_fitness_plan_schema_validation():
    """Verify fitness_plan.schema.json validates an authoritative fitness plan payload."""
    schema = get_fitness_plan_schema()
    validator = Draft202012Validator(schema)

    valid_plan = {
        "client_id": "client-12345",
        "nutrition_plan": {
            "targets": {
                "calories_kcal": 2200.0,
                "protein_g": 160.0,
                "carbs_g": 220.0,
                "fat_g": 65.0,
                "fiber_g": 30.0,
            },
            "meals": [
                {
                    "name": "Breakfast",
                    "foods": [
                        {
                            "food_id": "oats-01",
                            "name": "Oatmeal",
                            "quantity": 80.0,
                            "unit": "g",
                            "weight_g": 80.0,
                        }
                    ],
                }
            ],
        },
        "workout_plan": {
            "days": [
                {
                    "day": 1,
                    "name": "Upper Body Strength",
                    "exercises": [
                        {
                            "exercise_id": "bench-press",
                            "name": "Barbell Bench Press",
                            "sets": 4,
                            "reps": "8-10",
                            "rir": 2.0,
                            "rest_seconds": 120,
                        }
                    ],
                }
            ]
        },
        "metadata": {
            "status": "DRAFT",
            "version": 1,
            "generated_at": "2026-09-21T12:00:00Z",
        },
    }
    validator.validate(valid_plan)


def test_allowed_update_paths_contract_alignment():
    """Verify ALLOWED_UPDATE_PATHS matches profile_patch.schema.json exactly."""
    schema = get_profile_patch_schema()
    schema_enum_paths = set(
        schema["properties"]["updates"]["propertyNames"]["enum"]
    )
    schema_properties_paths = set(
        schema["properties"]["updates"]["properties"].keys()
    )

    # 1. Exactly 15 allowed paths
    assert len(ALLOWED_UPDATE_PATHS) == 15

    # 2. policies.py matches schema propertyNames enum
    assert ALLOWED_UPDATE_PATHS == schema_enum_paths

    # 3. policies.py matches schema properties keys
    assert ALLOWED_UPDATE_PATHS == schema_properties_paths

    # 4. InBody fields must NOT be in ALLOWED_UPDATE_PATHS
    inbody_paths = [p for p in ALLOWED_UPDATE_PATHS if p.startswith("inbody.")]
    assert inbody_paths == []


def test_deterministic_validator_accepts_all_allowed_paths():
    """Verify validate_profile_patch accepts a patch containing all 15 valid paths."""
    all_paths_patch = {
        "updates": {
            "personal.age": 25,
            "personal.gender": "رجل",
            "personal.height_cm": 178.0,
            "personal.weight_kg": 82.5,
            "goal.type": "weight_loss",
            "goal.target_weight_kg": 75.0,
            "goal.weight_change_target_kg": -7.5,
            "training.days_per_week": 4,
            "training.duration": "3 months",
            "training.experience": "intermediate",
            "training.activity_description": "مكتبي",
            "health.injuries": ["knee pain"],
            "nutrition.food_preferences": ["chicken", "rice"],
            "nutrition.disliked_foods": ["fish"],
            "nutrition.disliked_activities": ["running"],
        },
        "unknown_fields": [],
        "conflicts": [],
    }
    # Dict form
    validate_profile_patch(all_paths_patch)

    # Model form
    patch_model = ProfilePatch.model_validate(all_paths_patch)
    validate_profile_patch(patch_model)


def test_deterministic_validator_rejects_arbitrary_paths():
    """Verify validate_profile_patch strictly rejects arbitrary update paths."""
    # Arbitrary path
    bad_patch = {
        "updates": {"some.random.field": "bad"},
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ProfileValidationError, match="Arbitrary paths are strictly forbidden"):
        validate_profile_patch(bad_patch)

    # Non-existent subfield
    bad_subfield = {
        "updates": {"personal.foo": 123},
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ProfileValidationError, match="Arbitrary paths are strictly forbidden"):
        validate_profile_patch(bad_subfield)


def test_deterministic_validator_rejects_inbody_paths():
    """Verify InBody fields are strictly rejected by the validator."""
    inbody_patch = {
        "updates": {"inbody.body_fat_percent": 20},
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ProfileValidationError, match="InBody fields cannot be updated via ProfilePatch"):
        validate_profile_patch(inbody_patch)

    inbody_weight = {
        "updates": {"inbody.weight_kg": 75},
        "unknown_fields": [],
        "conflicts": [],
    }
    with pytest.raises(ProfileValidationError, match="InBody fields cannot be updated via ProfilePatch"):
        validate_profile_patch(inbody_weight)


def test_deterministic_validator_rejects_invalid_types():
    """Verify invalid types for allowed paths are rejected by validate_profile_patch."""
    # String age
    with pytest.raises(ProfileValidationError, match="must be an integer"):
        validate_profile_patch({
            "updates": {"personal.age": "twenty five"},
            "unknown_fields": [],
            "conflicts": [],
        })

    # Boolean age (bool is subclass of int in Python)
    with pytest.raises(ProfileValidationError, match="must be an integer"):
        validate_profile_patch({
            "updates": {"personal.age": True},
            "unknown_fields": [],
            "conflicts": [],
        })

    # Non-positive height
    with pytest.raises(ProfileValidationError, match="must be greater than 0"):
        validate_profile_patch({
            "updates": {"personal.height_cm": -175.0},
            "unknown_fields": [],
            "conflicts": [],
        })

    # Days per week > 7
    with pytest.raises(ProfileValidationError, match="must be between 0 and 7"):
        validate_profile_patch({
            "updates": {"training.days_per_week": 8},
            "unknown_fields": [],
            "conflicts": [],
        })

    # Non-list injuries
    with pytest.raises(ProfileValidationError, match="must be a list"):
        validate_profile_patch({
            "updates": {"health.injuries": "knee pain"},
            "unknown_fields": [],
            "conflicts": [],
        })


def test_deterministic_validator_required_keys():
    """Verify missing required keys in dict patch raise ProfileValidationError."""
    missing_updates = {"unknown_fields": [], "conflicts": []}
    with pytest.raises(ProfileValidationError, match="missing required keys"):
        validate_profile_patch(missing_updates)

    missing_unknown = {"updates": {}, "conflicts": []}
    with pytest.raises(ProfileValidationError, match="missing required keys"):
        validate_profile_patch(missing_unknown)

    extra_key = {
        "updates": {},
        "unknown_fields": [],
        "conflicts": [],
        "unexpected_extra": True,
    }
    with pytest.raises(ProfileValidationError, match="unexpected top-level keys"):
        validate_profile_patch(extra_key)


def test_fitness_plan_schema_invariants():
    """Verify FitnessPlan schema remains intact with all required top-level components."""
    schema = get_fitness_plan_schema()
    assert schema["title"] == "FitnessPlan"
    assert set(schema["required"]) == {
        "client_id",
        "nutrition_plan",
        "workout_plan",
        "metadata",
    }

