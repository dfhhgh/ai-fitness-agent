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
- WeightTargetResult: reference range, initial milestone, and flags
  from the weight target determination module (optional on assessment
  and planning context; read-only for the LLM).
- ProteinResult: Layer A protein target (protein-v1); protein_g binds
  into NutritionTargets.protein_g only when status == OK.
- FatResult: Layer A fat target (fat-v1-rev1); fat_g binds
  into NutritionTargets.fat_g only when status == OK.

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

# Importing weight_target triggers NutritionAssessment /
# NutritionPlanningContext.model_rebuild() so the optional
# weight_target forward reference is always resolvable.
from app.nutrition.weight_target import (  # noqa: E402
    ReviewFlag,
    ValidationFlag,
    WeightTargetInput,
    WeightTargetResult,
    WeightTargetStatus,
    determine_weight_targets,
)

# Protein Calculator (protein-v1) — Layer A contracts + Layer B helpers.
from app.nutrition.protein import (  # noqa: E402
    ProteinGoal,
    ProteinInput,
    ProteinIssueCode,
    ProteinResult,
    ProteinStatus,
    bind_protein_target,
    build_protein_input,
    calculate_protein,
    map_goal_to_protein_goal,
)

# Fat Calculator (fat-v1-rev1) — Layer A contracts + Layer B helpers.
from app.nutrition.fat import (  # noqa: E402
    FatGoal,
    FatInput,
    FatIssueCode,
    FatResult,
    FatStatus,
    bind_fat_target,
    build_fat_input,
    calculate_fat,
    map_goal_to_fat_goal,
)

# Carbohydrate Calculator (carb-v1) — Layer A contracts.
from app.nutrition.carbohydrate import (  # noqa: E402
    CarbInput,
    CarbIssueCode,
    CarbResult,
    CarbStatus,
    calculate_carbohydrates,
)

# Nutrition Core Orchestrator (2.2.9) — Layer B composition.
from app.nutrition.orchestrator import (  # noqa: E402
    CoreAssessmentStatus,
    FiberResult,
    INBODY_WEIGHT_MISMATCH,
    NutritionCoreInput,
    NutritionCoreOrchestrator,
    ORCHESTRATOR_VERSION,
    WeightAuthorityResolver,
    WeightAuthoritySource,
    build_planning_context,
    is_planning_allowed,
    prefill_survey_weight,
)

__all__ = [
    "ActivityCategory",
    "AssessmentIssue",
    "AssessmentStatus",
    "CarbInput",
    "CarbIssueCode",
    "CarbResult",
    "CarbStatus",
    "CoreAssessmentStatus",
    "FatGoal",
    "FatInput",
    "FatIssueCode",
    "FatResult",
    "FatStatus",
    "FiberResult",
    "GoalType",
    "INBODY_WEIGHT_MISMATCH",
    "InputStatus",
    "InBodySnapshot",
    "NutritionAssessment",
    "NutritionAssessmentInput",
    "NutritionCalculation",
    "NutritionCoreInput",
    "NutritionCoreOrchestrator",
    "NutritionPlanningContext",
    "NutritionTargets",
    "ORCHESTRATOR_VERSION",
    "ProteinGoal",
    "ProteinInput",
    "ProteinIssueCode",
    "ProteinResult",
    "ProteinStatus",
    "RMRMethod",
    "ReviewFlag",
    "ValidationFlag",
    "WeightAuthorityResolver",
    "WeightAuthoritySource",
    "WeightTargetInput",
    "WeightTargetResult",
    "WeightTargetStatus",
    "bind_fat_target",
    "bind_protein_target",
    "build_fat_input",
    "build_planning_context",
    "build_protein_input",
    "calculate_carbohydrates",
    "calculate_fat",
    "calculate_protein",
    "determine_weight_targets",
    "is_planning_allowed",
    "map_goal_to_fat_goal",
    "map_goal_to_protein_goal",
    "prefill_survey_weight",
]
