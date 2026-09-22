"""Nutrition Core V1 — deterministic contracts and data models.

All models are Pydantic v2 BaseModel with extra="forbid" for:
- JSON serialization/deserialization
- Structural validation
- Type safety
- Consistency with ClientProfile conventions

This module contains NO calculation logic. It only defines:

- Enums for goal types, activity categories, status codes, RMR methods
- Input contracts (NutritionAssessmentInput, InBodySnapshot)
- Output contracts (NutritionCalculation, NutritionAssessment, NutritionTargets)
- Planning contract (NutritionPlanningContext)
- Structured issue type (AssessmentIssue)

Architecture:

                  ClientProfile
                       │
             ┌─────────┴──────────┐
             ↓                    ↓
   Assessment mapping      Planning mapping
             ↓                    ↓
NutritionAssessmentInput   NutritionPlanningContext
             ↓                    ↑
    Deterministic Core      NutritionAssessment
             ↓                    │
    NutritionCalculation        │
             ↓                    │
    NutritionAssessment         │
             ↓                    │
     NutritionTargets ──────────┘
             ↓
      Future LLM Planner

Key distinction:
- "Assessment" tells us what the deterministic system calculated and
  whether it can be used.
- "Planning Context" tells the future LLM what it needs to know to
  turn those authoritative targets into a practical personalized plan.
"""

from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GoalType(str, Enum):
    """Fitness goal type driving calorie and protein policy."""

    MAINTENANCE = "maintenance"
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MUSCLE_GAIN = "muscle_gain"


class ActivityCategory(str, Enum):
    """Deterministic activity classification categories.

    Each category maps to a specific activity factor in the TDEE calculation.

    IMPORTANT: This is a NORMALIZED/PRE-CLASSIFIED value. The classification
    mechanism (ActivityClassifier) belongs to a later phase. The mapping layer
    normalizes ClientProfile.training.activity_description into this enum
    before constructing NutritionAssessmentInput.

    Nutrition Core receives this as an input — it does NOT interpret
    Egyptian Arabic or classify raw activity descriptions.
    """

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


class RMRMethod(str, Enum):
    """Resting Metabolic Rate calculation method."""

    MIFFLIN_ST_JEOR = "mifflin_st_jeor"
    CUNNINGHAM = "cunningham"


class InputStatus(str, Enum):
    """Status of input data before calculation.

    OWNERSHIP: Input validator / mapper layer.

    Describes whether the input is structurally usable for calculation.
    This is NOT about nutritional safety — it is about data completeness
    and validity.

    - COMPLETE: All required fields present and structurally valid.
    - INCOMPLETE: Required fields missing (calculation cannot run).
    - INVALID: Fields present but values out of valid range.
    """

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


class AssessmentStatus(str, Enum):
    """Status of the nutrition assessment after calculation.

    OWNERSHIP: Nutrition Core safety evaluator.

    Describes the result/assessment after the deterministic nutrition
    calculation and safety evaluation. This is NOT about input
    completeness — it is about whether the calculated output is safe
    to use.

    - OK: All calculations valid, safe for delivery.
    - WARNING: Minor issues (e.g., unusual values), calculation valid.
    - REVIEW_REQUIRED: Requires human/expert review before delivery.
    - ERROR: Structural or calculation error, no valid output.
    """

    OK = "OK"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Structured Issues
# ---------------------------------------------------------------------------


class AssessmentIssue(BaseModel):
    """Structured issue attached to a nutrition assessment.

    Enables programmatic issue handling without string parsing.

    Attributes:
        code: Machine-readable issue code (e.g., "MISSING_GOAL",
            "CALORIES_BELOW_1200", "INVALID_WEIGHT").
        message: Human-readable description of the issue.
        field: Optional reference to the specific field causing the issue.
    """

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field: Optional[str] = None


# ---------------------------------------------------------------------------
# Input Contracts
# ---------------------------------------------------------------------------


