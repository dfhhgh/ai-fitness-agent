"""Nutrition Core Orchestrator contracts — models, enums, and data definitions.

These models define the Layer B composition boundaries for Milestone 2.2.9.
All contracts are frozen Pydantic v2 models with extra="forbid".

Policy versions:
- activity: activity-v1
- rmr: rmr-v1
- tdee: tdee-v1
- calorie: calorie-v1
- protein: protein-v1
- fat: fat-v1-rev1
- carb: carb-v1
- weight_target: weight-target-v1-rev1
- fiber: fiber-v1-placeholder
- orchestrator: 2.2.9
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.calorie_target.models import CalorieTargetResult
from app.nutrition.carbohydrate.models import CarbResult
from app.nutrition.fat.models import FatResult
from app.nutrition.models import (
    ActivityCategory,
    GoalType,
    InBodySnapshot,
    NutritionAssessmentInput,
)
from app.nutrition.protein.models import ProteinResult
from app.nutrition.rmr.rmr_models import RMRResult
from app.nutrition.tdee.tdee_models import TDEEResult
from app.nutrition.weight_target.models import WeightTargetResult
from app.profile.models import ClientProfile


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WeightAuthoritySource(str, Enum):
    """Authoritative source of body mass for calculation.

    Values:
        SURVEY: Used nutrition_input.weight_kg as provided in current session.
        PROFILE_PREFILL: Used ClientProfile.personal.weight_kg during pre-assembly.
        UNRESOLVED: Neither source available; weight-dependent nodes cannot run.
    """

    SURVEY = "SURVEY"
    PROFILE_PREFILL = "PROFILE_PREFILL"
    UNRESOLVED = "UNRESOLVED"


class CoreAssessmentStatus(str, Enum):
    """Overall status of the aggregated Nutrition Core assessment.

    Five-tier status model with strict precedence:
        ERROR > INVALID > INCOMPLETE > REVIEW_REQUIRED > COMPLETE

    Values:
        COMPLETE: All required calculations completed successfully; no review flags.
        INCOMPLETE: One or more required nodes incomplete or skipped.
        REVIEW_REQUIRED: Calculations completed or partially completed with safety/review triggers.
        INVALID: Domain-level violation (e.g. activity conflict, negative carb residual, underage).
        ERROR: Execution or arithmetic error.
    """

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INVALID = "INVALID"
    ERROR = "ERROR"


# Status precedence mapping for comparison (higher number = higher precedence)
STATUS_PRECEDENCE: Dict[CoreAssessmentStatus, int] = {
    CoreAssessmentStatus.ERROR: 5,
    CoreAssessmentStatus.INVALID: 4,
    CoreAssessmentStatus.INCOMPLETE: 3,
    CoreAssessmentStatus.REVIEW_REQUIRED: 2,
    CoreAssessmentStatus.COMPLETE: 1,
}


# ---------------------------------------------------------------------------
# Placeholder / Delivery Contracts
# ---------------------------------------------------------------------------


class FiberResult(BaseModel):
    """Non-blocking fiber placeholder for 2.2.9.

    Contributes neutral (no contribution) to Core status.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = "NOT_IMPLEMENTED"
    fiber_g: Optional[float] = None
    policy_version: str = "fiber-v1-placeholder"


class NutritionTargets(BaseModel):
    """Authoritative numerical nutrition targets (Option B success payload).

    Issued ONLY when all four core macros (calories, protein, fat, carbohydrates)
    are successfully calculated and valid. When calculation fails or is partial,
    assessment.targets is None.

    Attributes:
        calories_kcal: Authoritative daily calorie target in kcal.
        protein_g: Authoritative daily protein target in integer/float grams.
        fat_g: Authoritative daily fat target in integer/float grams.
        carbohydrates_g: Authoritative daily carbohydrate target in integer/float grams.
        fiber_g: Optional daily fiber target in grams (placeholder in V1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    calories_kcal: float = Field(ge=0, description="Authoritative daily calorie target")
    protein_g: float = Field(ge=0, description="Authoritative daily protein target in grams")
    fat_g: float = Field(ge=0, description="Authoritative daily fat target in grams")
    carbohydrates_g: float = Field(
        ge=0, description="Authoritative daily carbohydrate target in grams"
    )
    fiber_g: Optional[float] = Field(
        default=None, ge=0, description="Optional daily fiber target in grams"
    )


# ---------------------------------------------------------------------------
# Composite Input Contract (Layer B Boundary)
# ---------------------------------------------------------------------------


class NutritionCoreInput(BaseModel):
    """Thread-safe, immutable composite input for Nutrition Core Orchestrator.

    Encapsulates all client profile data, survey input, and optional device
    snapshots for a single assessment execution.

    Attributes:
        client_profile: Full onboarding and profile information.
        nutrition_input: Authoritative survey facts including required weight_kg.
        inbody_snapshot: Optional device measurement; NEVER enters calculation weight.
        activity_input: Optional structured activity inputs for ActivityClassifier.
        weight_authority_source: Optional tracking flag for pre-fill lineage.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    client_profile: ClientProfile
    nutrition_input: NutritionAssessmentInput
    inbody_snapshot: Optional[InBodySnapshot] = None
    activity_input: Optional[ActivityClassificationInput] = None
    weight_authority_source: Optional[WeightAuthoritySource] = None


