"""Nutrition Core V1 — deterministic contracts and data models.

This package defines the input/output contracts for the deterministic
nutrition assessment pipeline. It contains NO calculation logic,
NO activity classification, NO food database, NO LLM integration.

The separation of responsibilities:

- ClientProfile: stores onboarding/profile information.
- NutritionAssessmentInput: contains facts needed for deterministic assessment.
- InBodySnapshot: contains a specific InBody measurement.
- NutritionAssessment: represents deterministic assessment results/status.
- NutritionTargets: contains authoritative numerical targets.
- NutritionPlanningContext: combines targets with client context for planning.

Architectural rule:

- Deterministic code produces NutritionTargets.
- LLM Nutrition Planner receives NutritionTargets + client context.
- LLM must NOT recalculate, override, or become the source of truth
  for calories/macros.
- Future deterministic Plan Validator verifies the LLM-generated plan
  against authoritative targets.
"""

from app.nutrition.models import (
    ActivityCategory,
    AssessmentIssue,
    AssessmentStatus,
    GoalType,
    InputStatus,
    InBodySnapshot,
    NutritionAssessment,
    NutritionAssessmentInput,
    NutritionCalculation,
    NutritionPlanningContext,
    NutritionTargets,
    RMRMethod,
)

__all__ = [
    "ActivityCategory",
    "AssessmentIssue",
    "AssessmentStatus",
    "GoalType",
    "InputStatus",
    "InBodySnapshot",
    "NutritionAssessment",
    "NutritionAssessmentInput",
    "NutritionCalculation",
    "NutritionPlanningContext",
    "NutritionTargets",
    "RMRMethod",
]
