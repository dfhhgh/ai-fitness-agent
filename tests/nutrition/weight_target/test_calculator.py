"""Tests for Weight Target Determination contracts and domain logic.

Layer A: Contract validation tests (strict Pydantic, no coercion)
Layer B: Calculator domain tests (loss, older adult, gain, maintenance,
         user target, review precedence)
Rounding tests (Decimal ROUND_HALF_UP, no intermediate rounding)
Boundary tests (B1–B5)
Invariant/property tests
Safety/regression tests (purity, isolation)
"""

import math

import pytest
from pydantic import ValidationError

from app.nutrition.models import GoalType
from app.nutrition.weight_target import (
    WEIGHT_GAIN_MILESTONE_FACTOR,
    WEIGHT_LOSS_MILESTONE_FACTOR,
    WEIGHT_TARGET_POLICY_VERSION,
    ReviewFlag,
    ValidationFlag,
    WeightTargetInput,
    WeightTargetResult,
    WeightTargetStatus,
    determine_weight_targets,
)
from app.nutrition.weight_target.calculator import _round_weight


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    age_years: int = 30,
    height_cm: float = 180.0,
    current_weight_kg: float = 80.0,
    goal: GoalType = GoalType.WEIGHT_LOSS,
    user_requested_target_weight_kg: float | None = None,
) -> WeightTargetInput:
    """Create a valid WeightTargetInput."""
    return WeightTargetInput(
        age_years=age_years,
        height_cm=height_cm,
        current_weight_kg=current_weight_kg,
        goal=goal,
        user_requested_target_weight_kg=user_requested_target_weight_kg,
    )


def _height_squared(height_cm: float) -> float:
    h_m = height_cm / 100.0
    return h_m * h_m


# ---------------------------------------------------------------------------
# Layer A: Contract Validation
# ---------------------------------------------------------------------------


