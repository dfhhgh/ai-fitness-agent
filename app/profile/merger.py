"""Deterministic profile merging logic applying validated patches to client profiles.

The merger is responsible for applying candidate updates from a ProfilePatch onto
an existing ClientProfile while preserving all omitted fields, enforcing list
replacement semantics, and preventing mutation of the original profile instance.
"""

from typing import Any, Dict, Union

from app.profile.models import ClientProfile, ProfilePatch
from app.profile.policies import ALLOWED_UPDATE_PATHS
from app.profile.validator import ProfileValidationError, validate_profile_patch


class ProfileMerger:
    """Deterministic merger applying ProfilePatch updates to a ClientProfile."""

    @staticmethod
    def merge(
        profile: ClientProfile,
        patch: Union[ProfilePatch, Dict[str, Any]],
    ) -> ClientProfile:
        """Apply a validated ProfilePatch to an existing ClientProfile.

        Semantics:
        - Deep-copies the existing profile so callers never experience accidental mutations.
        - Preserves all fields not explicitly provided in the patch.
        - Replaces list fields directly (no implicit append or deduplication).
        - Explicit ``None`` values are applied for nullable fields.
        - Defensively rejects arbitrary update paths and InBody paths.
        - Ignores ``unknown_fields`` and ``conflicts`` without premature business logic.

        Args:
            profile: The current ``ClientProfile``.
            patch: A ``ProfilePatch`` model or dict of patch data.

        Returns:
            A new, updated ``ClientProfile`` instance.

        Raises:
            ProfileValidationError: If the patch violates path constraints or types.
        """
        # Defensive validation: ensure patch is valid before applying
        validate_profile_patch(patch)

        if isinstance(patch, ProfilePatch):
            updates = patch.updates
        elif isinstance(patch, dict):
            updates = patch.get("updates", {})
        else:
            raise ProfileValidationError(
                f"Expected ProfilePatch or dict, got {type(patch).__name__}"
            )

        # Deep copy to ensure original profile is never mutated
        merged = profile.model_copy(deep=True)

        for path, val in updates.items():
            if path not in ALLOWED_UPDATE_PATHS:
                raise ProfileValidationError(
                    f"Invalid update path: '{path}'. Path is not in ALLOWED_UPDATE_PATHS."
                )

            section_name, field_name = path.split(".", 1)
            section = getattr(merged, section_name, None)
            if section is None:
                raise ProfileValidationError(
                    f"Profile section '{section_name}' does not exist on ClientProfile."
                )

            if not hasattr(section, field_name):
                raise ProfileValidationError(
                    f"Field '{field_name}' does not exist on section '{section_name}'."
                )

            # Defensive copy for mutable list fields to avoid shared references
            if isinstance(val, list):
                val = list(val)

            setattr(section, field_name, val)

        return merged


def merge_profile(
    profile: ClientProfile,
    patch: Union[ProfilePatch, Dict[str, Any]],
) -> ClientProfile:
    """Convenience function to merge a ProfilePatch into a ClientProfile."""
    return ProfileMerger.merge(profile=profile, patch=patch)


# Convenient alias
merge_profile_patch = merge_profile
