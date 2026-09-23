"""Nutrition Core Orchestrator — Milestone 2.2.9.

Deterministic Layer B composition and coordination service for the Nutrition Core.
"""

from app.nutrition.orchestrator.contracts import (
    CoreAssessmentStatus,
    FiberResult,
    NutritionAssessment,
    NutritionCoreInput,
    NutritionPlanningContext,
    NutritionTargets,
    WeightAuthoritySource,
)
from app.nutrition.orchestrator.mappers import (
    build_planning_context,
    is_planning_allowed,
    map_goal_to_weight_target_goal,
)
from app.nutrition.orchestrator.orchestrator import (
    ORCHESTRATOR_VERSION,
    NutritionCoreOrchestrator,
)
from app.nutrition.orchestrator.resolver import (
    INBODY_WEIGHT_MISMATCH,
    WeightAuthorityResolver,
    prefill_survey_weight,
)

__all__ = [
    "CoreAssessmentStatus",
    "FiberResult",
    "INBODY_WEIGHT_MISMATCH",
    "NutritionAssessment",
    "NutritionCoreInput",
    "NutritionCoreOrchestrator",
    "NutritionPlanningContext",
    "NutritionTargets",
    "ORCHESTRATOR_VERSION",
    "WeightAuthorityResolver",
    "WeightAuthoritySource",
    "build_planning_context",
    "is_planning_allowed",
    "map_goal_to_weight_target_goal",
    "prefill_survey_weight",
]
