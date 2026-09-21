"""Field update policies and authoritative allowed paths for profile patches.

This module defines the single source of truth for allowed update paths in the
deterministic profile layer.
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