class NutritionAssessmentInput(BaseModel):
    """All human facts required by the deterministic nutrition calculator.

    This is the bridge between ClientProfile and Nutrition Core.
    The mapper constructs this from ClientProfile + InBody data.

    DO NOT include derived values (RMR, TDEE, activity factor, calorie
    targets, macro targets). Those belong to outputs.

    DO NOT invent defaults for missing fields. Missing required information
    must remain missing (use None for optional fields).

    Attributes:
        age: Age in years, ≥ 0.
        gender: Biological sex for RMR calculation ("male" | "female").
        height_cm: Height in centimeters, > 0.
        weight_kg: The weight selected as authoritative for this assessment.
            The mapper selects this according to an explicit future policy
            (e.g., InBody weight vs profile weight). Nutrition Core does
            NOT decide precedence — it receives the selected value.
        goal_type: Fitness goal driving calorie/protein policy.
        target_weight_kg: Optional target weight in kg.
        weight_change_target_kg: Optional weight change amount in kg.
        training_days_per_week: Training frequency, 0–7.
        work_activity: Pre-classified/normalized activity category supplied
            by the mapping/normalization boundary. The classification
            mechanism belongs to a later phase.
        training_duration_minutes: Optional normalized training duration.
        exercise_intensity: Reserved for V2, not consumed in V1.
        assessment_date: ISO 8601 date of this assessment.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Personal (required) ---
    age: int = Field(ge=0, description="Age in years")
    gender: str = Field(description="Biological sex: 'male' or 'female'")
    height_cm: float = Field(gt=0, description="Height in centimeters")
    weight_kg: float = Field(gt=0, description="Current body weight in kg")

    # --- Goal (required) ---
    goal_type: GoalType = Field(description="Fitness goal type")

    # --- Goal (optional) ---
    target_weight_kg: Optional[float] = Field(default=None, gt=0)
    weight_change_target_kg: Optional[float] = Field(default=None)

    # --- Activity (required) ---
    training_days_per_week: int = Field(ge=0, le=7)
    work_activity: ActivityCategory = Field(
        description="Pre-classified work/daily activity category"
    )

    # --- Activity (optional) ---
    training_duration_minutes: Optional[int] = Field(default=None, ge=0)
    exercise_intensity: Optional[str] = Field(
        default=None, description="Reserved for V2"
    )

    # --- Metadata ---
    assessment_date: Optional[str] = Field(
        default=None, description="ISO 8601 date"
    )


class InBodySnapshot(BaseModel):
    """InBody measurement data, independent from NutritionAssessmentInput.

    InBody is a measurement with uncertainty. It does NOT automatically
    override the assessment weight. The mapper selects the authoritative
    weight according to an explicit future policy.

    All fields are optional — an InBody snapshot may contain partial data.

    The data flow is:

        ClientProfile.weight_kg  (human-reported profile fact)
                +
        InBodySnapshot.weight_kg  (machine measurement)
                ↓
        Future mapper/policy
                ↓
        NutritionAssessmentInput.weight_kg  (selected authoritative weight)

    Attributes:
        measurement_date: ISO 8601 date of the measurement.
        weight_kg: Measured weight in kg.
        body_fat_percent: Body fat percentage, 0–100.
        fat_mass_kg: Fat mass in kg.
        skeletal_muscle_mass_kg: Skeletal muscle mass in kg.
        bmi: Body Mass Index (informational, derived).
        visceral_fat_level: Visceral fat level (informational).
    """

    model_config = ConfigDict(extra="forbid")

    measurement_date: Optional[str] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None, gt=0)
    body_fat_percent: Optional[float] = Field(default=None, ge=0, le=100)
    fat_mass_kg: Optional[float] = Field(default=None, ge=0)
    skeletal_muscle_mass_kg: Optional[float] = Field(default=None, ge=0)
    bmi: Optional[float] = Field(default=None, ge=0)
    visceral_fat_level: Optional[float] = Field(default=None, ge=0)


# ---------------------------------------------------------------------------
# Output Contracts
# ---------------------------------------------------------------------------


class NutritionCalculation(BaseModel):
    """Raw calculated values from the deterministic Nutrition Core.

    This represents the pure mathematical output — no status, no warnings,
    no review flags. It answers: "What did the calculator compute?"

    OWNERSHIP: Deterministic Nutrition Core.

    Attributes:
        rmr_kcal: Resting Metabolic Rate in kcal.
        rmr_method: Method used for RMR calculation.
        activity_factor: Activity multiplier applied to RMR.
        activity_category: Deterministic activity classification.
        tdee_kcal: Total Daily Energy Expenditure in kcal.
        target_calories_kcal: Goal-adjusted calorie target.
        protein_g: Protein target in grams.
        fat_g: Fat target in grams.
        carbohydrates_g: Carbohydrate target in grams.
        fiber_g: Fiber target in grams.
        goal_type: Goal used for calculation.
        current_weight_kg: Weight used as basis for calculation.
    """

    model_config = ConfigDict(extra="forbid")

    rmr_kcal: float = Field(ge=0)
    rmr_method: RMRMethod
    activity_factor: float = Field(gt=0)
    activity_category: ActivityCategory
    tdee_kcal: float = Field(ge=0)
    target_calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)
    fiber_g: float = Field(ge=0)
    goal_type: GoalType
    current_weight_kg: float = Field(gt=0)


class NutritionAssessment(BaseModel):
    """Complete nutrition assessment including safety evaluation.

    Combines the raw calculation with status, warnings, and structured
    issues. This is the authoritative record of the nutrition assessment.

    OWNERSHIP: Deterministic Nutrition Core + safety evaluator.

    The calculation is None when input is incomplete/invalid or when
    an error prevents calculation.

    Attributes:
        input_status: Structural completeness of input data.
        status: Safety/appropriateness of calculated output.
        calculation: Raw calculated values (None if not computable).
        warnings: Human-readable warning messages.
        review_flags: Flags requiring expert review.
        issues: Structured issues for programmatic handling.
        policy_version: Version string for audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    input_status: InputStatus
    status: AssessmentStatus
    calculation: Optional[NutritionCalculation] = None
    warnings: List[str] = Field(default_factory=list)
    review_flags: List[str] = Field(default_factory=list)
    issues: List[AssessmentIssue] = Field(default_factory=list)
    policy_version: str = Field(default="nutrition-v1")


