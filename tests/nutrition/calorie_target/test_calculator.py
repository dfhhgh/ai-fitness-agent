"""Tests for Calorie Target Calculator contracts and domain logic.

Layer A: Contract validation tests (CT-001 to CT-008)
Layer B: Calculator domain tests (happy path, upstream, validation,
         low-calorie trigger)
Property/invariant tests
Safety/regression tests
Integration tests
"""

import math

import pytest
from pydantic import ValidationError

from app.nutrition.activity.activity_classifier import ActivityClassifier
from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.calorie_target.calculator import (
    CALORIE_TARGET_POLICY_VERSION,
    GOAL_ADJUSTMENTS,
    LOW_CALORIE_REVIEW_REQUIRED,
    LOW_CALORIE_THRESHOLD_KCAL,
    NEGATIVE_OR_ZERO_TARGET,
    calculate_calorie_target,
    get_goal_adjustment,
)
from app.nutrition.calorie_target.models import (
    CalorieTargetInput,
    CalorieTargetResult,
    CalorieTargetStatus,
    CalorieTargetTraceability,
)
from app.nutrition.models import ActivityCategory, ActivityClassificationStatus, GoalType
from app.nutrition.rmr.rmr_calculator import RMRCalculator
from app.nutrition.rmr.rmr_models import RMRInput, RMRResult, RMRStatus
from app.nutrition.tdee.tdee_calculator import calculate_tdee
from app.nutrition.tdee.tdee_models import TDEEInput, TDEEResult, TDEEStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_tdee(kcal: int = 2500) -> TDEEResult:
    """Create an OK TDEEResult."""
    return TDEEResult(
        status=TDEEStatus.OK,
        issues=[],
        tdee_kcal=kcal,
        policy_version="tdee-v1",
    )


def _non_ok_tdee(
    status: TDEEStatus = TDEEStatus.INCOMPLETE,
    issues: list[str] | None = None,
) -> TDEEResult:
    """Create a non-OK TDEEResult."""
    return TDEEResult(
        status=status,
        issues=issues or [],
    )


