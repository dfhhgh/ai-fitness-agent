"""Deterministic conflict detection between an existing ClientProfile and an incoming ProfilePatch.

This module is the authoritative source for conflict detection. It does NOT resolve
conflicts — it only reports them. LLM-generated conflicts in the patch are ignored;
the deterministic detector inspects the actual profile and patch values independently.

Conflict classification (per field policy):
- CONTRADICTION_SENSITIVE_FIELDS: existing non-None != incoming  =>  conflict
- MUTABLE_FIELDS: any change is a normal update  =>  no conflict
- LIST_FIELDS: replacement semantics handled by merger  =>  no conflict
"""

from typing import Any, Dict, List, Union

from app.profile.models import ClientProfile, ProfilePatch
from app.profile.policies import (
    ALLOWED_UPDATE_PATHS,
    CONTRADICTION_SENSITIVE_FIELDS,
    LIST_FIELDS,
    MUTABLE_FIELDS,
)
from app.profile.validator import ProfileValidationError, validate_profile_patch


class Conflict:
    """Structured representation of a detected conflict between existing and incoming values.

    Attributes:
        path: Dot-notation field path (e.g. ``personal.age``).
        existing_value: Current value stored in the profile.
        incoming_value: New value proposed by the patch.
        reason: Deterministic reason code describing the conflict.
    """

    __slots__ = ("path", "existing_value", "incoming_value", "reason")

    def __init__(self, path: str, existing_value: Any, incoming_value: Any, reason: str) -> None:
        self.path = path
        self.existing_value = existing_value
        self.incoming_value = incoming_value
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "existing_value": self.existing_value,
            "incoming_value": self.incoming_value,
            "reason": self.reason,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Conflict):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"Conflict(path={self.path!r}, existing_value={self.existing_value!r}, "
            f"incoming_value={self.incoming_value!r}, reason={self.reason!r})"
        )


def _get_nested_value(obj: Any, path: str) -> Any:
    """Retrieve a value from a nested object using a dot-notation path."""
    parts = path.split(".")
    current = obj
    for part in parts:
        current = getattr(current, part, None)
        if current is None and part != parts[-1]:
            return None
    return current


def _is_list_field(path: str) -> bool:
    """Return True if path is a list-replacement field (handled by merger)."""
    return path in LIST_FIELDS


def _is_mutable_field(path: str) -> bool:
    """Return True if path is a naturally mutable field (no conflict on change)."""
    return path in MUTABLE_FIELDS


def _is_contradiction_sensitive(path: str) -> bool:
    """Return True if path is contradiction-sensitive under current onboarding policy."""
    return path in CONTRADICTION_SENSITIVE_FIELDS


def detect_conflicts(
    profile: ClientProfile,
    patch: Union[ProfilePatch, Dict[str, Any]],
) -> List[Conflict]:
    """Detect conflicts between an existing ClientProfile and an incoming patch.

    The deterministic detector inspects the actual profile and patch values.
    LLM-generated ``conflicts`` in the patch are ignored entirely.

    Policy per field classification:
    - List fields: skip (merger handles replacement).
    - Mutable fields: skip (normal updates, no conflict).
    - Contradiction-sensitive fields: conflict if existing non-None differs from incoming.

    Args:
        profile: The current ``ClientProfile``.
        patch: A ``ProfilePatch`` model or dict of patch data.

    Returns:
        A list of ``Conflict`` objects. Empty list means no conflicts detected.

    Raises:
        ProfileValidationError: If the patch fails deterministic validation.
    """
    validate_profile_patch(patch)

    if isinstance(patch, ProfilePatch):
        updates = patch.updates
    elif isinstance(patch, dict):
        updates = patch.get("updates", {})
    else:
        raise ProfileValidationError(
            f"Expected ProfilePatch or dict, got {type(patch).__name__}"
        )

    conflicts: List[Conflict] = []

    for path, incoming_value in updates.items():
        if path not in ALLOWED_UPDATE_PATHS:
            raise ProfileValidationError(
                f"Invalid update path: '{path}'. Path is not in ALLOWED_UPDATE_PATHS."
            )

        if _is_list_field(path):
            continue

        if _is_mutable_field(path):
            continue

        if not _is_contradiction_sensitive(path):
            continue

        existing_value = _get_nested_value(profile, path)

        if existing_value is None:
            continue

        if existing_value == incoming_value:
            continue

        conflicts.append(
            Conflict(
                path=path,
                existing_value=existing_value,
                incoming_value=incoming_value,
                reason="existing_value_conflicts_with_incoming_value",
            )
        )

    return conflicts