class TestWeightTargetInputContract:
    """Layer A: strict schema boundary validation."""

    def test_missing_age(self):
        """Missing age_years → ValidationError."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_missing_height(self):
        """Missing height_cm → ValidationError."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_missing_current_weight(self):
        """Missing current_weight_kg → ValidationError."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_missing_goal(self):
        """Missing goal → ValidationError."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
            )

    def test_string_age_rejected(self):
        """String age rejected under strict=True (no silent coercion)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years="25",
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_string_height_rejected(self):
        """String height rejected under strict=True."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm="180.0",
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_string_weight_rejected(self):
        """String weight rejected under strict=True."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg="80.0",
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_string_target_rejected(self):
        """String user target rejected under strict=True."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
                user_requested_target_weight_kg="75.0",
            )

    def test_zero_age_rejected(self):
        """Zero age rejected (gt=0)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=0,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_zero_height_rejected(self):
        """Zero height rejected (gt=0)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=0.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_zero_weight_rejected(self):
        """Zero weight rejected (gt=0)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=0.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_zero_target_rejected(self):
        """Zero user target rejected (gt=0)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
                user_requested_target_weight_kg=0.0,
            )

    def test_negative_values_rejected(self):
        """Negative age, height, weight, target rejected."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=-30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=-180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=-80.0,
                goal=GoalType.WEIGHT_LOSS,
            )
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
                user_requested_target_weight_kg=-75.0,
            )

    def test_extra_fields_rejected(self):
        """Extra fields rejected (extra='forbid')."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
                whtr=0.5,
            )

    def test_float_age_rejected_strict(self):
        """Float age rejected under strict=True (no int coercion)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30.0,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )

    def test_invalid_goal_rejected(self):
        """Invalid goal enum value rejected."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal="fat_loss",
            )

    def test_frozen_input(self):
        """Input model is frozen (immutable)."""
        inp = _make_input()
        with pytest.raises(ValidationError):
            inp.age_years = 31

    def test_strict_config(self):
        """model_config has strict=True, frozen=True, extra='forbid'."""
        config = WeightTargetInput.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_structural_failure_is_not_result(self):
        """Structural failures raise ValidationError, never WeightTargetResult."""
        with pytest.raises(ValidationError) as exc_info:
            WeightTargetInput(
                age_years=0,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.WEIGHT_LOSS,
            )
        assert not isinstance(exc_info.value, WeightTargetResult)

    def test_muscle_gain_rejected_at_contract_boundary(self):
        """GoalType.MUSCLE_GAIN cannot enter WeightTargetInput (no V1 semantic)."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.MUSCLE_GAIN,
            )

    def test_muscle_gain_string_value_rejected(self):
        """Raw 'muscle_gain' string rejected at contract boundary."""
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal="muscle_gain",
            )

    def test_supported_goals_accepted(self):
        """Only WEIGHT_LOSS, WEIGHT_GAIN, MAINTENANCE are accepted goals."""
        for goal in (
            GoalType.WEIGHT_LOSS,
            GoalType.WEIGHT_GAIN,
            GoalType.MAINTENANCE,
        ):
            inp = WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=goal,
            )
            assert inp.goal == goal

    def test_muscle_gain_cannot_reach_calculator_as_maintenance(self):
        """Regression: MUSCLE_GAIN must not silently become maintenance.

        Layer A rejects the goal. Even a bypass via model_construct
        (skipping validation) must raise in the calculator — never
        return a maintenance-style OK result with milestone == weight.
        """
        with pytest.raises(ValidationError):
            WeightTargetInput(
                age_years=30,
                height_cm=180.0,
                current_weight_kg=80.0,
                goal=GoalType.MUSCLE_GAIN,
            )

        bypass = WeightTargetInput.model_construct(
            age_years=30,
            height_cm=180.0,
            current_weight_kg=80.0,
            goal=GoalType.MUSCLE_GAIN,
            user_requested_target_weight_kg=None,
        )
        assert bypass.goal == GoalType.MUSCLE_GAIN

        with pytest.raises(ValueError, match="Unsupported goal"):
            determine_weight_targets(bypass)


# ---------------------------------------------------------------------------
# Layer B: Weight Loss
# ---------------------------------------------------------------------------


class TestWeightLoss:
    """Weight-loss milestone and gates."""

    def test_normal_weight_loss(self):
        """Normal loss: current above ref_min, 5% stays above → OK."""
        # height 180 → ref_min = 18.5 * 3.24 = 59.94
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.review_flags == []
        assert result.validation_flags == []
        # milestone = max(80 * 0.95, 59.94) = max(76.0, 59.94) = 76.0
        assert result.initial_milestone_weight_kg == 76.0
        assert result.initial_milestone_weight_kg is not None

    def test_exactly_at_reference_minimum(self):
        """Current weight exactly at reference_min → no below-min flag."""
        # ref_min = 59.94 for height 180
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.94,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN not in result.review_flags
        # milestone = max(59.94*0.95, 59.94) = 59.94 → 59.9
        assert result.initial_milestone_weight_kg == 59.9

    def test_below_reference_minimum_review(self):
        """Current weight below reference_min → REVIEW_REQUIRED."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.90,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags

    def test_5pct_crosses_reference_min_clamped(self):
        """5% loss would cross reference_min → milestone = reference_min."""
        # current = 62.0; 62 * 0.95 = 58.9 < 59.94 → max → 59.94 → 59.9
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=62.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 59.9
        # unrounded reference_min is 59.94; output rounds to 59.9
        assert result.reference_weight_range_min_kg == 59.9

    def test_5pct_remains_above_reference_min(self):
        """5% loss remains above reference_min → exact 5% milestone."""
        # current = 70.0; 70 * 0.95 = 66.5 > 59.94
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=70.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 66.5


# ---------------------------------------------------------------------------
# Layer B: Older Adult
# ---------------------------------------------------------------------------


