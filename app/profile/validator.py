"""Deterministic validation logic for ClientProfile and ProfilePatch.

Enforces allowed update paths, value types, and semantic boundaries
as defined in the authoritative schema contracts and policies.
"""

from typing import Any, Dict, List, Union

from app.profile.models import ClientProfile, ProfilePatch
from app.profile.policies import ALLOWED_UPDATE_PATHS


class ProfileValidationError(ValueError):
    """Raised when a profile or profile patch violates deterministic validation rules."""
    pass


def validate_profile_patch(patch: Union[ProfilePatch, Dict[str, Any]]) -> None:
    """Deterministically validate a ProfilePatch instance or dict representation.

    Enforces:
    - Required patch keys: updates, unknown_fields, conflicts
    - No arbitrary update paths (must be in ALLOWED_UPDATE_PATHS)
    - InBody fields are strictly rejected
    - Type and range validation for every updated field

    Args:
        patch: A ``ProfilePatch`` model or dict.

    Raises:
        ProfileValidationError: If any path, type, or constraint is violated.
    """
    if isinstance(patch, ProfilePatch):
        updates = patch.updates
        unknown_fields = patch.unknown_fields
        conflicts = patch.conflicts
    elif isinstance(patch, dict):
        required_keys = {"updates", "unknown_fields", "conflicts"}
        missing_keys = required_keys - set(patch.keys())
        if missing_keys:
            raise ProfileValidationError(
                f"ProfilePatch missing required keys: {sorted(missing_keys)}"
            )

        extra_keys = set(patch.keys()) - required_keys
        if extra_keys:
            raise ProfileValidationError(
                f"ProfilePatch contains unexpected top-level keys: {sorted(extra_keys)}"
            )

        updates = patch["updates"]
        unknown_fields = patch["unknown_fields"]
        conflicts = patch["conflicts"]

        if not isinstance(updates, dict):
            raise ProfileValidationError(
                f"ProfilePatch 'updates' must be a dict, got {type(updates).__name__}"
            )
        if not isinstance(unknown_fields, list):
            raise ProfileValidationError(
                f"ProfilePatch 'unknown_fields' must be a list, got {type(unknown_fields).__name__}"
            )
        if not isinstance(conflicts, list):
            raise ProfileValidationError(
                f"ProfilePatch 'conflicts' must be a list, got {type(conflicts).__name__}"
            )
    else:
        raise ProfileValidationError(
            f"Expected ProfilePatch or dict, got {type(patch).__name__}"
        )

    # Validate unknown_fields and conflicts types
    for item in unknown_fields:
        if not isinstance(item, str):
            raise ProfileValidationError(
                f"Items in 'unknown_fields' must be strings, got {type(item).__name__} ({item!r})"
            )
    for item in conflicts:
        if not isinstance(item, dict):
            raise ProfileValidationError(
                f"Items in 'conflicts' must be dicts, got {type(item).__name__} ({item!r})"
            )

    # Validate each update path and value
    for path, val in updates.items():
        if path.startswith("inbody."):
            raise ProfileValidationError(
                f"Invalid update path: '{path}'. InBody fields cannot be updated via ProfilePatch."
            )

        if path not in ALLOWED_UPDATE_PATHS:
            raise ProfileValidationError(
                f"Invalid update path: '{path}'. Arbitrary paths are strictly forbidden. "
                f"Must be one of: {sorted(ALLOWED_UPDATE_PATHS)}"
            )

        _validate_field_value(path, val)


def _validate_field_value(path: str, val: Any) -> None:
    """Validate type and value boundaries for a specific allowed update path."""
    if path == "personal.age":
        if val is not None:
            if not isinstance(val, int) or isinstance(val, bool):
                raise ProfileValidationError(
                    f"'{path}' must be an integer, got {type(val).__name__} ({val!r})"
                )
            if val < 0:
                raise ProfileValidationError(f"'{path}' must be non-negative, got {val}")

    elif path == "personal.gender":
        if val is not None and not isinstance(val, str):
            raise ProfileValidationError(
                f"'{path}' must be a string or null, got {type(val).__name__} ({val!r})"
            )

    elif path in ("personal.height_cm", "personal.weight_kg", "goal.target_weight_kg"):
        if val is not None:
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise ProfileValidationError(
                    f"'{path}' must be a numeric value, got {type(val).__name__} ({val!r})"
                )
            if val <= 0:
                raise ProfileValidationError(f"'{path}' must be greater than 0, got {val}")

    elif path == "goal.weight_change_target_kg":
        if val is not None:
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise ProfileValidationError(
                    f"'{path}' must be a numeric value, got {type(val).__name__} ({val!r})"
                )

    elif path == "goal.type":
        if val is not None and not isinstance(val, str):
            raise ProfileValidationError(
                f"'{path}' must be a string or null, got {type(val).__name__} ({val!r})"
            )

    elif path == "training.days_per_week":
        if val is not None:
            if not isinstance(val, int) or isinstance(val, bool):
                raise ProfileValidationError(
                    f"'{path}' must be an integer, got {type(val).__name__} ({val!r})"
                )
            if not (0 <= val <= 7):
                raise ProfileValidationError(
                    f"'{path}' must be between 0 and 7, got {val}"
                )

    elif path == "training.duration":
        if val is not None:
            if not isinstance(val, (str, int, float)) or isinstance(val, bool):
                raise ProfileValidationError(
                    f"'{path}' must be a string or number, got {type(val).__name__} ({val!r})"
                )

    elif path in ("training.experience", "training.activity_description"):
        if val is not None and not isinstance(val, str):
            raise ProfileValidationError(
                f"'{path}' must be a string or null, got {type(val).__name__} ({val!r})"
            )

    elif path == "health.injuries":
        if val is not None:
            if not isinstance(val, list):
                raise ProfileValidationError(
                    f"'{path}' must be a list of strings or null, got {type(val).__name__} ({val!r})"
                )
            for item in val:
                if not isinstance(item, str):
                    raise ProfileValidationError(
                        f"Items in '{path}' must be strings, got {type(item).__name__} ({item!r})"
                    )

    elif path in (
        "nutrition.food_preferences",
        "nutrition.disliked_foods",
        "nutrition.disliked_activities",
    ):
        if not isinstance(val, list):
            raise ProfileValidationError(
                f"'{path}' must be a list of strings, got {type(val).__name__} ({val!r})"
            )
        for item in val:
            if not isinstance(item, str):
                raise ProfileValidationError(
                    f"Items in '{path}' must be strings, got {type(item).__name__} ({item!r})"
                )


# Convenient alias
validate_patch = validate_profile_patch
