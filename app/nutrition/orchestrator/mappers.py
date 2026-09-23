"""Adapters and mapping boundaries for Nutrition Core Orchestrator 2.2.9.

Responsibilities:
- GoalType -> ProteinGoal adapter (1:1 mapping).
- GoalType -> FatGoal adapter (1:1 mapping).
- GoalType -> WeightTargetGoal adapter (filters unsupported MUSCLE_GAIN).
- Planning gate validation: is_planning_allowed.
- Assembly of NutritionPlanningContext from NutritionAssessment.

Follow-up (not a 2.2.9 blocker): NutritionPlanningContext.training_duration
is documented as raw profile tenure (e.g. "2 months"). The current fallback
below may substitute survey session length (e.g. "45 min") when profile
duration is absent. Tenure and per-session duration are different concepts;
splitting them requires a contract change deferred past 2.2.9. Macro
calculation, status aggregation, Option B targets, and the planning gate
are unaffected.
"""

from typing import Optional

from app.nutrition.fat import FatGoal, map_goal_to_fat_goal
from app.nutrition.models import GoalType
from app.nutrition.orchestrator.contracts import (
    NutritionAssessment,
    NutritionPlanningContext,
    NutritionTargets,
)
from app.nutrition.protein import ProteinGoal, map_goal_to_protein_goal
from app.nutrition.weight_target.models import WeightTargetGoal


def map_goal_to_weight_target_goal(
    goal: Optional[GoalType],
) -> Optional[WeightTargetGoal]:
    """Map shared GoalType to WeightTargetGoal.

    weight-target-v1-rev1 supports:
    - MAINTENANCE
    - WEIGHT_LOSS
    - WEIGHT_GAIN

    MUSCLE_GAIN is rejected/unsupported in V1 (returns None).
    """
    if goal in (GoalType.MAINTENANCE, GoalType.WEIGHT_LOSS, GoalType.WEIGHT_GAIN):
        return goal  # Literal matches GoalType enum values
    return None


def is_planning_allowed(targets: Optional[NutritionTargets]) -> bool:
    """Evaluate hard planning gate according to Option B.

    Planning is allowed IF AND ONLY IF all 4 authoritative macro values
    (calories, protein, fat, carbohydrates) are present and non-null.

    Fiber absence does not block planning.
    Review flags do not block planning.
    """
    if targets is None:
        return False
    return (
        targets.calories_kcal is not None
        and targets.protein_g is not None
        and targets.fat_g is not None
        and targets.carbohydrates_g is not None
    )


def build_planning_context(
    assessment: NutritionAssessment,
) -> Optional[NutritionPlanningContext]:
    """Assemble NutritionPlanningContext for downstream Layer C LLM planner.

    Returns None if authoritative targets are missing (planning gate fails).
    Does NOT pass calculator implementation details or secrets.
    """
    if not is_planning_allowed(assessment.targets) or assessment.targets is None:
        return None

    inp = assessment.input_snapshot
    profile = inp.client_profile
    survey = inp.nutrition_input

    # Injuries context (context only — zero formula impact)
    injuries_list = list(profile.health.injuries) if profile.health.injuries is not None else []

    training_duration = getattr(profile.training, "duration", None)
    if training_duration is None and survey.training_duration_minutes is not None:
        training_duration = f"{survey.training_duration_minutes} min"

    return NutritionPlanningContext(
        age=survey.age,
        gender=survey.gender,
        height_cm=survey.height_cm,
        current_weight_kg=(
            assessment.resolved_current_weight_kg
            if assessment.resolved_current_weight_kg is not None
            else survey.weight_kg
        ),
        weight_authority_source=assessment.weight_authority_source,
        goal_type=survey.goal_type,
        target_weight_kg=survey.target_weight_kg,
        weight_change_target_kg=survey.weight_change_target_kg,
        training_days_per_week=survey.training_days_per_week,
        training_duration=training_duration,
        training_experience=getattr(profile.training, "experience", None),
        work_activity=survey.work_activity,
        activity_description=getattr(profile.training, "activity_description", None),
        exercise_intensity=survey.exercise_intensity,
        injuries=injuries_list,
        food_preferences=list(profile.nutrition.food_preferences),
        disliked_foods=list(profile.nutrition.disliked_foods),
        disliked_activities=list(profile.nutrition.disliked_activities),
        inbody=inp.inbody_snapshot,
        targets=assessment.targets,
        weight_target=assessment.weight_target_result,
        review_flags=list(assessment.review_flags),
        warnings=list(assessment.warnings),
        issues=list(assessment.issues),
    )


__all__ = [
    "FatGoal",
    "ProteinGoal",
    "WeightTargetGoal",
    "build_planning_context",
    "is_planning_allowed",
    "map_goal_to_fat_goal",
    "map_goal_to_protein_goal",
    "map_goal_to_weight_target_goal",
]