def _make_input(
    tdee_kcal: int = 2500,
    goal: GoalType = GoalType.MAINTENANCE,
    correlation_id: str | None = None,
    tdee_result: TDEEResult | None = None,
) -> CalorieTargetInput:
    """Create a valid CalorieTargetInput."""
    return CalorieTargetInput(
        tdee_result=tdee_result if tdee_result is not None else _ok_tdee(tdee_kcal),
        goal_type=goal,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Layer A: Contract Validation Tests (CT-001 to CT-008)
# ---------------------------------------------------------------------------


class TestCalorieTargetInputContract:
    """Layer A: Schema boundary validation tests."""

    def test_ct001_tdee_result_none(self):
        """CT-001: tdee_result=None → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result=None, goal_type=GoalType.MAINTENANCE)

    def test_ct001_missing_tdee_result(self):
        """CT-001: missing tdee_result → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(goal_type=GoalType.MAINTENANCE)

    def test_ct002_goal_type_none(self):
        """CT-002: goal_type=None → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result=_ok_tdee(), goal_type=None)

    def test_ct002_missing_goal_type(self):
        """CT-002: missing goal_type → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result=_ok_tdee())

    def test_ct003_invalid_goal_enum(self):
        """CT-003: invalid goal enum value → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result=_ok_tdee(), goal_type="fat_loss")

    def test_ct004_extra_target_weight_field(self):
        """CT-004: unsupported target_weight field → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(
                tdee_result=_ok_tdee(),
                goal_type=GoalType.MAINTENANCE,
                target_weight=75,
            )

    def test_ct005_arbitrary_extra_field(self):
        """CT-005: unsupported arbitrary extra field → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(
                tdee_result=_ok_tdee(),
                goal_type=GoalType.MAINTENANCE,
                extra_field="unauthorized",
            )

    def test_ct006_valid_correlation_id_accepted(self):
        """CT-006: valid optional correlation_id is accepted."""
        inp = CalorieTargetInput(
            tdee_result=_ok_tdee(),
            goal_type=GoalType.MAINTENANCE,
            correlation_id="track-123",
        )
        assert inp.correlation_id == "track-123"

    def test_ct007_tdee_result_wrong_type(self):
        """CT-007: tdee_result as string → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result="2500", goal_type=GoalType.MAINTENANCE)

    def test_ct008_invalid_correlation_id_type(self):
        """CT-008: correlation_id=12345 (int) → ValidationError."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(
                tdee_result=_ok_tdee(),
                goal_type=GoalType.MAINTENANCE,
                correlation_id=12345,
            )

    def test_layer_a_not_converted_to_result(self):
        """Structural failures raise ValidationError, never CalorieTargetResult."""
        with pytest.raises(ValidationError) as exc_info:
            CalorieTargetInput(tdee_result=None, goal_type=None)
        assert not isinstance(exc_info.value, CalorieTargetResult)


# ---------------------------------------------------------------------------
# Layer B: Happy Path
# ---------------------------------------------------------------------------


class TestCalorieTargetHappyPath:
    """Standard happy-path calculations (policy Test Matrix)."""

    def test_happy_maintenance(self):
        """TDEE OK (2500) + maintenance → target 2500, status OK."""
        result = calculate_calorie_target(_make_input(2500, GoalType.MAINTENANCE))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 2500
        assert result.tdee_kcal_used == 2500
        assert result.goal_type_used == GoalType.MAINTENANCE
        assert result.calorie_adjustment_kcal == 0
        assert result.issues == []
        assert result.safety_flags == []

    def test_happy_weight_loss(self):
        """TDEE OK (2500) + weight_loss → target 2000, status OK."""
        result = calculate_calorie_target(_make_input(2500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 2000
        assert result.tdee_kcal_used == 2500
        assert result.goal_type_used == GoalType.WEIGHT_LOSS
        assert result.calorie_adjustment_kcal == -500
        assert result.issues == []
        assert result.safety_flags == []

    def test_happy_weight_gain(self):
        """TDEE OK (2500) + weight_gain → target 3000, status OK."""
        result = calculate_calorie_target(_make_input(2500, GoalType.WEIGHT_GAIN))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 3000
        assert result.tdee_kcal_used == 2500
        assert result.goal_type_used == GoalType.WEIGHT_GAIN
        assert result.calorie_adjustment_kcal == 500
        assert result.issues == []
        assert result.safety_flags == []

    def test_happy_muscle_gain(self):
        """TDEE OK (2500) + muscle_gain → target 3000, status OK."""
        result = calculate_calorie_target(_make_input(2500, GoalType.MUSCLE_GAIN))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 3000
        assert result.tdee_kcal_used == 2500
        assert result.goal_type_used == GoalType.MUSCLE_GAIN
        assert result.calorie_adjustment_kcal == 500
        assert result.issues == []
        assert result.safety_flags == []

    def test_policy_version(self):
        """policy_version is always calorie-v1."""
        result = calculate_calorie_target(_make_input())
        assert result.policy_version == CALORIE_TARGET_POLICY_VERSION
        assert result.policy_version == "calorie-v1"


# ---------------------------------------------------------------------------
# Layer B: Upstream Status Propagation
# ---------------------------------------------------------------------------


class TestUpstreamPropagation:
    """TDEE INCOMPLETE / INVALID / ERROR propagate directly."""

    def test_tdee_incomplete(self):
        """TDEE INCOMPLETE → CalorieTargetResult INCOMPLETE, target None."""
        result = calculate_calorie_target(
            _make_input(goal=GoalType.WEIGHT_LOSS, tdee_result=_non_ok_tdee(TDEEStatus.INCOMPLETE))
        )
        assert result.status == CalorieTargetStatus.INCOMPLETE
        assert result.target_calories_kcal is None
        assert result.tdee_kcal_used is None
        assert "UPSTREAM_TDEE_NOT_OK" in result.issues

    def test_tdee_invalid(self):
        """TDEE INVALID → CalorieTargetResult INVALID, target None."""
        result = calculate_calorie_target(
            _make_input(goal=GoalType.WEIGHT_GAIN, tdee_result=_non_ok_tdee(TDEEStatus.INVALID))
        )
        assert result.status == CalorieTargetStatus.INVALID
        assert result.target_calories_kcal is None
        assert result.tdee_kcal_used is None
        assert "UPSTREAM_TDEE_NOT_OK" in result.issues

    def test_tdee_error(self):
        """TDEE ERROR → CalorieTargetResult ERROR, target None."""
        result = calculate_calorie_target(
            _make_input(goal=GoalType.MUSCLE_GAIN, tdee_result=_non_ok_tdee(TDEEStatus.ERROR))
        )
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert result.tdee_kcal_used is None
        assert "UPSTREAM_TDEE_NOT_OK" in result.issues

    def test_upstream_inherits_tdee_issues(self):
        """Upstream non-OK inherits TDEE issue codes."""
        result = calculate_calorie_target(
            _make_input(
                tdee_result=_non_ok_tdee(
                    TDEEStatus.ERROR,
                    issues=["MISSING_RMR_VALUE"],
                )
            )
        )
        assert "UPSTREAM_TDEE_NOT_OK" in result.issues
        assert "MISSING_RMR_VALUE" in result.issues

    def test_input_echo_populated_on_failure(self):
        """goal_type_used and calorie_adjustment_kcal echo input on failure."""
        result = calculate_calorie_target(
            _make_input(goal=GoalType.WEIGHT_LOSS, tdee_result=_non_ok_tdee(TDEEStatus.INCOMPLETE))
        )
        assert result.goal_type_used == GoalType.WEIGHT_LOSS
        assert result.calorie_adjustment_kcal == -500


# ---------------------------------------------------------------------------
# Layer B: TDEE Domain Validation
# ---------------------------------------------------------------------------


class TestTDEEDomainValidation:
    """OK status with missing / non-positive / non-finite TDEE → ERROR."""

    def test_tdee_none_with_ok_status(self):
        """TDEE OK but tdee_kcal=None → ERROR, MISSING_TDEE_VALUE."""
        bad = TDEEResult(status=TDEEStatus.OK, issues=[], tdee_kcal=None)
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "MISSING_TDEE_VALUE" in result.issues

    def test_tdee_zero(self):
        """TDEE = 0 → ERROR, TDEE_VALUE_NON_POSITIVE."""
        bad = TDEEResult(status=TDEEStatus.OK, issues=[], tdee_kcal=0)
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "TDEE_VALUE_NON_POSITIVE" in result.issues

    def test_tdee_negative(self):
        """TDEE < 0 → ERROR, TDEE_VALUE_NON_POSITIVE."""
        bad = TDEEResult.model_construct(
            status=TDEEStatus.OK,
            issues=[],
            tdee_kcal=-1500,
            policy_version="tdee-v1",
        )
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "TDEE_VALUE_NON_POSITIVE" in result.issues

    def test_tdee_nan(self):
        """TDEE = NaN → ERROR, NON_FINITE_INPUT."""
        bad = TDEEResult.model_construct(
            status=TDEEStatus.OK,
            issues=[],
            tdee_kcal=float("nan"),
            policy_version="tdee-v1",
        )
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "NON_FINITE_INPUT" in result.issues

    def test_tdee_positive_infinity(self):
        """TDEE = +Infinity → ERROR, NON_FINITE_INPUT."""
        bad = TDEEResult.model_construct(
            status=TDEEStatus.OK,
            issues=[],
            tdee_kcal=float("inf"),
            policy_version="tdee-v1",
        )
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "NON_FINITE_INPUT" in result.issues

    def test_tdee_negative_infinity(self):
        """TDEE = -Infinity → ERROR, NON_FINITE_INPUT."""
        bad = TDEEResult.model_construct(
            status=TDEEStatus.OK,
            issues=[],
            tdee_kcal=float("-inf"),
            policy_version="tdee-v1",
        )
        result = calculate_calorie_target(_make_input(tdee_result=bad))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert "NON_FINITE_INPUT" in result.issues


# ---------------------------------------------------------------------------
# Layer B: Low-Calorie Engineering Review Trigger
# ---------------------------------------------------------------------------


class TestLowCalorieTrigger:
    """Threshold 1200 (Engineering Trigger): no clamping, flag only."""

    def test_target_exactly_1200_no_flag(self):
        """TDEE=1700 + weight_loss → target 1200, no flag."""
        result = calculate_calorie_target(_make_input(1700, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1200
        assert result.safety_flags == []
        assert LOW_CALORIE_REVIEW_REQUIRED not in result.safety_flags

    def test_target_1199_flag(self):
        """TDEE=1699 + weight_loss → target 1199 + LOW_CALORIE_REVIEW_REQUIRED."""
        result = calculate_calorie_target(_make_input(1699, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1199
        assert LOW_CALORIE_REVIEW_REQUIRED in result.safety_flags

    def test_target_1000_flag(self):
        """TDEE=1500 + weight_loss → target 1000 + LOW_CALORIE_REVIEW_REQUIRED."""
        result = calculate_calorie_target(_make_input(1500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1000
        assert LOW_CALORIE_REVIEW_REQUIRED in result.safety_flags

    def test_no_clamping_occurs(self):
        """Exact calculated target is preserved; never raised to 1200."""
        result = calculate_calorie_target(_make_input(1400, GoalType.WEIGHT_LOSS))
        assert result.target_calories_kcal == 900
        assert result.target_calories_kcal != 1200

    def test_threshold_constant(self):
        """Threshold constant is exactly 1200."""
        assert LOW_CALORIE_THRESHOLD_KCAL == 1200


# ---------------------------------------------------------------------------
# Layer B: Post-Calculation Target Validity (calorie-v1 Rev1.2)
# ---------------------------------------------------------------------------


class TestPostCalculationTargetValidity:
    """Rev1.2: target <= 0 → ERROR before the low-calorie rule.

    Policy Test Matrix — Post-calculation Target Validity (Rev1.2).
    """

    def test_zero_target(self):
        """TDEE=500 + weight_loss → target 0 → ERROR, NEGATIVE_OR_ZERO_TARGET."""
        result = calculate_calorie_target(_make_input(500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert result.issues == [NEGATIVE_OR_ZERO_TARGET]
        assert result.issues == ["NEGATIVE_OR_ZERO_TARGET"]
        assert result.safety_flags == []

    def test_negative_target(self):
        """TDEE=400 + weight_loss → target -100 → ERROR, NEGATIVE_OR_ZERO_TARGET."""
        result = calculate_calorie_target(_make_input(400, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert result.issues == [NEGATIVE_OR_ZERO_TARGET]
        assert result.issues == ["NEGATIVE_OR_ZERO_TARGET"]
        assert result.safety_flags == []

    def test_just_below_threshold(self):
        """TDEE=1699 + weight_loss → target 1199 → OK + LOW_CALORIE flag."""
        result = calculate_calorie_target(_make_input(1699, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1199
        assert result.issues == []
        assert result.safety_flags == [LOW_CALORIE_REVIEW_REQUIRED]

    def test_exact_threshold(self):
        """TDEE=1700 + weight_loss → target 1200 → OK, no flag."""
        result = calculate_calorie_target(_make_input(1700, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1200
        assert result.issues == []
        assert result.safety_flags == []

    def test_positive_low_target(self):
        """TDEE=1500 + weight_loss → target 1000 → OK + LOW_CALORIE flag."""
        result = calculate_calorie_target(_make_input(1500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1000
        assert result.issues == []
        assert result.safety_flags == [LOW_CALORIE_REVIEW_REQUIRED]

    def test_maintenance_regression(self):
        """TDEE=2000 + maintenance → target 2000 → OK, no flag."""
        result = calculate_calorie_target(_make_input(2000, GoalType.MAINTENANCE))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 2000
        assert result.issues == []
        assert result.safety_flags == []

    def test_weight_gain_regression(self):
        """TDEE=2000 + weight_gain → target 2500 → OK, no flag."""
        result = calculate_calorie_target(_make_input(2000, GoalType.WEIGHT_GAIN))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 2500
        assert result.issues == []
        assert result.safety_flags == []

    def test_invariant_evaluated_before_low_calorie_zero(self):
        """Ordering: target=0 is ERROR, never OK + LOW_CALORIE flag."""
        result = calculate_calorie_target(_make_input(500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.ERROR
        assert "NEGATIVE_OR_ZERO_TARGET" in result.issues
        assert result.status != CalorieTargetStatus.OK
        assert LOW_CALORIE_REVIEW_REQUIRED not in result.safety_flags
        assert result.safety_flags == []

    def test_invariant_evaluated_before_low_calorie_negative(self):
        """Ordering: target=-100 is ERROR, never OK + LOW_CALORIE flag."""
        result = calculate_calorie_target(_make_input(400, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.ERROR
        assert "NEGATIVE_OR_ZERO_TARGET" in result.issues
        assert result.status != CalorieTargetStatus.OK
        assert LOW_CALORIE_REVIEW_REQUIRED not in result.safety_flags
        assert result.safety_flags == []

    def test_error_result_field_contract(self):
        """ERROR result: target None, tdee_kcal_used None, echo populated."""
        result = calculate_calorie_target(_make_input(500, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.ERROR
        assert result.target_calories_kcal is None
        assert result.tdee_kcal_used is None
        assert result.goal_type_used == GoalType.WEIGHT_LOSS
        assert result.calorie_adjustment_kcal == -500
        assert result.policy_version == "calorie-v1"
        assert result.traceability is not None
        assert result.traceability.policy_version == "calorie-v1"

    def test_positive_floor_not_introduced(self):
        """Every positive target stays OK with exact value (no 1200 floor)."""
        # TDEE=501 + weight_loss → target 1 → positive → OK + flag
        result = calculate_calorie_target(_make_input(501, GoalType.WEIGHT_LOSS))
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1
        assert result.safety_flags == [LOW_CALORIE_REVIEW_REQUIRED]

    def test_issue_code_constant(self):
        """NEGATIVE_OR_ZERO_TARGET is exactly the policy issue code."""
        assert NEGATIVE_OR_ZERO_TARGET == "NEGATIVE_OR_ZERO_TARGET"


# ---------------------------------------------------------------------------
# Goal Mapping
# ---------------------------------------------------------------------------


class TestGoalMapping:
    """Fixed V1 goal mapping values."""

    def test_mapping_maintenance(self):
        """maintenance → 0."""
        assert get_goal_adjustment(GoalType.MAINTENANCE) == 0
        assert GOAL_ADJUSTMENTS[GoalType.MAINTENANCE] == 0

    def test_mapping_weight_loss(self):
        """weight_loss → -500."""
        assert get_goal_adjustment(GoalType.WEIGHT_LOSS) == -500
        assert GOAL_ADJUSTMENTS[GoalType.WEIGHT_LOSS] == -500

    def test_mapping_weight_gain(self):
        """weight_gain → +500."""
        assert get_goal_adjustment(GoalType.WEIGHT_GAIN) == 500
        assert GOAL_ADJUSTMENTS[GoalType.WEIGHT_GAIN] == 500

    def test_mapping_muscle_gain(self):
        """muscle_gain → +500."""
        assert get_goal_adjustment(GoalType.MUSCLE_GAIN) == 500
        assert GOAL_ADJUSTMENTS[GoalType.MUSCLE_GAIN] == 500

    def test_mapping_has_no_extra_goals(self):
        """Mapping contains exactly the four policy goals."""
        assert set(GOAL_ADJUSTMENTS.keys()) == set(GoalType)


# ---------------------------------------------------------------------------
# Determinism / Metadata Isolation
# ---------------------------------------------------------------------------


class TestDeterminismAndIsolation:
    """Determinism and correlation_id metadata isolation."""

    def test_same_input_twice_identical(self):
        """Same input twice → identical output."""
        inp = _make_input(2500, GoalType.WEIGHT_LOSS, correlation_id="det-1")
        a = calculate_calorie_target(inp)
        b = calculate_calorie_target(inp)
        assert a.model_dump() == b.model_dump()

    def test_correlation_id_does_not_change_calculation(self):
        """correlation_id changes → calculation unchanged."""
        base_a = _make_input(2500, GoalType.WEIGHT_LOSS, correlation_id="id-1")
        base_b = _make_input(2500, GoalType.WEIGHT_LOSS, correlation_id="id-2")
        base_c = _make_input(2500, GoalType.WEIGHT_LOSS, correlation_id=None)
        ra = calculate_calorie_target(base_a)
        rb = calculate_calorie_target(base_b)
        rc = calculate_calorie_target(base_c)
        assert ra.target_calories_kcal == rb.target_calories_kcal == rc.target_calories_kcal == 2000
        assert ra.status == rb.status == rc.status == CalorieTargetStatus.OK

    def test_correlation_id_propagated_to_traceability(self):
        """correlation_id is preserved in traceability when provided."""
        result = calculate_calorie_target(
            _make_input(2500, GoalType.MAINTENANCE, correlation_id="trace-42")
        )
        assert result.traceability is not None
        assert result.traceability.correlation_id == "trace-42"

    def test_determinism_100_invocations(self):
        """100 invocations of the same input are identical."""
        inp = _make_input(2200, GoalType.WEIGHT_LOSS, correlation_id="determinism-test")
        results = [calculate_calorie_target(inp) for _ in range(100)]
        assert all(r.target_calories_kcal == 1700 for r in results)
        assert all(r.status == CalorieTargetStatus.OK for r in results)


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


class TestInvariants:
    """Mathematical invariants from the policy."""

    def test_weight_loss_lt_maintenance_lt_weight_gain(self):
        """For identical TDEE: weight_loss < maintenance < weight_gain."""
        tdee = 3000
        loss = calculate_calorie_target(_make_input(tdee, GoalType.WEIGHT_LOSS))
        maint = calculate_calorie_target(_make_input(tdee, GoalType.MAINTENANCE))
        gain = calculate_calorie_target(_make_input(tdee, GoalType.WEIGHT_GAIN))
        assert loss.target_calories_kcal < maint.target_calories_kcal
        assert maint.target_calories_kcal < gain.target_calories_kcal

    def test_maintenance_lt_muscle_gain(self):
        """For identical TDEE: maintenance < muscle_gain."""
        tdee = 3000
        maint = calculate_calorie_target(_make_input(tdee, GoalType.MAINTENANCE))
        muscle = calculate_calorie_target(_make_input(tdee, GoalType.MUSCLE_GAIN))
        assert maint.target_calories_kcal < muscle.target_calories_kcal

    def test_weight_gain_equals_muscle_gain(self):
        """For identical TDEE: weight_gain == muscle_gain (both +500)."""
        tdee = 3000
        wg = calculate_calorie_target(_make_input(tdee, GoalType.WEIGHT_GAIN))
        mg = calculate_calorie_target(_make_input(tdee, GoalType.MUSCLE_GAIN))
        assert wg.target_calories_kcal == mg.target_calories_kcal

    def test_target_is_integer_on_success(self):
        """Successful target is always a Python int."""
        for goal in GoalType:
            result = calculate_calorie_target(_make_input(2500, goal))
            assert isinstance(result.target_calories_kcal, int)

    def test_no_default_maintenance_when_goal_missing(self):
        """Missing goal is structural error — never silently defaults."""
        with pytest.raises(ValidationError):
            CalorieTargetInput(tdee_result=_ok_tdee())


# ---------------------------------------------------------------------------
# Safety / Regression Tests
# ---------------------------------------------------------------------------


class TestSafetyRegression:
    """Safety regressions: no high-calorie rule, no Decimal, no clamping."""

    def test_no_high_calorie_review_constant(self):
        """HIGH_CALORIE_REVIEW_REQUIRED does not exist in the package."""
        import app.nutrition.calorie_target as pkg
        import app.nutrition.calorie_target.calculator as calc_mod
        import app.nutrition.calorie_target.models as models_mod

        for mod in (pkg, calc_mod, models_mod):
            assert not hasattr(mod, "HIGH_CALORIE_REVIEW_REQUIRED")
        assert "HIGH_CALORIE_REVIEW_REQUIRED" not in dir(pkg)

    def test_no_high_calorie_in_source(self):
        """Calculator source contains no HIGH_CALORIE symbol or numeric threshold."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "HIGH_CALORIE" not in source
        assert "3500" not in source
        assert "high_calorie_threshold" not in source

    def test_result_never_contains_high_calorie_flag(self):
        """No result ever carries a high-calorie safety flag."""
        for goal in GoalType:
            result = calculate_calorie_target(_make_input(4000, goal))
            assert all("HIGH" not in flag for flag in result.safety_flags)

    def test_no_decimal_arithmetic_in_calculator(self):
        """Calculator module does not import Decimal."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "from decimal import" not in source
        assert "import decimal" not in source

    def test_target_is_int_not_float(self):
        """Successful target is int, never float."""
        result = calculate_calorie_target(_make_input(2501, GoalType.WEIGHT_LOSS))
        assert result.target_calories_kcal == 2001
        assert type(result.target_calories_kcal) is int

    def test_safety_flags_empty_on_success_above_threshold(self):
        """Above threshold, safety_flags remains empty."""
        result = calculate_calorie_target(_make_input(2500, GoalType.MAINTENANCE))
        assert result.safety_flags == []

    def test_failure_has_empty_safety_flags(self):
        """Failures never emit safety flags."""
        result = calculate_calorie_target(
            _make_input(goal=GoalType.WEIGHT_LOSS, tdee_result=_non_ok_tdee(TDEEStatus.ERROR))
        )
        assert result.safety_flags == []


# ---------------------------------------------------------------------------
# Traceability Tests
# ---------------------------------------------------------------------------


class TestTraceability:
    """Verify traceability contract."""

    def test_traceability_populated_on_ok(self):
        """Traceability is populated when status is OK."""
        result = calculate_calorie_target(_make_input(2500, GoalType.WEIGHT_LOSS))
        assert result.traceability is not None
        assert result.traceability.formula_expression == (
            "Target Calories = TDEE + Goal Adjustment"
        )
        assert result.traceability.arithmetic_mode == "integer"
        assert result.traceability.policy_version == "calorie-v1"

    def test_traceability_populated_on_failure(self):
        """Traceability is populated even on upstream failure (metadata)."""
        result = calculate_calorie_target(
            _make_input(tdee_result=_non_ok_tdee(TDEEStatus.INCOMPLETE))
        )
        assert result.traceability is not None
        assert result.traceability.policy_version == "calorie-v1"

    def test_traceability_no_timestamps(self):
        """Traceability must not contain timestamps or clock fields."""
        result = calculate_calorie_target(_make_input())
        trace_dict = result.traceability.model_dump()
        for key in trace_dict:
            assert "timestamp" not in key.lower()
            assert "time" not in key.lower()
            assert "clock" not in key.lower()
            assert "now" not in key.lower()

    def test_traceability_is_deterministic(self):
        """Identical inputs produce identical traceability dumps."""
        a = calculate_calorie_target(_make_input(2500, GoalType.MAINTENANCE, correlation_id="x"))
        b = calculate_calorie_target(_make_input(2500, GoalType.MAINTENANCE, correlation_id="x"))
        assert a.traceability.model_dump() == b.traceability.model_dump()


# ---------------------------------------------------------------------------
# Source-Level Isolation Tests
# ---------------------------------------------------------------------------


class TestSourceIsolation:
    """Calculator module must not pull external dependencies."""

    def test_no_llm_dependency(self):
        """Calculator does not import or use LLM modules."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        """Calculator does not import or use network modules."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source

    def test_no_database_dependency(self):
        """Calculator does not import database modules."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "sqlite" not in source
        assert "sqlalchemy" not in source
        assert "postgres" not in source

    def test_no_datetime_or_random(self):
        """Calculator does not use system clock or random state."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "datetime.now" not in source
        assert "time.time" not in source
        assert "import random" not in source

    def test_no_upstream_recalculation(self):
        """Calculator does not call ActivityClassifier, RMRCalculator, or TDEECalculator."""
        import app.nutrition.calorie_target.calculator as mod

        source = open(mod.__file__).read()
        assert "ActivityClassifier" not in source
        assert "RMRCalculator" not in source
        assert "calculate_tdee" not in source
        assert "Mifflin" not in source


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestCalorieTargetIntegration:
    """Integration with actual upstream components."""

    def setup_method(self):
        self.activity_classifier = ActivityClassifier()
        self.rmr_calculator = RMRCalculator()

    def test_full_pipeline_to_calorie_target(self):
        """Full pipeline: Activity → RMR → TDEE → CalorieTarget."""
        act_result = self.activity_classifier.classify(
            ActivityClassificationInput(
                occupational_activity="sedentary",
                daily_movement="low",
                training_days_per_week=0,
            )
        )
        assert act_result.status == ActivityClassificationStatus.OK

        rmr_result = self.rmr_calculator.calculate(
            RMRInput(age=30, gender="MALE", height_cm=180.0, weight_kg=80.0)
        )
        assert rmr_result.status == RMRStatus.OK

        tdee_result = calculate_tdee(
            TDEEInput(rmr_result=rmr_result, activity_result=act_result)
        )
        assert tdee_result.status == TDEEStatus.OK

        calorie_result = calculate_calorie_target(
            CalorieTargetInput(
                tdee_result=tdee_result,
                goal_type=GoalType.MAINTENANCE,
                correlation_id="integration-1",
            )
        )
        assert calorie_result.status == CalorieTargetStatus.OK
        assert calorie_result.tdee_kcal_used == tdee_result.tdee_kcal
        assert calorie_result.target_calories_kcal == tdee_result.tdee_kcal
        assert calorie_result.calorie_adjustment_kcal == 0
        assert calorie_result.traceability is not None
        assert calorie_result.traceability.correlation_id == "integration-1"

    def test_full_pipeline_weight_loss(self):
        """Full pipeline with weight_loss applies -500."""
        act_result = self.activity_classifier.classify(
            ActivityClassificationInput(
                occupational_activity="sedentary",
                daily_movement="low",
                training_days_per_week=3,
                training_duration_minutes=60,
                exercise_intensity="moderate",
            )
        )
        rmr_result = self.rmr_calculator.calculate(
            RMRInput(age=25, gender="FEMALE", height_cm=165.0, weight_kg=60.0)
        )
        tdee_result = calculate_tdee(
            TDEEInput(rmr_result=rmr_result, activity_result=act_result)
        )
        assert tdee_result.status == TDEEStatus.OK

        calorie_result = calculate_calorie_target(
            CalorieTargetInput(tdee_result=tdee_result, goal_type=GoalType.WEIGHT_LOSS)
        )
        assert calorie_result.status == CalorieTargetStatus.OK
        assert calorie_result.target_calories_kcal == tdee_result.tdee_kcal - 500
        assert calorie_result.calorie_adjustment_kcal == -500

    def test_integration_upstream_incomplete_propagates(self):
        """Upstream INCOMPLETE propagates through TDEE into CalorieTarget."""
        act_result = self.activity_classifier.classify(
            ActivityClassificationInput(
                occupational_activity="sedentary",
                daily_movement="low",
                training_days_per_week=4,
                # Missing duration and intensity → INCOMPLETE
            )
        )
        assert act_result.status == ActivityClassificationStatus.INCOMPLETE

        rmr_result = self.rmr_calculator.calculate(
            RMRInput(age=30, gender="MALE", height_cm=180.0, weight_kg=80.0)
        )
        tdee_result = calculate_tdee(
            TDEEInput(rmr_result=rmr_result, activity_result=act_result)
        )
        assert tdee_result.status == TDEEStatus.INCOMPLETE

        calorie_result = calculate_calorie_target(
            CalorieTargetInput(tdee_result=tdee_result, goal_type=GoalType.MAINTENANCE)
        )
        assert calorie_result.status == CalorieTargetStatus.INCOMPLETE
        assert calorie_result.target_calories_kcal is None

    def test_integration_low_calorie_flag_end_to_end(self):
        """End-to-end path can emit LOW_CALORIE_REVIEW_REQUIRED when TDEE is low."""
        low_tdee = TDEEResult(status=TDEEStatus.OK, issues=[], tdee_kcal=1699)
        result = calculate_calorie_target(
            CalorieTargetInput(tdee_result=low_tdee, goal_type=GoalType.WEIGHT_LOSS)
        )
        assert result.status == CalorieTargetStatus.OK
        assert result.target_calories_kcal == 1199
        assert LOW_CALORIE_REVIEW_REQUIRED in result.safety_flags