# ---------------------------------------------------------------------------
# Output Assessment Record
# ---------------------------------------------------------------------------


class NutritionAssessment(BaseModel):
    """Complete, immutable nutrition assessment record preserving full lineage.

    Preserves input snapshot, resolved weight, authority source, all Layer A
    node results (present or None if skipped), consolidated flags/issues,
    and the authoritative NutritionTargets payload (Option B).

    Attributes:
        overall_status: Aggregated 5-tier status of the core assessment.
        input_snapshot: Frozen snapshot of the ingested inputs.
        resolved_current_weight_kg: Authoritative mass used for calculation.
        weight_authority_source: Provenance of the resolved weight.
        targets: Authoritative macro targets (None if macro chain incomplete/invalid).
        activity_result: Authoritative ActivityClassificationResult (or None).
        rmr_result: Authoritative RMRResult (or None).
        tdee_result: Authoritative TDEEResult (or None).
        calorie_target_result: Authoritative CalorieTargetResult (or None).
        protein_result: Authoritative ProteinResult (or None).
        fat_result: Authoritative FatResult (or None).
        carb_result: Authoritative CarbResult (or None).
        weight_target_result: Authoritative WeightTargetResult (or None).
        fiber_result: Fiber placeholder result.
        issues: Aggregated operational issue codes.
        warnings: Non-blocking warning messages.
        review_flags: Consolidated review/safety flags.
        orchestrator_version: Fixed orchestrator release version ("2.2.9").
        policy_versions: Map of policy versions for all coordinated engines.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    overall_status: CoreAssessmentStatus
    input_snapshot: NutritionCoreInput
    resolved_current_weight_kg: Optional[float] = None
    weight_authority_source: WeightAuthoritySource
    targets: Optional[NutritionTargets] = None

    # Individual node results (None if skipped or not run)
    activity_result: Optional[ActivityClassificationResult] = None
    rmr_result: Optional[RMRResult] = None
    tdee_result: Optional[TDEEResult] = None
    calorie_target_result: Optional[CalorieTargetResult] = None
    protein_result: Optional[ProteinResult] = None
    fat_result: Optional[FatResult] = None
    carb_result: Optional[CarbResult] = None
    weight_target_result: Optional[WeightTargetResult] = None
    fiber_result: Optional[FiberResult] = None

    # Consolidated diagnostics
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    review_flags: List[str] = Field(default_factory=list)

    # Provenance
    orchestrator_version: str = "2.2.9"
    policy_versions: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Planning Context Contract
# ---------------------------------------------------------------------------


class NutritionPlanningContext(BaseModel):
    """Read-only context payload for downstream LLM Nutrition Planning (Layer C).

    Provides authoritative numerical targets and relevant client background
    without giving the LLM permission or mechanisms to recalculate macros.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Demographics & mass
    age: int = Field(ge=0)
    gender: str
    height_cm: float = Field(gt=0)
    current_weight_kg: float = Field(gt=0)
    weight_authority_source: Optional[WeightAuthoritySource] = None

    # Goals
    goal_type: GoalType
    target_weight_kg: Optional[float] = None
    weight_change_target_kg: Optional[float] = None

    # Training & activity
    training_days_per_week: int = Field(ge=0, le=7)
    training_duration: Optional[Union[str, float, int]] = None
    training_experience: Optional[str] = None
    work_activity: ActivityCategory
    activity_description: Optional[str] = None
    exercise_intensity: Optional[str] = None

    # Health & preferences (context only)
    injuries: List[str] = Field(default_factory=list)
    food_preferences: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)

    # InBody context (read-only context, not for math)
    inbody: Optional[InBodySnapshot] = None

    # Authoritative targets (hard constraints)
    targets: NutritionTargets

    # Optional Weight Target milestone
    weight_target: Optional[WeightTargetResult] = None

    # Diagnostics for planner awareness
    review_flags: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
