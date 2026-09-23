"""Deterministic activity classifier — Revision 3 implementation.

This module implements the complete deterministic classification logic
that converts structured activity inputs into an ActivityCategory.

STATUS: IMPLEMENTED — Revision 3 policy.

Validation order:
    1. Structural validation (Pydantic type checks)
    2. Range validation → ERROR for out-of-range values
    3. Missing-data validation → INCOMPLETE for missing conditional fields
    4. Conflict validation → CONFLICT for contradictory inputs
    5. Calculation (baseline, adjustment, WES, upgrade, final score)

Algorithm:
    1. Validate inputs (structural, range, missing-data, conflict)
    2. Compute occupation baseline score (0–3)
    3. Apply daily movement adjustment (+0 or +1)
    4. Compute WES (Work Exercise Score) from training data
    5. Compute WES upgrade score (0–2)
    6. Compute final score = baseline + adjustment + upgrade, capped at 3
    7. Map final score to ActivityCategory

This module REFUSES to classify when:
- Values are out of valid range (ERROR)
- Required conditional fields are missing (INCOMPLETE)
- Inputs are logically contradictory (CONFLICT)

This module does NOT:
- Interpret Egyptian Arabic
- Inspect free-form text
- Calculate nutrition
- Calculate TDEE
- Access ClientProfile directly
"""

from typing import List, Optional

from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.activity.activity_policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    OCCUPATION_BASELINES,
    INTENSITY_WEIGHTS,
    WES_UPGRADE_THRESHOLDS,
    get_activity_factor,
)
from app.nutrition.models import (
    ActivityCategory,
    ActivityClassificationStatus,
    DailyMovement,
    ExerciseIntensity,
    OccupationalActivity,
)