class TestOlderAdult:
    """Age-band reference range and older-adult loss gate."""

    def test_age_64_bmi_24_9_ok(self):
        """Age 64 + BMI ~24.9 → OK (adult band; not older-adult gate)."""
        # height 180, h^2=3.24; weight = 24.9 * 3.24 = 80.676
        result = determine_weight_targets(
            _make_input(age_years=64, height_cm=180.0, current_weight_kg=80.676,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS not in result.review_flags

    def test_age_65_bmi_24_9_review(self):
        """Age 65 + BMI ~24.9 → REVIEW_REQUIRED, older-adult flag."""
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=80.676,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS in result.review_flags

    def test_age_65_bmi_exactly_25_ok(self):
        """Age 65 + BMI exactly 25.0 → OK (gate is BMI < 25.0)."""
        # weight = 25.0 * 3.24 = 81.0; BMI = 81.0 / 3.24 = 25.0
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=81.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS not in result.review_flags

    def test_age_65_bmi_above_25_ok(self):
        """Age 65 + BMI > 25 → OK (if weight still >= older ref_min)."""
        # weight = 90.0; BMI = 90/3.24 ≈ 27.78; older ref_min = 23*3.24 = 74.52
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=90.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.review_flags == []

    def test_age_65_weight_below_older_ref_min_both_flags(self):
        """Age 65 + weight below older ref_min + BMI < 25 → both flags."""
        # older ref_min = 23.0 * 3.24 = 74.52
        # weight = 70.0 < 74.52; BMI = 70/3.24 ≈ 21.6 < 25
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=70.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS in result.review_flags
        assert len(result.review_flags) == 2

    def test_older_adult_reference_band(self):
        """Age >= 65 uses BMI 23.0–29.9 reference band."""
        result = determine_weight_targets(
            _make_input(age_years=70, height_cm=180.0, current_weight_kg=90.0,
                        goal=GoalType.MAINTENANCE)
        )
        # ref_min = 23.0 * 3.24 = 74.52 → 74.5
        # ref_max = 29.9 * 3.24 = 96.876 → 96.9
        assert result.reference_weight_range_min_kg == 74.5
        assert result.reference_weight_range_max_kg == 96.9


# ---------------------------------------------------------------------------
# Layer B: Weight Gain
# ---------------------------------------------------------------------------


class TestWeightGain:
    """Weight-gain milestone and BMI >= 30 gate."""

    def test_normal_gain(self):
        """Normal gain: BMI < 30 → OK, milestone = current * 1.05."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=70.0,
                        goal=GoalType.WEIGHT_GAIN)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.review_flags == []
        assert result.initial_milestone_weight_kg == 73.5  # 70 * 1.05

    def test_bmi_exactly_30_review(self):
        """BMI exactly 30.0 → REVIEW_REQUIRED (gate is BMI >= 30)."""
        # height 170, h^2=2.89; weight = 30.0 * 2.89 = 86.7
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=170.0, current_weight_kg=86.7,
                        goal=GoalType.WEIGHT_GAIN)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.HIGH_BMI_WEIGHT_GAIN_REQUEST in result.review_flags

    def test_bmi_just_below_30_ok(self):
        """BMI just below 30 → OK."""
        # weight = 86.6; BMI = 86.6 / 2.89 ≈ 29.965 < 30
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=170.0, current_weight_kg=86.6,
                        goal=GoalType.WEIGHT_GAIN)
        )
        assert result.status == WeightTargetStatus.OK
        assert ReviewFlag.HIGH_BMI_WEIGHT_GAIN_REQUEST not in result.review_flags

    def test_bmi_above_30_review(self):
        """BMI above 30 → REVIEW_REQUIRED."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=170.0, current_weight_kg=90.0,
                        goal=GoalType.WEIGHT_GAIN)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert ReviewFlag.HIGH_BMI_WEIGHT_GAIN_REQUEST in result.review_flags

    def test_gain_milestone_may_exceed_reference_max(self):
        """Gain milestone is NOT clamped to reference_max."""
        # height 180 adult ref_max = 24.9 * 3.24 = 80.676
        # current = 80.0 (BMI ≈ 24.69 < 30); milestone = 84.0 > 80.676
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.WEIGHT_GAIN)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 84.0
        # output ref_max rounds to 80.7; milestone exceeds it
        assert result.reference_weight_range_max_kg == 80.7
        assert result.initial_milestone_weight_kg > result.reference_weight_range_max_kg


# ---------------------------------------------------------------------------
# Layer B: Maintenance
# ---------------------------------------------------------------------------