class NutritionTargets(BaseModel):
    """Authoritative numerical nutrition targets for downstream consumers.

    Flattened, consumer-friendly view of NutritionAssessment.
    Contains only what the meal planner or API response needs.

    The full NutritionAssessment is stored for audit; NutritionTargets
    is the delivery contract.

    OWNERSHIP: Deterministic Nutrition Core (produced by calculation).

    Attributes:
        calories_kcal: Daily calorie target.
        protein_g: Daily protein target in grams.
        fat_g: Daily fat target in grams.
        carbohydrates_g: Daily carbohydrate target in grams.
        fiber_g: Daily fiber target in grams (optional).
        status: Assessment status for delivery decision.
        warnings: Any warnings to display to the user.
        review_flags: Flags requiring expert review.
        policy_version: Version string for audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    carbohydrates_g: float = Field(ge=0)
    fiber_g: Optional[float] = Field(default=None, ge=0)
    status: AssessmentStatus
    warnings: List[str] = Field(default_factory=list)
    review_flags: List[str] = Field(default_factory=list)
    policy_version: str = Field(default="nutrition-v1")


# ---------------------------------------------------------------------------
# Planning Contract
# ---------------------------------------------------------------------------


class NutritionPlanningContext(BaseModel):
    """Everything the LLM Nutrition Planner needs to create a practical plan.

    Combines authoritative numerical targets with client context for
    personalized plan generation.

    The planner receives NutritionTargets through this context.
    The planner must NOT recalculate targets — they are authoritative.

    OWNERSHIP: Mapping layer (constructs from ClientProfile + assessment).

    The planning context preserves relevant client context that the LLM
    planner needs to personalize meal structure and practical choices
    without needing to reconstruct information from free text.

    Attributes:
        # Client context
        age: Age in years.
        gender: Biological sex.
        height_cm: Height in cm.
        current_weight_kg: Current body weight in kg.
        goal_type: Fitness goal.
        target_weight_kg: Optional target weight.
        weight_change_target_kg: Optional weight change amount.
        training_days_per_week: Training frequency.
        training_duration: Raw training duration from profile (e.g., "2 months").
        training_experience: Experience level from profile (e.g., "beginner").
        work_activity: Pre-classified activity category.
        activity_description: Raw activity description from profile.
        exercise_intensity: Optional exercise intensity if available.
        injuries: List of reported injuries/health issues.
        food_preferences: Preferred foods.
        disliked_foods: Foods to avoid.
        disliked_activities: Activities to avoid.
        # InBody context
        inbody: Optional InBody snapshot (measurement, not absolute truth).
        # Authoritative targets
        targets: NutritionTargets from deterministic Nutrition Core.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Client context ---
    age: int = Field(ge=0)
    gender: str
    height_cm: float = Field(gt=0)
    current_weight_kg: float = Field(gt=0)
    goal_type: GoalType
    target_weight_kg: Optional[float] = Field(default=None, gt=0)
    weight_change_target_kg: Optional[float] = Field(default=None)
    training_days_per_week: int = Field(ge=0, le=7)
    training_duration: Optional[Union[str, float, int]] = Field(
        default=None, description="Raw training duration from profile"
    )
    training_experience: Optional[str] = Field(
        default=None, description="Experience level from profile"
    )
    work_activity: ActivityCategory
    activity_description: Optional[str] = Field(
        default=None, description="Raw activity description from profile"
    )
    exercise_intensity: Optional[str] = Field(
        default=None, description="Exercise intensity if available"
    )
    injuries: List[str] = Field(default_factory=list)
    food_preferences: List[str] = Field(default_factory=list)
    disliked_foods: List[str] = Field(default_factory=list)
    disliked_activities: List[str] = Field(default_factory=list)

    # --- InBody context ---
    inbody: Optional[InBodySnapshot] = None

    # --- Authoritative targets ---
    targets: NutritionTargets
