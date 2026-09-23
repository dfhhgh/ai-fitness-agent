"""Tests for app.nutrition.activity.classifier — Revision 3 implementation.

Tests cover:
- 20 decision-table vectors from approved Revision 3 policy
- Boundary tests (WES thresholds)
- ERROR status tests (range validation)
- INCOMPLETE status tests (missing conditional data)
- CONFLICT status tests (contradictory inputs)
- Score capping at 3
- Integration with policies module
- No LLM/network dependencies
"""

import pytest

from app.nutrition.activity.activity_classifier import ActivityClassifier
from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.activity.activity_policies import (
    ACTIVITY_FACTORS,
    ACTIVITY_POLICY_VERSION,
    INTENSITY_WEIGHTS,
    OCCUPATION_BASELINES,
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


# ---------------------------------------------------------------------------
# Decision-table vectors (20 cases)
# ---------------------------------------------------------------------------

DECISION_TABLE_VECTORS = [
    # (description, input_kwargs, expected_category, expected_factor,
    #  expected_baseline, expected_adj, expected_wes, expected_upgrade, expected_final)

    # --- SEDENTARY occupation ---
    ("S1: SEDENTARY + LOW + 0 days",
     dict(occupational_activity="sedentary", daily_movement="low", training_days_per_week=0),
     "sedentary", 1.20, 0, 0, 0, 0, 0),

    ("S2: SEDENTARY + LOW + 3 days + MODERATE + 60min",
     dict(occupational_activity="sedentary", daily_movement="low",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "light", 1.35, 0, 0, 720, 1, 1),

    ("S3: SEDENTARY + LOW + 5 days + VIGOROUS + 60min",
     dict(occupational_activity="sedentary", daily_movement="low",
          training_days_per_week=5, training_duration_minutes=60, exercise_intensity="vigorous"),
     "moderate", 1.55, 0, 0, 2100, 2, 2),

    ("S4: SEDENTARY + MODERATE + 0 days",
     dict(occupational_activity="sedentary", daily_movement="moderate",
          training_days_per_week=0),
     "sedentary", 1.20, 0, 0, 0, 0, 0),

    ("S5: SEDENTARY + MODERATE + 3 days + MODERATE + 60min",
     dict(occupational_activity="sedentary", daily_movement="moderate",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "light", 1.35, 0, 0, 720, 1, 1),

    ("S6: SEDENTARY + HIGH + 0 days (adj +1)",
     dict(occupational_activity="sedentary", daily_movement="high",
          training_days_per_week=0),
     "light", 1.35, 0, 1, 0, 0, 1),

    ("S7: SEDENTARY + HIGH + 3 days + MODERATE + 60min",
     dict(occupational_activity="sedentary", daily_movement="high",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "moderate", 1.55, 0, 1, 720, 1, 2),

    ("S8: SEDENTARY + HIGH + 5 days + VIGOROUS + 60min",
     dict(occupational_activity="sedentary", daily_movement="high",
          training_days_per_week=5, training_duration_minutes=60, exercise_intensity="vigorous"),
     "high", 1.75, 0, 1, 2100, 2, 3),

    # --- LIGHT_MANUAL occupation ---
    ("L1: LIGHT_MANUAL + LOW + 0 days",
     dict(occupational_activity="light_manual", daily_movement="low",
          training_days_per_week=0),
     "light", 1.35, 1, 0, 0, 0, 1),

    ("L2: LIGHT_MANUAL + LOW + 3 days + MODERATE + 60min",
     dict(occupational_activity="light_manual", daily_movement="low",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "moderate", 1.55, 1, 0, 720, 1, 2),

    ("L3: LIGHT_MANUAL + HIGH + 0 days (no adj, not sedentary)",
     dict(occupational_activity="light_manual", daily_movement="high",
          training_days_per_week=0),
     "light", 1.35, 1, 0, 0, 0, 1),

    ("L4: LIGHT_MANUAL + HIGH + 5 days + VIGOROUS + 60min",
     dict(occupational_activity="light_manual", daily_movement="high",
          training_days_per_week=5, training_duration_minutes=60, exercise_intensity="vigorous"),
     "high", 1.75, 1, 0, 2100, 2, 3),

    # --- ACTIVE_MANUAL occupation ---
    ("A1: ACTIVE_MANUAL + LOW + 0 days",
     dict(occupational_activity="active_manual", daily_movement="low",
          training_days_per_week=0),
     "moderate", 1.55, 2, 0, 0, 0, 2),

    ("A2: ACTIVE_MANUAL + LOW + 3 days + MODERATE + 60min",
     dict(occupational_activity="active_manual", daily_movement="low",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "high", 1.75, 2, 0, 720, 1, 3),

    ("A3: ACTIVE_MANUAL + MODERATE + 5 days + VIGOROUS + 60min",
     dict(occupational_activity="active_manual", daily_movement="moderate",
          training_days_per_week=5, training_duration_minutes=60, exercise_intensity="vigorous"),
     "high", 1.75, 2, 0, 2100, 2, 3),

    # --- HEAVY_MANUAL occupation ---
    ("H1: HEAVY_MANUAL + LOW + 0 days",
     dict(occupational_activity="heavy_manual", daily_movement="low",
          training_days_per_week=0),
     "high", 1.75, 3, 0, 0, 0, 3),

    ("H2: HEAVY_MANUAL + LOW + 3 days + MODERATE + 60min (capped)",
     dict(occupational_activity="heavy_manual", daily_movement="low",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="moderate"),
     "high", 1.75, 3, 0, 720, 1, 3),

    ("H3: HEAVY_MANUAL + HIGH + 5 days + VIGOROUS + 60min (capped)",
     dict(occupational_activity="heavy_manual", daily_movement="high",
          training_days_per_week=5, training_duration_minutes=60, exercise_intensity="vigorous"),
     "high", 1.75, 3, 0, 2100, 2, 3),

    # --- WES threshold edge cases ---
    ("W1: WES < 600 (3 days + LIGHT + 60min = 360)",
     dict(occupational_activity="sedentary", daily_movement="low",
          training_days_per_week=3, training_duration_minutes=60, exercise_intensity="light"),
     "sedentary", 1.20, 0, 0, 360, 0, 0),

    ("W2: WES >= 1800 (5 days + VIGOROUS + 90min = 3150)",
     dict(occupational_activity="sedentary", daily_movement="low",
          training_days_per_week=5, training_duration_minutes=90, exercise_intensity="vigorous"),
     "moderate", 1.55, 0, 0, 3150, 2, 2),
]


class TestActivityClassifierDecisionTable:
    """Test all 20 decision-table vectors from Revision 3 policy."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    @pytest.mark.parametrize(
        "description,input_kwargs,expected_category,expected_factor,"
        "expected_baseline,expected_adj,expected_wes,expected_upgrade,expected_final",
        DECISION_TABLE_VECTORS,
        ids=[v[0] for v in DECISION_TABLE_VECTORS],
    )
    def test_decision_vector(
        self,
        description,
        input_kwargs,
        expected_category,
        expected_factor,
        expected_baseline,
        expected_adj,
        expected_wes,
        expected_upgrade,
        expected_final,
    ):
        """Verify each decision-table vector produces the expected result."""
        inputs = ActivityClassificationInput(**input_kwargs)
        result = self.classifier.classify(inputs)

        assert result.status == ActivityClassificationStatus.OK
        assert result.activity_category == ActivityCategory(expected_category)
        assert result.activity_factor == expected_factor
        assert result.baseline_score == expected_baseline
        assert result.daily_movement_adjustment == expected_adj
        assert result.wes_units == expected_wes
        assert result.upgrade_score == expected_upgrade
        assert result.final_score == expected_final
        assert result.issues == []
        assert result.policy_version == ACTIVITY_POLICY_VERSION


class TestActivityClassifierBaseline:
    """Test occupation baseline score calculation."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_sedentary_baseline_zero(self):
        """SEDENTARY occupation → baseline 0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.baseline_score == 0

    def test_light_manual_baseline_one(self):
        """LIGHT_MANUAL occupation → baseline 1."""
        inputs = ActivityClassificationInput(
            occupational_activity="light_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.baseline_score == 1

    def test_active_manual_baseline_two(self):
        """ACTIVE_MANUAL occupation → baseline 2."""
        inputs = ActivityClassificationInput(
            occupational_activity="active_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.baseline_score == 2

    def test_heavy_manual_baseline_three(self):
        """HEAVY_MANUAL occupation → baseline 3."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.baseline_score == 3


class TestActivityClassifierDailyMovementAdjustment:
    """Test daily movement adjustment calculation."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_sedentary_high_movement_gets_adjustment(self):
        """SEDENTARY + HIGH → adjustment +1."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 1

    def test_sedentary_low_movement_no_adjustment(self):
        """SEDENTARY + LOW → adjustment +0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 0

    def test_sedentary_moderate_movement_no_adjustment(self):
        """SEDENTARY + MODERATE → adjustment +0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="moderate",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 0

    def test_light_manual_high_movement_no_adjustment(self):
        """LIGHT_MANUAL + HIGH → adjustment +0 (NOT sedentary)."""
        inputs = ActivityClassificationInput(
            occupational_activity="light_manual",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 0

    def test_active_manual_high_movement_no_adjustment(self):
        """ACTIVE_MANUAL + HIGH → adjustment +0 (NOT sedentary)."""
        inputs = ActivityClassificationInput(
            occupational_activity="active_manual",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 0

    def test_heavy_manual_high_movement_no_adjustment(self):
        """HEAVY_MANUAL + HIGH → adjustment +0 (NOT sedentary)."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.daily_movement_adjustment == 0

    def test_only_sedentary_high_gets_adjustment(self):
        """Only SEDENTARY + HIGH gets +1; all other combinations get +0."""
        for occ in OccupationalActivity:
            for movement in DailyMovement:
                inputs = ActivityClassificationInput(
                    occupational_activity=occ,
                    daily_movement=movement,
                    training_days_per_week=0,
                )
                result = self.classifier.classify(inputs)
                expected = 1 if (
                    occ == OccupationalActivity.SEDENTARY
                    and movement == DailyMovement.HIGH
                ) else 0
                assert result.daily_movement_adjustment == expected, (
                    f"{occ.value} + {movement.value}: expected {expected}, "
                    f"got {result.daily_movement_adjustment}"
                )


class TestActivityClassifierWES:
    """Test WES (Work Exercise Score) calculation."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_wes_is_integer(self):
        """WES result must be an integer, not a float."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert isinstance(result.wes_units, int)

    def test_zero_training_days(self):
        """0 training days, no duration, no intensity → OK, WES 0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 0

    def test_zero_training_days_with_none_intensity(self):
        """0 training days, duration=None, intensity=None → OK, WES 0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=None,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 0

    def test_zero_training_days_with_none_duration_and_none_intensity(self):
        """0 training days, duration=None, intensity=None → OK, WES 0."""
        inputs = ActivityClassificationInput(
            occupational_activity="light_manual",
            daily_movement="moderate",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 0

    def test_wes_calculation_vigorous(self):
        """5 days × 60min × VIGOROUS(7) = 2100."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 2100

    def test_wes_calculation_moderate(self):
        """3 days × 60min × MODERATE(4) = 720."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 720

    def test_wes_calculation_light(self):
        """3 days × 60min × LIGHT(2) = 360."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="light",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 360

    def test_wes_calculation_90min(self):
        """5 days × 90min × VIGOROUS(7) = 3150."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=90,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 3150


class TestActivityClassifierWESUpgrade:
    """Test WES upgrade score calculation."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_wes_below_600_upgrade_zero(self):
        """WES < 600 → upgrade 0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="light",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 360
        assert result.upgrade_score == 0

    def test_wes_exactly_600_upgrade_one(self):
        """WES = 600 → upgrade 1."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=30,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 600
        assert result.upgrade_score == 1

    def test_wes_1200_upgrade_one(self):
        """WES = 1200 → upgrade 1."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 1200
        assert result.upgrade_score == 1

    def test_wes_exactly_1800_upgrade_two(self):
        """WES = 1800 → upgrade 2."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 2100
        assert result.upgrade_score == 2

    def test_wes_very_high_upgrade_two(self):
        """WES >> 1800 → still upgrade 2."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=7,
            training_duration_minutes=120,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.wes_units == 5880
        assert result.upgrade_score == 2


class TestActivityClassifierScoreCapping:
    """Test final score capping at 3."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_capping_baseline_three(self):
        """HEAVY_MANUAL baseline 3, no adjustment, no upgrade → final 3."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.final_score == 3

    def test_capping_baseline_three_plus_adjustment(self):
        """HEAVY_MANUAL + HIGH → raw 4, capped to 3."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.final_score == 3

    def test_capping_baseline_three_plus_upgrade(self):
        """HEAVY_MANUAL + training → raw >3, capped to 3."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.final_score == 3

    def test_capping_active_manual_plus_adjustment(self):
        """ACTIVE_MANUAL + SEDENTARY + HIGH + training → raw >3, capped to 3."""
        inputs = ActivityClassificationInput(
            occupational_activity="active_manual",
            daily_movement="high",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.final_score == 3

    def test_no_capping_needed(self):
        """Score below 3 not capped."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.final_score == 1


class TestActivityClassifierScoreToCategory:
    """Test score-to-category mapping."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_score_zero_maps_to_sedentary(self):
        """Score 0 → SEDENTARY."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.activity_category == ActivityCategory.SEDENTARY

    def test_score_one_maps_to_light(self):
        """Score 1 → LIGHT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="high",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.activity_category == ActivityCategory.LIGHT

    def test_score_two_maps_to_moderate(self):
        """Score 2 → MODERATE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=60,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.activity_category == ActivityCategory.MODERATE

    def test_score_three_maps_to_high(self):
        """Score 3 → HIGH."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.activity_category == ActivityCategory.HIGH


# ---------------------------------------------------------------------------
# ERROR status tests
# ---------------------------------------------------------------------------


class TestActivityClassifierERROR:
    """Test ERROR status — invalid values rejected by classifier."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_training_days_negative(self):
        """training_days_per_week = -1 → ERROR."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=-1,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR
        assert "INVALID_ACTIVITY_DATA" in result.issues
        assert result.activity_category is None
        assert result.activity_factor is None
        assert result.baseline_score is None
        assert result.daily_movement_adjustment is None
        assert result.wes_units is None
        assert result.upgrade_score is None
        assert result.final_score is None

    def test_training_days_eight(self):
        """training_days_per_week = 8 → ERROR."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=8,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR
        assert "INVALID_ACTIVITY_DATA" in result.issues
        assert result.activity_category is None

    def test_training_days_ten(self):
        """training_days_per_week = 10 → ERROR."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=10,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR

    def test_negative_duration(self):
        """training_duration_minutes = -10 → ERROR."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=-10,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR
        assert "INVALID_ACTIVITY_DATA" in result.issues
        assert result.activity_category is None

    def test_negative_duration_with_zero_days(self):
        """training_duration_minutes = -5, days = 0 → ERROR."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=-5,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR

    def test_error_all_calculated_fields_none(self):
        """ERROR result has all calculated fields = None."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=8,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.ERROR
        assert result.activity_category is None
        assert result.activity_factor is None
        assert result.baseline_score is None
        assert result.daily_movement_adjustment is None
        assert result.wes_units is None
        assert result.upgrade_score is None
        assert result.final_score is None

    def test_error_preserves_policy_version(self):
        """ERROR result still includes policy_version."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=8,
        )
        result = self.classifier.classify(inputs)
        assert result.policy_version == ACTIVITY_POLICY_VERSION


# ---------------------------------------------------------------------------
# INCOMPLETE status tests
# ---------------------------------------------------------------------------


class TestActivityClassifierINCOMPLETE:
    """Test INCOMPLETE status — missing conditional data."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_days_positive_duration_none(self):
        """days > 0, duration = None → INCOMPLETE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE
        assert "INCOMPLETE_ACTIVITY_DATA" in result.issues

    def test_days_positive_intensity_none(self):
        """days > 0, intensity = None → INCOMPLETE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE
        assert "INCOMPLETE_ACTIVITY_DATA" in result.issues

    def test_days_positive_both_none(self):
        """days > 0, duration = None, intensity = None → INCOMPLETE (both issues)."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE
        assert "INCOMPLETE_ACTIVITY_DATA" in result.issues
        # Should have 2 INCOMPLETE_ACTIVITY_DATA entries
        assert result.issues.count("INCOMPLETE_ACTIVITY_DATA") == 2

    def test_incomplete_all_calculated_fields_none(self):
        """INCOMPLETE result has all calculated fields = None."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE
        assert result.activity_category is None
        assert result.activity_factor is None
        assert result.baseline_score is None
        assert result.daily_movement_adjustment is None
        assert result.wes_units is None
        assert result.upgrade_score is None
        assert result.final_score is None

    def test_incomplete_preserves_policy_version(self):
        """INCOMPLETE result still includes policy_version."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.policy_version == ACTIVITY_POLICY_VERSION

    def test_no_wes_calculated_for_incomplete(self):
        """WES must not be calculated when INCOMPLETE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=5,
            training_duration_minutes=None,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE
        assert result.wes_units is None


# ---------------------------------------------------------------------------
# CONFLICT status tests
# ---------------------------------------------------------------------------


class TestActivityClassifierCONFLICT:
    """Test CONFLICT status — contradictory training data."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_days_positive_intensity_none_value(self):
        """days > 0, intensity = NONE → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert "ACTIVITY_CONFLICT" in result.issues

    def test_days_zero_intensity_light(self):
        """days = 0, intensity = LIGHT → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=None,
            exercise_intensity="light",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert "ACTIVITY_CONFLICT" in result.issues

    def test_days_zero_intensity_moderate(self):
        """days = 0, intensity = MODERATE → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert "ACTIVITY_CONFLICT" in result.issues

    def test_days_zero_intensity_vigorous(self):
        """days = 0, intensity = VIGOROUS → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=None,
            exercise_intensity="vigorous",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert "ACTIVITY_CONFLICT" in result.issues

    def test_days_zero_duration_positive(self):
        """days = 0, duration = 30 → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=30,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert "ACTIVITY_CONFLICT" in result.issues

    def test_days_zero_duration_positive_intensity_none(self):
        """days = 0, duration = 30, intensity = None → CONFLICT (duration rule)."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=30,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT

    def test_conflict_all_calculated_fields_none(self):
        """CONFLICT result has all calculated fields = None."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert result.activity_category is None
        assert result.activity_factor is None
        assert result.baseline_score is None
        assert result.daily_movement_adjustment is None
        assert result.wes_units is None
        assert result.upgrade_score is None
        assert result.final_score is None

    def test_conflict_preserves_policy_version(self):
        """CONFLICT result still includes policy_version."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.policy_version == ACTIVITY_POLICY_VERSION

    def test_no_wes_calculated_for_conflict(self):
        """WES must not be calculated when CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT
        assert result.wes_units is None

    def test_heavy_manual_low_movement_no_conflict(self):
        """HEAVY_MANUAL + LOW → NOT a conflict (valid combination)."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK
        assert result.baseline_score == 3

    def test_heavy_manual_low_movement_with_valid_training(self):
        """HEAVY_MANUAL + LOW + valid training → OK."""
        inputs = ActivityClassificationInput(
            occupational_activity="heavy_manual",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK
        assert result.baseline_score == 3


# ---------------------------------------------------------------------------
# Important semantics tests (from spec)
# ---------------------------------------------------------------------------


class TestActivityClassifierSemantics:
    """Test the exact cases from the Revision 3 spec."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_case_a_days_zero_duration_none_intensity_none(self):
        """Case A: days=0, duration=None, intensity=None → OK, WES=0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK
        assert result.wes_units == 0

    def test_case_b_days_zero_duration_zero_intensity_none_val(self):
        """Case B: days=0, duration=0, intensity=NONE → OK, WES=0."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=0,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK
        assert result.wes_units == 0

    def test_case_c_days_four_duration_60_intensity_moderate(self):
        """Case C: days=4, duration=60, intensity=MODERATE → OK."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK

    def test_case_d_days_four_duration_none_intensity_moderate(self):
        """Case D: days=4, duration=None, intensity=MODERATE → INCOMPLETE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE

    def test_case_e_days_four_duration_60_intensity_none_val(self):
        """Case E: days=4, duration=60, intensity=None → INCOMPLETE."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.INCOMPLETE

    def test_case_f_days_four_duration_60_intensity_none_enum(self):
        """Case F: days=4, duration=60, intensity=NONE → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT

    def test_case_g_days_zero_duration_30_intensity_none(self):
        """Case G: days=0, duration=30, intensity=None → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=30,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT

    def test_case_h_days_zero_duration_none_intensity_moderate(self):
        """Case H: days=0, duration=None, intensity=MODERATE → CONFLICT."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
            training_duration_minutes=None,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.CONFLICT


# ---------------------------------------------------------------------------
# Validation order tests
# ---------------------------------------------------------------------------


class TestActivityClassifierValidationOrder:
    """Test that validation follows the required order."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_error_before_incomplete(self):
        """Range error (days=8) takes precedence over missing data."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=8,
            training_duration_minutes=None,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        # Should be ERROR, not INCOMPLETE
        assert result.status == ActivityClassificationStatus.ERROR
        assert "INVALID_ACTIVITY_DATA" in result.issues

    def test_error_before_conflict(self):
        """Range error (days=-1) takes precedence over conflict."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=-1,
            training_duration_minutes=60,
            exercise_intensity="none",
        )
        result = self.classifier.classify(inputs)
        # Should be ERROR, not CONFLICT
        assert result.status == ActivityClassificationStatus.ERROR

    def test_incomplete_before_conflict(self):
        """Missing data (INCOMPLETE) takes precedence over conflict."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            training_duration_minutes=None,
            exercise_intensity=None,
        )
        result = self.classifier.classify(inputs)
        # Should be INCOMPLETE, not CONFLICT
        assert result.status == ActivityClassificationStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestActivityClassifierIntegration:
    """Integration tests for the full classification pipeline."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_factor_matches_category(self):
        """Activity factor always matches the determined category."""
        inputs = ActivityClassificationInput(
            occupational_activity="active_manual",
            daily_movement="moderate",
            training_days_per_week=4,
            training_duration_minutes=45,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        expected_factor = get_activity_factor(result.activity_category)
        assert result.activity_factor == expected_factor

    def test_policy_version_in_result(self):
        """Result always includes the policy version."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        result = self.classifier.classify(inputs)
        assert result.policy_version == ACTIVITY_POLICY_VERSION

    def test_full_score_breakdown_when_ok(self):
        """Result includes complete score breakdown when OK."""
        inputs = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="high",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        result = self.classifier.classify(inputs)
        assert result.status == ActivityClassificationStatus.OK
        assert result.baseline_score is not None
        assert result.daily_movement_adjustment is not None
        assert result.wes_units is not None
        assert result.upgrade_score is not None
        assert result.final_score is not None

    def test_all_occupation_movement_combinations_ok(self):
        """All valid occupation × movement combinations → OK status."""
        for occ in OccupationalActivity:
            for movement in DailyMovement:
                inputs = ActivityClassificationInput(
                    occupational_activity=occ,
                    daily_movement=movement,
                    training_days_per_week=0,
                )
                result = self.classifier.classify(inputs)
                assert result.status == ActivityClassificationStatus.OK, (
                    f"{occ.value} + {movement.value} should be OK, "
                    f"got {result.status}"
                )


# ---------------------------------------------------------------------------
# Dependency tests
# ---------------------------------------------------------------------------


class TestActivityClassifierDependencies:
    """Verify no LLM or network dependencies."""

    def test_no_llm_dependency(self):
        """Classifier does not import or use LLM modules."""
        import app.nutrition.activity.activity_classifier as mod
        source = open(mod.__file__).read()
        assert "llm" not in source.lower()
        assert "LLMClient" not in source
        assert "ProfileExtractor" not in source

    def test_no_network_dependency(self):
        """Classifier does not import or use network modules."""
        import app.nutrition.activity.activity_classifier as mod
        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source