class ActivityClassifier:
    """Deterministic activity classifier — Revision 3.

    The classifier accepts structured activity inputs and returns an
    ActivityClassificationResult with the determined category, factor,
    and full score breakdown.

    Validation order:
        1. Structural (Pydantic type enforcement)
        2. Range validation → ERROR
        3. Missing-data validation → INCOMPLETE
        4. Conflict validation → CONFLICT
        5. Calculation → OK

    This module does NOT:
    - Interpret Egyptian Arabic
    - Inspect free-form text
    - Calculate nutrition
    - Calculate TDEE
    - Access ClientProfile
    """

    def classify(
        self, inputs: ActivityClassificationInput
    ) -> ActivityClassificationResult:
        """Classify structured activity inputs into an ActivityCategory.

        Args:
            inputs: Structured activity inputs.

        Returns:
            ActivityClassificationResult with category, factor, and
            score breakdown (when status == OK).
        """
        # Step 1: Range validation → ERROR
        range_issues = self._validate_ranges(inputs)
        if range_issues:
            return ActivityClassificationResult(
                status=ActivityClassificationStatus.ERROR,
                issues=range_issues,
                policy_version=ACTIVITY_POLICY_VERSION,
            )

        # Step 2: Missing-data validation → INCOMPLETE
        missing_issues = self._check_missing(inputs)
        if missing_issues:
            return ActivityClassificationResult(
                status=ActivityClassificationStatus.INCOMPLETE,
                issues=missing_issues,
                policy_version=ACTIVITY_POLICY_VERSION,
            )

        # Step 3: Conflict validation → CONFLICT
        conflict_issues = self._check_conflicts(inputs)
        if conflict_issues:
            return ActivityClassificationResult(
                status=ActivityClassificationStatus.CONFLICT,
                issues=conflict_issues,
                policy_version=ACTIVITY_POLICY_VERSION,
            )

        # Step 4: Compute occupation baseline score
        baseline_score = self._compute_baseline(inputs.occupational_activity)

        # Step 5: Compute daily movement adjustment
        daily_movement_adjustment = self._compute_daily_movement_adjustment(
            inputs.occupational_activity, inputs.daily_movement
        )

        # Step 6: Compute WES
        wes_units = self._compute_wes(
            inputs.training_days_per_week,
            inputs.training_duration_minutes,
            inputs.exercise_intensity,
        )

        # Step 7: Compute WES upgrade score
        upgrade_score = self._compute_wes_upgrade(wes_units)

        # Step 8: Compute final score (capped at 3)
        raw_score = baseline_score + daily_movement_adjustment + upgrade_score
        final_score = min(raw_score, 3)

        # Step 9: Map to category
        category = self._score_to_category(final_score)
        factor = get_activity_factor(category)

        return ActivityClassificationResult(
            status=ActivityClassificationStatus.OK,
            issues=[],
            activity_category=category,
            activity_factor=factor,
            baseline_score=baseline_score,
            daily_movement_adjustment=daily_movement_adjustment,
            wes_units=wes_units,
            upgrade_score=upgrade_score,
            final_score=final_score,
            policy_version=ACTIVITY_POLICY_VERSION,
        )

    def _validate_ranges(self, inputs: ActivityClassificationInput) -> List[str]:
        """Validate numeric ranges. Returns ERROR issues.

        training_days_per_week must be 0–7.
        training_duration_minutes, if present, must be ≥ 0.

        Returns:
            List of issue codes. Empty list means valid.
        """
        issues: List[str] = []

        if not (0 <= inputs.training_days_per_week <= 7):
            issues.append("INVALID_ACTIVITY_DATA")

        if inputs.training_duration_minutes is not None:
            if inputs.training_duration_minutes < 0:
                issues.append("INVALID_ACTIVITY_DATA")

        return issues

    def _check_missing(self, inputs: ActivityClassificationInput) -> List[str]:
        """Check for missing conditional data. Returns INCOMPLETE issues.

        If training_days_per_week > 0:
        - training_duration_minutes must not be None
        - exercise_intensity must not be None

        Returns:
            List of issue codes. Empty list means complete.
        """
        issues: List[str] = []

        if inputs.training_days_per_week > 0:
            if inputs.training_duration_minutes is None:
                issues.append("INCOMPLETE_ACTIVITY_DATA")
            if inputs.exercise_intensity is None:
                issues.append("INCOMPLETE_ACTIVITY_DATA")

        return issues

    def _check_conflicts(self, inputs: ActivityClassificationInput) -> List[str]:
        """Check for logically contradictory inputs. Returns CONFLICT issues.

        Conflict rules:
        1. training_days > 0 AND exercise_intensity == NONE → CONFLICT
        2. training_days == 0 AND exercise_intensity in {LIGHT, MODERATE, VIGOROUS} → CONFLICT
        3. training_days == 0 AND training_duration_minutes > 0 → CONFLICT

        Returns:
            List of issue codes. Empty list means no conflicts.
        """
        issues: List[str] = []

        # Rule 1: training_days > 0 AND intensity == NONE
        if (
            inputs.training_days_per_week > 0
            and inputs.exercise_intensity == ExerciseIntensity.NONE
        ):
            issues.append("ACTIVITY_CONFLICT")

        # Rule 2: training_days == 0 AND intensity in {LIGHT, MODERATE, VIGOROUS}
        if (
            inputs.training_days_per_week == 0
            and inputs.exercise_intensity in (
                ExerciseIntensity.LIGHT,
                ExerciseIntensity.MODERATE,
                ExerciseIntensity.VIGOROUS,
            )
        ):
            issues.append("ACTIVITY_CONFLICT")

        # Rule 3: training_days == 0 AND duration > 0
        if (
            inputs.training_days_per_week == 0
            and inputs.training_duration_minutes is not None
            and inputs.training_duration_minutes > 0
        ):
            issues.append("ACTIVITY_CONFLICT")

        return issues

    def _compute_baseline(self, occupation: OccupationalActivity) -> int:
        """Compute occupation baseline score (0–3).

        Args:
            occupation: Occupational activity level.

        Returns:
            Baseline score (0–3).
        """
        return OCCUPATION_BASELINES[occupation]

    def _compute_daily_movement_adjustment(
        self,
        occupation: OccupationalActivity,
        daily_movement: DailyMovement,
    ) -> int:
        """Compute daily movement adjustment (+0 or +1).

        The adjustment is +1 ONLY when:
        - Occupation is SEDENTARY, AND
        - Daily movement is HIGH

        All other combinations get +0.

        Args:
            occupation: Occupational activity level.
            daily_movement: Daily movement level.

        Returns:
            Adjustment value (0 or 1).
        """
        if (
            occupation == OccupationalActivity.SEDENTARY
            and daily_movement == DailyMovement.HIGH
        ):
            return 1
        return 0

    def _compute_wes(
        self,
        training_days: int,
        duration_minutes: Optional[int],
        intensity: Optional[ExerciseIntensity],
    ) -> int:
        """Compute Work Exercise Score (WES).

        WES = training_days × duration_minutes × intensity_weight

        WES is an engineering exercise-volume proxy.
        It is NOT actual MET-minutes and NOT measured physiological
        energy expenditure.

        When duration or intensity is None, WES is 0 (no training
        data to weight).

        Args:
            training_days: Training frequency, 0–7.
            duration_minutes: Average session duration in minutes.
            intensity: Self-reported exercise intensity.

        Returns:
            WES value (≥ 0, integer).
        """
        if duration_minutes is None or intensity is None:
            return 0

        intensity_weight = INTENSITY_WEIGHTS.get(intensity, 0)
        return training_days * duration_minutes * intensity_weight

    def _compute_wes_upgrade(self, wes_units: int) -> int:
        """Compute WES upgrade score (0–2) from WES value.

        Thresholds:
            WES < 600 → upgrade 0
            600 ≤ WES < 1800 → upgrade 1
            WES ≥ 1800 → upgrade 2

        Args:
            wes_units: Work Exercise Score value.

        Returns:
            Upgrade score (0–2).
        """
        for threshold, upgrade in WES_UPGRADE_THRESHOLDS:
            if wes_units < threshold:
                return upgrade
        # If no threshold matches (WES ≥ last threshold), return max upgrade
        return WES_UPGRADE_THRESHOLDS[-1][1]

    def _score_to_category(self, score: int) -> ActivityCategory:
        """Map final composite score to ActivityCategory.

        Score mapping:
            0 → SEDENTARY
            1 → LIGHT
            2 → MODERATE
            3 → HIGH

        Args:
            score: Final composite score (0–3).

        Returns:
            Corresponding ActivityCategory.
        """
        score_map = {
            0: ActivityCategory.SEDENTARY,
            1: ActivityCategory.LIGHT,
            2: ActivityCategory.MODERATE,
            3: ActivityCategory.HIGH,
        }
        return score_map[score]
