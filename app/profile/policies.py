"""Field update policies and authoritative allowed paths for profile patches.

This module defines the single source of truth for allowed update paths and
field-specific conflict policies in the deterministic profile layer.

Conflict policy overview
------------------------
Each allowed update path belongs to exactly one of three categories:

1. **Contradiction-sensitive** (``CONTRADICTION_SENSITIVE_FIELDS``)
   During the current onboarding interview, if an existing non-None value
   differs from an incoming value, the detector reports a conflict and the
   later interview layer asks for clarification.

   These fields are NOT universally immutable. Some of them (e.g.
   ``personal.age``, ``goal.target_weight_kg``, ``training.days_per_week``)
   may legitimately change over time in a profile-update workflow that has
   temporal context. The current onboarding MVP treats any differing value
   as a contradiction because no temporal reasoning is available yet.

2. **Mutable** (``MUTABLE_FIELDS``)
   Fields whose values naturally change over time (e.g. current body weight).
   A different incoming value does NOT produce a conflict; the patch
   represents a normal update.

3. **List** (``LIST_FIELDS``)
   Fields with list semantics. The merger replaces the entire list; conflict
   detection does not apply. The merger handles these via direct replacement.
"""

from typing import FrozenSet

# Authoritative list of allowed update paths for ProfilePatch
ALLOWED_UPDATE_PATHS: FrozenSet[str] = frozenset({
    "personal.age",
    "personal.gender",
    "personal.height_cm",
    "personal.weight_kg",
    "goal.type",
    "goal.target_weight_kg",
    "goal.weight_change_target_kg",
    "training.days_per_week",
    "training.duration",
    "training.experience",
    "training.activity_description",
    "health.injuries",
    "nutrition.food_preferences",
    "nutrition.disliked_foods",
    "nutrition.disliked_activities",
})

# Contradiction-sensitive fields: current onboarding interview policy.
#
# If the existing value is not None and differs from the incoming value,
# the detector reports a conflict. The interview layer then asks for
# clarification.
#
# NOTE: Some of these fields (e.g. personal.age, goal.target_weight_kg,
# training.days_per_week) can legitimately change over time. A future
# profile-update workflow with temporal context may reclassify them.
# For the current onboarding MVP, all differing values are contradictions.
CONTRADICTION_SENSITIVE_FIELDS: FrozenSet[str] = frozenset({
    "personal.age",
    "personal.gender",
    "personal.height_cm",
    "goal.type",
    "goal.target_weight_kg",
    "goal.weight_change_target_kg",
    "training.days_per_week",
    "training.duration",
    "training.experience",
    "training.activity_description",
})

# Mutable fields: values naturally change over time.
# A different incoming value is a normal update, not a contradiction.
MUTABLE_FIELDS: FrozenSet[str] = frozenset({
    "personal.weight_kg",
})

# List fields: replacement semantics handled by the merger.
# Conflict detection does not apply to these fields.
LIST_FIELDS: FrozenSet[str] = frozenset({
    "health.injuries",
    "nutrition.food_preferences",
    "nutrition.disliked_foods",
    "nutrition.disliked_activities",
})