class TestMaintenance:
    """Maintenance returns current weight as milestone."""

    def test_maintenance(self):
        """Maintenance → status OK, milestone == current weight."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.MAINTENANCE)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 80.0
        assert result.review_flags == []

    def test_maintenance_at_low_reference_weight(self):
        """Maintenance at low weight within reference range → OK."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=60.0,
                        goal=GoalType.MAINTENANCE)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 60.0

    def test_maintenance_at_high_reference_weight(self):
        """Maintenance at high weight within reference range → OK."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.MAINTENANCE)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 80.0

    def test_maintenance_no_loss_or_gain_gates(self):
        """Maintenance applies no weight-loss/gain safety gates."""
        # BMI >= 30 would trip gain gate, but goal is maintenance
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=170.0, current_weight_kg=95.0,
                        goal=GoalType.MAINTENANCE)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.review_flags == []


# ---------------------------------------------------------------------------
# Layer B: User Requested Target
# ---------------------------------------------------------------------------


class TestUserTarget:
    """User-requested target validation flags (informational only)."""

    def test_target_below_reference_range(self):
        """User target below ref_min → validation flag, status OK."""
        # ref_min adult height 180 = 59.94; target = 50.0
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=50.0)
        )
        assert result.status == WeightTargetStatus.OK
        assert ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE in result.validation_flags
        assert ValidationFlag.USER_TARGET_ABOVE_REFERENCE_RANGE not in result.validation_flags

    def test_target_exactly_at_reference_minimum(self):
        """User target == ref_min → no flag (boundary equality)."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=59.94)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.validation_flags == []

    def test_target_inside_range(self):
        """User target inside range → no flag."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=70.0)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.validation_flags == []

    def test_target_exactly_at_reference_maximum(self):
        """User target == ref_max → no flag (boundary equality)."""
        # ref_max adult height 180 = 24.9 * 3.24 = 80.676
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=80.676)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.validation_flags == []

    def test_target_above_reference_range(self):
        """User target above ref_max → validation flag, status OK."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=90.0)
        )
        assert result.status == WeightTargetStatus.OK
        assert ValidationFlag.USER_TARGET_ABOVE_REFERENCE_RANGE in result.validation_flags
        assert ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE not in result.validation_flags

    def test_user_target_does_not_alter_milestone(self):
        """Changing only user target must not change initial milestone."""
        base = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        with_target = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                        goal=GoalType.WEIGHT_LOSS,
                        user_requested_target_weight_kg=50.0)
        )
        assert base.initial_milestone_weight_kg == with_target.initial_milestone_weight_kg
        assert base.reference_weight_range_min_kg == with_target.reference_weight_range_min_kg
        assert base.reference_weight_range_max_kg == with_target.reference_weight_range_max_kg
        assert base.status == with_target.status
        # only validation flags may differ
        assert ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE in with_target.validation_flags
        assert with_target.validation_flags != base.validation_flags

    def test_none_target_is_not_truthiness_checked(self):
        """user_target is None → no flags (uses `is not None`, not truthiness)."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=None)
        )
        assert result.user_requested_target_weight_kg is None
        assert result.validation_flags == []

    def test_validation_flag_does_not_change_status(self):
        """Validation flag alone never forces REVIEW_REQUIRED."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE, user_requested_target_weight_kg=50.0)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.review_flags == []
        assert result.initial_milestone_weight_kg is not None

    def test_user_target_still_collected_on_review(self):
        """Validation flags still collected when review flags exist."""
        # below ref_min → review; also user target below range
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.90,
                        goal=GoalType.WEIGHT_LOSS,
                        user_requested_target_weight_kg=50.0)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags
        assert ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE in result.validation_flags


# ---------------------------------------------------------------------------
# Layer B: Review Flag Precedence
# ---------------------------------------------------------------------------


