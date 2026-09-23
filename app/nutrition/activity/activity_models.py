"""Activity classification contracts — input and result models.

These models define the structured inputs and outputs of the
ActivityClassifier. They are Pydantic v2 BaseModel with extra="forbid"
for type safety and JSON serialization.

Architecture:

    ClientProfile.training fields
            ↓
    Mapper (normalizes to structured enums)
            ↓
    ActivityClassificationInput
            ↓
    ActivityClassifier (deterministic)
            ↓
    ActivityClassificationResult
            ↓
    ActivityCategory → get_activity_factor() → float
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.nutrition.models import (
    ActivityCategory,
    ActivityClassificationStatus,
    DailyMovement,
    ExerciseIntensity,
    OccupationalActivity,
)


class ActivityClassificationInput(BaseModel):
    """Structured activity inputs for classification.

    This is NOT NutritionAssessmentInput. This is the raw structured
    data before normalization into a single ActivityCategory.

    The mapper constructs this from ClientProfile data.

    Pydantic enforces STRUCTURAL and TYPE safety only.
    RANGE validation is performed by the ActivityClassifier, which
    returns ERROR status for out-of-range values rather than raising
    ValidationError.

    Required fields:
        occupational_activity: Pre-classified work/daily activity level.
        daily_movement: Daily movement level outside of structured exercise.
        training_days_per_week: Training frequency (integer).

    Optional fields:
        training_duration_minutes: Average duration of training sessions.
        exercise_intensity: Self-reported exercise intensity.

    Attributes:
        occupational_activity: Occupational activity baseline.
        daily_movement: Daily movement level.
        training_days_per_week: Training frequency (integer, 0–7 validated
            by classifier).
        training_duration_minutes: Average session duration in minutes
            (≥0 validated by classifier).
        exercise_intensity: Self-reported exercise intensity.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Required (type-only validation; range validated by classifier) ---
    occupational_activity: OccupationalActivity = Field(
        description="Pre-classified occupational activity level"
    )
    daily_movement: DailyMovement = Field(
        description="Daily movement level outside of structured exercise"
    )
    training_days_per_week: int = Field(
        description="Training frequency (integer, 0–7 validated by classifier)"
    )

    # --- Optional (type-only validation; range validated by classifier) ---
    training_duration_minutes: Optional[int] = Field(
        default=None, description="Average session duration in minutes (≥0 validated by classifier)"
    )
    exercise_intensity: Optional[ExerciseIntensity] = Field(
        default=None, description="Self-reported exercise intensity"
    )


class ActivityClassificationResult(BaseModel):
    """Result of activity classification.

    When classification fails (INCOMPLETE, CONFLICT, ERROR), category
    and factor are None and issues describe exactly what went wrong.

    When classification succeeds (OK), all score fields are populated
    and issues is empty.

    Attributes:
        status: Classification status (OK, INCOMPLETE, CONFLICT, ERROR).
        issues: Structured issue codes for programmatic handling.
        activity_category: Determined category (None if not OK).
        activity_factor: Activity factor (None if not OK).
        baseline_score: Occupation baseline score 0–3 (None if not OK).
        daily_movement_adjustment: Daily movement adjustment 0 or 1
            (None if not OK).
        wes_units: Work Exercise Score — an engineering exercise-volume
            proxy. NOT actual MET-minutes and NOT measured physiological
            energy expenditure. None if not computed.
        upgrade_score: WES-based upgrade score 0–2 (None if not OK).
        final_score: Final composite score 0–3 (None if not OK).
        policy_version: Version string for audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    status: ActivityClassificationStatus
    issues: List[str] = Field(default_factory=list)

    # --- Classification output (populated only when status == OK) ---
    activity_category: Optional[ActivityCategory] = None
    activity_factor: Optional[float] = None

    # --- Score breakdown (for audit trail) ---
    baseline_score: Optional[int] = Field(default=None, ge=0, le=3)
    daily_movement_adjustment: Optional[int] = Field(default=None, ge=0, le=1)
    wes_units: Optional[int] = Field(default=None, ge=0)
    upgrade_score: Optional[int] = Field(default=None, ge=0, le=2)
    final_score: Optional[int] = Field(default=None, ge=0, le=3)

    # --- Metadata ---
    policy_version: str = Field(default="activity-v1")