class TestReviewFlagPrecedence:
    """All applicable review flags are evaluated (no short-circuit)."""

    def test_multiple_review_flags_returned_together(self):
        """Age>=65 + BMI<25 + weight below ref_min + LOSS → both flags."""
        result = determine_weight_targets(
            _make_input(age_years=70, height_cm=170.0, current_weight_kg=70.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        # h^2 = 2.89; older ref_min = 23 * 2.89 = 66.47; 70 >= 66.47?
        # 70 > 66.47 so weight is NOT below older ref_min.
        # Need weight below 66.47 for both flags.
        result = determine_weight_targets(
            _make_input(age_years=70, height_cm=170.0, current_weight_kg=65.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        # BMI = 65/2.89 ≈ 22.49 < 25; weight 65 < 66.47
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS in result.review_flags
        assert len(result.review_flags) == 2

    def test_review_required_milestone_none(self):
        """Any review flag → milestone is None."""
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=80.676,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------


class TestRounding:
    """Decimal ROUND_HALF_UP output rounding; no intermediate rounding."""

    def test_round_half_up_not_half_even(self):
        """_round_weight uses half-up, not banker's rounding."""
        # 2.25 → half-up 2.3; Python round(2.25, 1) is 2.2 (half-even)
        assert _round_weight(2.25) == 2.3
        assert round(2.25, 1) == 2.2  # documents the distinction

    def test_round_half_up_x_x5_matters(self):
        """Explicit x.x5 half-up behavior via Decimal(str(...))."""
        assert _round_weight(1.25) == 1.3
        assert _round_weight(0.05) == 0.1
        assert _round_weight(10.15) == 10.2

    def test_round_preserves_one_decimal_display(self):
        """Output weights are rounded to 1 decimal place."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.94,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.initial_milestone_weight_kg == 59.9
        assert result.reference_weight_range_min_kg == 59.9

    def test_intermediate_not_rounded_before_comparison(self):
        """Comparison uses unrounded reference_min (59.94), not 59.9."""
        # weight 59.92: unrounded ref_min = 59.94 → 59.92 < 59.94 → review
        # If ref_min were wrongly rounded to 59.9 first: 59.92 < 59.9 is False → OK
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.92,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags

    def test_intermediate_not_rounded_milestone_floor(self):
        """Milestone floor uses unrounded reference_min before output round."""
        # current 62.0: 62*0.95=58.9 < 59.94 → floor to 59.94 → output 59.9
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=62.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.initial_milestone_weight_kg == 59.9

    def test_bmi_not_rounded_before_comparison(self):
        """BMI comparison uses full precision, not a rounded BMI."""
        # Construct age 65, height 180, weight such that BMI is just under 25
        # but a rounded-to-integer BMI might differ.
        # weight = 80.9; BMI = 80.9/3.24 ≈ 24.969 < 25
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=80.9,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS in result.review_flags


# ---------------------------------------------------------------------------
# Boundary Tests B1–B5
# ---------------------------------------------------------------------------


class TestBoundaryCases:
    """Policy boundary cases B1–B5."""

    def test_b1_below_crosses_5pct_ok(self):
        """B1: age=30, weight=59.94, height=180, LOSS → OK, milestone 59.9."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.94,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg == 59.9

    def test_b2_below_reference_min_review(self):
        """B2: age=30, weight=59.90, height=180, LOSS → REVIEW, milestone None."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0, current_weight_kg=59.90,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN in result.review_flags

    def test_b3_age_65_bmi_24_9_review(self):
        """B3: age=65, BMI≈24.9, LOSS → REVIEW, older-adult flag."""
        # weight = 24.9 * 3.24 = 80.676
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=80.676,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS in result.review_flags

    def test_b4_age_64_bmi_24_9_ok(self):
        """B4: age=64, BMI≈24.9, LOSS → OK."""
        result = determine_weight_targets(
            _make_input(age_years=64, height_cm=180.0, current_weight_kg=80.676,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg is not None

    def test_b5_age_65_bmi_exactly_25_ok(self):
        """B5: age=65, BMI exactly 25.0, LOSS → OK."""
        # weight = 25.0 * 3.24 = 81.0
        result = determine_weight_targets(
            _make_input(age_years=65, height_cm=180.0, current_weight_kg=81.0,
                        goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.OK
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS not in result.review_flags
        assert result.initial_milestone_weight_kg is not None


# ---------------------------------------------------------------------------
# Invariants / Property Tests
# ---------------------------------------------------------------------------


class TestInvariants:
    """Mathematical and contract invariants (hand-written; no Hypothesis)."""

    def test_loss_milestone_bounds(self):
        """Successful loss: milestone <= current and milestone >= ref_min."""
        for weight in (65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 100.0):
            result = determine_weight_targets(
                _make_input(age_years=30, height_cm=180.0,
                            current_weight_kg=weight, goal=GoalType.WEIGHT_LOSS)
            )
            if result.status == WeightTargetStatus.OK:
                assert result.initial_milestone_weight_kg is not None
                assert result.initial_milestone_weight_kg <= weight
                # compare against rounded ref_min for output-level invariant
                assert (
                    result.initial_milestone_weight_kg
                    >= result.reference_weight_range_min_kg - 0.05
                )

    def test_gain_milestone_bounds(self):
        """Successful gain: milestone >= current."""
        for weight in (55.0, 60.0, 65.0, 70.0, 75.0, 80.0):
            result = determine_weight_targets(
                _make_input(age_years=30, height_cm=180.0,
                            current_weight_kg=weight, goal=GoalType.WEIGHT_GAIN)
            )
            if result.status == WeightTargetStatus.OK:
                assert result.initial_milestone_weight_kg is not None
                assert result.initial_milestone_weight_kg >= weight

    def test_maintenance_milestone_equals_current(self):
        """Maintenance: milestone == current weight."""
        for weight in (55.0, 70.0, 85.0, 100.0):
            result = determine_weight_targets(
                _make_input(age_years=30, height_cm=180.0,
                            current_weight_kg=weight, goal=GoalType.MAINTENANCE)
            )
            assert result.initial_milestone_weight_kg == weight

    def test_reference_min_le_max_always(self):
        """reference_min <= reference_max for varied inputs."""
        for age in (20, 30, 50, 64, 65, 70, 80):
            for height in (150.0, 165.0, 180.0, 200.0):
                for weight in (40.0, 60.0, 80.0, 100.0, 120.0):
                    result = determine_weight_targets(
                        _make_input(age_years=age, height_cm=height,
                                    current_weight_kg=weight,
                                    goal=GoalType.MAINTENANCE)
                    )
                    assert (
                        result.reference_weight_range_min_kg
                        <= result.reference_weight_range_max_kg
                    )

    def test_review_required_milestone_none_always(self):
        """REVIEW_REQUIRED always has milestone None."""
        cases = [
            dict(age_years=30, height_cm=180.0, current_weight_kg=59.9,
                 goal=GoalType.WEIGHT_LOSS),
            dict(age_years=65, height_cm=180.0, current_weight_kg=80.676,
                 goal=GoalType.WEIGHT_LOSS),
            dict(age_years=30, height_cm=170.0, current_weight_kg=86.7,
                 goal=GoalType.WEIGHT_GAIN),
        ]
        for kwargs in cases:
            result = determine_weight_targets(_make_input(**kwargs))
            assert result.status == WeightTargetStatus.REVIEW_REQUIRED
            assert result.initial_milestone_weight_kg is None

    def test_ok_milestone_not_none_always(self):
        """OK always has a non-None milestone."""
        cases = [
            dict(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                 goal=GoalType.WEIGHT_LOSS),
            dict(age_years=30, height_cm=180.0, current_weight_kg=70.0,
                 goal=GoalType.WEIGHT_GAIN),
            dict(age_years=30, height_cm=180.0, current_weight_kg=80.0,
                 goal=GoalType.MAINTENANCE),
            dict(age_years=64, height_cm=180.0, current_weight_kg=80.676,
                 goal=GoalType.WEIGHT_LOSS),
        ]
        for kwargs in cases:
            result = determine_weight_targets(_make_input(**kwargs))
            assert result.status == WeightTargetStatus.OK
            assert result.initial_milestone_weight_kg is not None

    def test_user_target_change_does_not_change_milestone(self):
        """Changing only user target never changes milestone."""
        targets = [None, 50.0, 59.94, 70.0, 80.676, 90.0]
        milestones = []
        for t in targets:
            result = determine_weight_targets(
                _make_input(age_years=30, height_cm=180.0,
                            current_weight_kg=80.0, goal=GoalType.WEIGHT_LOSS,
                            user_requested_target_weight_kg=t)
            )
            milestones.append(result.initial_milestone_weight_kg)
        assert all(m == milestones[0] for m in milestones)

    def test_loss_milestone_factors_constant(self):
        """Milestone factors match policy constants."""
        assert WEIGHT_LOSS_MILESTONE_FACTOR == 0.95
        assert WEIGHT_GAIN_MILESTONE_FACTOR == 1.05

    def test_policy_version_constant(self):
        """Policy version is weight-target-v1-rev1."""
        assert WEIGHT_TARGET_POLICY_VERSION == "weight-target-v1-rev1"
        result = determine_weight_targets(_make_input())
        assert result.policy_version == "weight-target-v1-rev1"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Pure function determinism."""

    def test_same_input_twice_identical(self):
        """Same input twice → identical output."""
        inp = _make_input(age_years=30, height_cm=180.0,
                          current_weight_kg=80.0, goal=GoalType.WEIGHT_LOSS)
        a = determine_weight_targets(inp)
        b = determine_weight_targets(inp)
        assert a.model_dump() == b.model_dump()

    def test_determinism_100_invocations(self):
        """100 invocations of the same input are identical."""
        inp = _make_input(age_years=45, height_cm=172.0,
                          current_weight_kg=77.0, goal=GoalType.WEIGHT_LOSS)
        results = [determine_weight_targets(inp) for _ in range(100)]
        first = results[0].model_dump()
        assert all(r.model_dump() == first for r in results)

    def test_input_not_mutated(self):
        """Calculator does not mutate the frozen input."""
        inp = _make_input(age_years=30, height_cm=180.0,
                          current_weight_kg=80.0, goal=GoalType.WEIGHT_LOSS)
        before = inp.model_dump()
        determine_weight_targets(inp)
        assert inp.model_dump() == before


# ---------------------------------------------------------------------------
# Source-Level Isolation Tests
# ---------------------------------------------------------------------------


class TestSourceIsolation:
    """Calculator module must not pull external dependencies."""

    def test_no_llm_dependency(self):
        """Calculator does not import or use LLM modules."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        """Calculator does not import or use network modules."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source
        assert "requests" not in source

    def test_no_database_dependency(self):
        """Calculator does not import database modules."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "sqlite" not in source
        assert "sqlalchemy" not in source
        assert "postgres" not in source

    def test_no_datetime_or_random(self):
        """Calculator does not use system clock or random state."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "datetime.now" not in source
        assert "time.time" not in source
        assert "import random" not in source
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_no_upstream_recalculation(self):
        """Calculator does not call RMR/TDEE/calorie/activity calculators."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "ActivityClassifier" not in source
        assert "RMRCalculator" not in source
        assert "calculate_tdee" not in source
        assert "calculate_calorie_target" not in source
        assert "Mifflin" not in source

    def test_no_diagnosis_logic(self):
        """No diagnostic enums/fields or condition-coding helpers."""
        import app.nutrition.weight_target.calculator as calc_mod
        import app.nutrition.weight_target.models as models_mod

        # No diagnosis-related public names
        for mod in (calc_mod, models_mod):
            for name in dir(mod):
                assert "diagnos" not in name.lower()
                assert "disorder" not in name.lower()
                assert "anorexia" not in name.lower()
                assert "bulimia" not in name.lower()

        # No diagnosis-related model fields
        for field_name in WeightTargetInput.model_fields:
            assert "diagnos" not in field_name.lower()
            assert "disorder" not in field_name.lower()
        for field_name in WeightTargetResult.model_fields:
            assert "diagnos" not in field_name.lower()
            assert "disorder" not in field_name.lower()

    def test_no_whtr_or_bia(self):
        """No WHtR / waist / body-fat / InBody fields in V1."""
        import app.nutrition.weight_target.calculator as calc_mod
        import app.nutrition.weight_target.models as models_mod

        forbidden_fragments = ("whtr", "waist", "body_fat", "inbody", "pregnan")
        for mod in (calc_mod, models_mod):
            for name in dir(mod):
                lowered = name.lower()
                for fragment in forbidden_fragments:
                    assert fragment not in lowered

        for field_name in list(WeightTargetInput.model_fields) + list(
            WeightTargetResult.model_fields
        ):
            lowered = field_name.lower()
            for fragment in forbidden_fragments:
                assert fragment not in lowered

    def test_no_ideal_or_recommended_target_field(self):
        """Result model has no ideal/recommended/final target fields."""
        fields = WeightTargetResult.model_fields
        for forbidden in (
            "system_recommended_target_weight_kg",
            "recommended_final_weight_kg",
            "ideal_weight_kg",
            "healthy_weight_min_kg",
        ):
            assert forbidden not in fields
        assert "reference_weight_range_min_kg" in fields
        assert "reference_weight_range_max_kg" in fields

    def test_no_builtin_round_in_calculator(self):
        """No Python builtin round() for weights (Decimal half-up only)."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        # _round_weight is allowed; bare round( is not
        assert "round(" not in source.replace("_round_weight(", "")

    def test_uses_decimal_round_half_up(self):
        """Output rounding uses Decimal + ROUND_HALF_UP."""
        import app.nutrition.weight_target.calculator as mod

        source = open(mod.__file__).read()
        assert "ROUND_HALF_UP" in source
        assert "Decimal" in source
        assert "quantize" in source


# ---------------------------------------------------------------------------
# Result Contract Tests
# ---------------------------------------------------------------------------


class TestResultContract:
    """WeightTargetResult field and nullability rules."""

    def test_result_extra_forbid(self):
        """Result model forbids extra fields."""
        assert WeightTargetResult.model_config.get("extra") == "forbid"

    def test_result_frozen_config(self):
        """Result model_config is strict=True, frozen=True, extra=forbid."""
        config = WeightTargetResult.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_result_immutable(self):
        """WeightTargetResult instances cannot be mutated after construction."""
        result = determine_weight_targets(_make_input())
        with pytest.raises(ValidationError):
            result.status = WeightTargetStatus.ERROR

    def test_policy_version_immutable(self):
        """policy_version cannot be mutated after construction."""
        result = determine_weight_targets(_make_input())
        assert result.policy_version == "weight-target-v1-rev1"
        with pytest.raises(ValidationError):
            result.policy_version = "tampered"

    def test_result_weights_immutable(self):
        """Milestone and reference range fields are immutable."""
        result = determine_weight_targets(_make_input())
        with pytest.raises(ValidationError):
            result.initial_milestone_weight_kg = 1.0
        with pytest.raises(ValidationError):
            result.reference_weight_range_min_kg = 1.0
        with pytest.raises(ValidationError):
            result.reference_weight_range_max_kg = 1.0

    def test_result_flags_immutable(self):
        """Flag list fields are immutable on the result."""
        result = determine_weight_targets(_make_input())
        with pytest.raises(ValidationError):
            result.validation_flags = []
        with pytest.raises(ValidationError):
            result.review_flags = []

    def test_required_fields_always_populated(self):
        """Status, weights, reference range, flags, policy always set."""
        result = determine_weight_targets(_make_input())
        assert result.status is not None
        assert result.current_weight_kg is not None
        assert result.reference_weight_range_min_kg is not None
        assert result.reference_weight_range_max_kg is not None
        assert result.validation_flags is not None
        assert result.review_flags is not None
        assert result.policy_version == "weight-target-v1-rev1"

    def test_ok_implies_milestone_not_none(self):
        """status OK → milestone MUST NOT be None."""
        result = determine_weight_targets(
            _make_input(goal=GoalType.MAINTENANCE)
        )
        assert result.status == WeightTargetStatus.OK
        assert result.initial_milestone_weight_kg is not None

    def test_review_implies_milestone_none(self):
        """status REVIEW_REQUIRED → milestone MUST be None."""
        result = determine_weight_targets(
            _make_input(age_years=30, height_cm=180.0,
                        current_weight_kg=59.9, goal=GoalType.WEIGHT_LOSS)
        )
        assert result.status == WeightTargetStatus.REVIEW_REQUIRED
        assert result.initial_milestone_weight_kg is None

    def test_status_enum_values(self):
        """WeightTargetStatus has OK, REVIEW_REQUIRED, ERROR."""
        assert WeightTargetStatus.OK.value == "OK"
        assert WeightTargetStatus.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"
        assert WeightTargetStatus.ERROR.value == "ERROR"

    def test_flag_enum_values(self):
        """ValidationFlag and ReviewFlag have exact policy values."""
        assert ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE.value == (
            "USER_TARGET_BELOW_REFERENCE_RANGE"
        )
        assert ValidationFlag.USER_TARGET_ABOVE_REFERENCE_RANGE.value == (
            "USER_TARGET_ABOVE_REFERENCE_RANGE"
        )
        assert ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN.value == (
            "CURRENT_WEIGHT_BELOW_REFERENCE_MIN"
        )
        assert ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS.value == (
            "OLDER_ADULT_LOW_BMI_WEIGHT_LOSS"
        )
        assert ReviewFlag.HIGH_BMI_WEIGHT_GAIN_REQUEST.value == (
            "HIGH_BMI_WEIGHT_GAIN_REQUEST"
        )


# ---------------------------------------------------------------------------
# Integration: NutritionAssessment / NutritionPlanningContext
# ---------------------------------------------------------------------------


class TestNutritionCoreIntegration:
    """Optional weight_target field on assessment and planning context."""

    def test_assessment_accepts_weight_target(self):
        """NutritionAssessment accepts optional weight_target."""
        from app.nutrition.models import (
            AssessmentStatus,
            InputStatus,
            NutritionAssessment,
        )

        wt = determine_weight_targets(_make_input())
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
            weight_target=wt,
        )
        assert assessment.weight_target is not None
        assert assessment.weight_target.policy_version == "weight-target-v1-rev1"
        assert assessment.weight_target.status == WeightTargetStatus.OK

    def test_assessment_weight_target_defaults_none(self):
        """Existing assessments without weight_target still construct."""
        from app.nutrition.models import (
            AssessmentStatus,
            InputStatus,
            NutritionAssessment,
        )

        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
        )
        assert assessment.weight_target is None

    def test_planning_context_accepts_weight_target(self):
        """NutritionPlanningContext accepts optional weight_target."""
        from app.nutrition.models import (
            ActivityCategory,
            AssessmentStatus,
            GoalType as NutritionGoalType,
            NutritionPlanningContext,
            NutritionTargets,
        )

        wt = determine_weight_targets(_make_input())
        targets = NutritionTargets(
            calories_kcal=2200.0,
            protein_g=160.0,
            fat_g=61.0,
            carbohydrates_g=250.0,
            status=AssessmentStatus.OK,
        )
        ctx = NutritionPlanningContext(
            age=30,
            gender="male",
            height_cm=180.0,
            current_weight_kg=80.0,
            goal_type=NutritionGoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            work_activity=ActivityCategory.MODERATE,
            targets=targets,
            weight_target=wt,
        )
        assert ctx.weight_target is not None
        assert ctx.weight_target.initial_milestone_weight_kg == 76.0

    def test_planning_context_weight_target_defaults_none(self):
        """Existing planning contexts without weight_target still construct."""
        from app.nutrition.models import (
            ActivityCategory,
            AssessmentStatus,
            GoalType as NutritionGoalType,
            NutritionPlanningContext,
            NutritionTargets,
        )

        targets = NutritionTargets(
            calories_kcal=2200.0,
            protein_g=160.0,
            fat_g=61.0,
            carbohydrates_g=250.0,
            status=AssessmentStatus.OK,
        )
        ctx = NutritionPlanningContext(
            age=30,
            gender="male",
            height_cm=180.0,
            current_weight_kg=80.0,
            goal_type=NutritionGoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            work_activity=ActivityCategory.MODERATE,
            targets=targets,
        )
        assert ctx.weight_target is None
