"""Tests for TDEE Calculator contracts and domain logic.

Layer A: Contract validation tests (CT-001 to CT-006)
Layer B: Calculator domain tests (DT-001 to DT-026)
Property/invariant tests
Integration tests
"""

import math
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.nutrition.activity.activity_classifier import ActivityClassifier
from app.nutrition.activity.activity_models import (
    ActivityClassificationInput,
    ActivityClassificationResult,
)
from app.nutrition.rmr.rmr_calculator import RMRCalculator
from app.nutrition.rmr.rmr_models import RMRInput, RMRResult, RMRStatus
from app.nutrition.tdee.tdee_calculator import TDEE_POLICY_VERSION, calculate_tdee
from app.nutrition.tdee.tdee_models import (
    TDEEInput,
    TDEEResult,
    TDEEStatus,
    TDEETraceability,
)
from app.nutrition.models import ActivityCategory, ActivityClassificationStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok_rmr(kcal: int = 1780) -> RMRResult:
    """Create an OK RMRResult."""
    return RMRResult(
        status=RMRStatus.OK,
        issues=[],
        rmr_kcal=kcal,
        rmr_method="MIFFLIN_ST_JEOR",
        policy_version="rmr-v1",
    )


def _ok_activity(
    factor: float = 1.55,
    category: str = "moderate",
) -> ActivityClassificationResult:
    """Create an OK ActivityClassificationResult."""
    return ActivityClassificationResult(
        status=ActivityClassificationStatus.OK,
        issues=[],
        activity_category=ActivityCategory(category),
        activity_factor=factor,
        baseline_score=2,
        daily_movement_adjustment=0,
        wes_units=720,
        upgrade_score=1,
        final_score=2,
        policy_version="activity-v1",
    )


def _non_ok_rmr(
    status: RMRStatus = RMRStatus.INCOMPLETE,
    issues: list[str] | None = None,
) -> RMRResult:
    """Create a non-OK RMRResult."""
    return RMRResult(
        status=status,
        issues=issues or [],
    )


def _non_ok_activity(
    status: ActivityClassificationStatus = ActivityClassificationStatus.INCOMPLETE,
    issues: list[str] | None = None,
) -> ActivityClassificationResult:
    """Create a non-OK ActivityClassificationResult."""
    return ActivityClassificationResult(
        status=status,
        issues=issues or [],
    )


# ---------------------------------------------------------------------------
# Layer A: Contract Validation Tests (CT-001 to CT-006)
# ---------------------------------------------------------------------------


class TestTDEEInputContract:
    """Layer A: Schema boundary validation tests."""

    def test_ct001_missing_rmr_result(self):
        """CT-001: missing rmr_result → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(activity_result=_ok_activity())

    def test_ct001_rmr_result_none(self):
        """CT-001: rmr_result=None → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(rmr_result=None, activity_result=_ok_activity())

    def test_ct002_missing_activity_result(self):
        """CT-002: missing activity_result → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(rmr_result=_ok_rmr())

    def test_ct002_activity_result_none(self):
        """CT-002: activity_result=None → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(rmr_result=_ok_rmr(), activity_result=None)

    def test_ct003_rmr_result_wrong_type(self):
        """CT-003: rmr_result="1780" (string) → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(rmr_result="1780", activity_result=_ok_activity())

    def test_ct004_activity_result_wrong_type(self):
        """CT-004: activity_result={} (empty dict) → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(rmr_result=_ok_rmr(), activity_result={})

    def test_ct005_extra_field(self):
        """CT-005: extra_field injected → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(
                rmr_result=_ok_rmr(),
                activity_result=_ok_activity(),
                extra_field="unauthorized",
            )

    def test_ct006_invalid_correlation_id_type(self):
        """CT-006: correlation_id=12345 (int) → ValidationError."""
        with pytest.raises(ValidationError):
            TDEEInput(
                rmr_result=_ok_rmr(),
                activity_result=_ok_activity(),
                correlation_id=12345,
            )


# ---------------------------------------------------------------------------
# Layer B: Calculator Domain Tests (DT-001 to DT-026)
# ---------------------------------------------------------------------------


class TestTDEECalculatorHappyPath:
    """DT-001 to DT-004: Standard happy-path calculations."""

    def test_dt001_sedentary(self):
        """DT-001: RMR=1780, factor=1.20 → 2136."""
        inp = TDEEInput(rmr_result=_ok_rmr(1780), activity_result=_ok_activity(1.20, "sedentary"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 2136
        assert result.issues == []

    def test_dt002_light(self):
        """DT-002: RMR=1780, factor=1.35 → 2403."""
        inp = TDEEInput(rmr_result=_ok_rmr(1780), activity_result=_ok_activity(1.35, "light"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 2403

    def test_dt003_moderate(self):
        """DT-003: RMR=1780, factor=1.55 → 2759."""
        inp = TDEEInput(rmr_result=_ok_rmr(1780), activity_result=_ok_activity(1.55, "moderate"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 2759

    def test_dt004_high(self):
        """DT-004: RMR=1780, factor=1.75 → 3115."""
        inp = TDEEInput(rmr_result=_ok_rmr(1780), activity_result=_ok_activity(1.75, "high"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 3115


class TestTDEECalculatorUpstreamState:
    """DT-005 to DT-010: Upstream status propagation."""

    def test_dt005_rmr_incomplete(self):
        """DT-005: RMR=INCOMPLETE, Activity=OK → INCOMPLETE."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.INCOMPLETE),
            activity_result=_ok_activity(),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INCOMPLETE
        assert result.tdee_kcal is None
        assert "UPSTREAM_RMR_NOT_OK" in result.issues

    def test_dt006_activity_incomplete(self):
        """DT-006: RMR=OK, Activity=INCOMPLETE → INCOMPLETE."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(),
            activity_result=_non_ok_activity(ActivityClassificationStatus.INCOMPLETE),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INCOMPLETE
        assert result.tdee_kcal is None
        assert "UPSTREAM_ACTIVITY_NOT_OK" in result.issues

    def test_dt007_rmr_invalid(self):
        """DT-007: RMR=INVALID, Activity=OK → INVALID."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.INVALID),
            activity_result=_ok_activity(),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert result.tdee_kcal is None
        assert "UPSTREAM_RMR_NOT_OK" in result.issues

    def test_dt008_activity_invalid(self):
        """DT-008: RMR=OK, Activity=INVALID → INVALID."""
        # ActivityClassificationStatus uses CONFLICT, not INVALID
        inp = TDEEInput(
            rmr_result=_ok_rmr(),
            activity_result=_non_ok_activity(ActivityClassificationStatus.CONFLICT),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert result.tdee_kcal is None
        assert "UPSTREAM_ACTIVITY_NOT_OK" in result.issues

    def test_dt009_rmr_error(self):
        """DT-009: RMR=ERROR, Activity=OK → ERROR."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.ERROR),
            activity_result=_ok_activity(),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert result.tdee_kcal is None
        assert "UPSTREAM_RMR_NOT_OK" in result.issues

    def test_dt010_activity_error(self):
        """DT-010: RMR=OK, Activity=ERROR → ERROR."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(),
            activity_result=_non_ok_activity(ActivityClassificationStatus.ERROR),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert result.tdee_kcal is None
        assert "UPSTREAM_ACTIVITY_NOT_OK" in result.issues


class TestTDEECalculatorErrorPrecedence:
    """DT-011 to DT-013: Error severity precedence."""

    def test_dt011_invalid_over_incomplete(self):
        """DT-011: RMR=INVALID, Activity=INCOMPLETE → INVALID."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.INVALID),
            activity_result=_non_ok_activity(ActivityClassificationStatus.INCOMPLETE),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID

    def test_dt012_incomplete_with_invalid(self):
        """DT-012: RMR=INCOMPLETE, Activity=CONFLICT → INVALID."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.INCOMPLETE),
            activity_result=_non_ok_activity(ActivityClassificationStatus.CONFLICT),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID

    def test_dt013_error_over_invalid(self):
        """DT-013: RMR=ERROR, Activity=CONFLICT → ERROR."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.ERROR),
            activity_result=_non_ok_activity(ActivityClassificationStatus.CONFLICT),
        )
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR


class TestTDEECalculatorFieldIntegrity:
    """DT-014 to DT-015: Domain validation for missing fields."""

    def test_dt014_rmr_kcal_none(self):
        """DT-014: RMR OK but rmr_kcal=None → ERROR, MISSING_RMR_VALUE."""
        rmr = RMRResult(
            status=RMRStatus.OK,
            issues=[],
            rmr_kcal=None,
            rmr_method=None,
        )
        inp = TDEEInput(rmr_result=rmr, activity_result=_ok_activity())
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert result.tdee_kcal is None
        assert "MISSING_RMR_VALUE" in result.issues

    def test_dt015_activity_factor_none(self):
        """DT-015: Activity OK but factor=None → ERROR, MISSING_ACTIVITY_FACTOR_VALUE."""
        act = ActivityClassificationResult(
            status=ActivityClassificationStatus.OK,
            issues=[],
            activity_category=ActivityCategory.MODERATE,
            activity_factor=None,
        )
        inp = TDEEInput(rmr_result=_ok_rmr(), activity_result=act)
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert result.tdee_kcal is None
        assert "MISSING_ACTIVITY_FACTOR_VALUE" in result.issues


class TestTDEECalculatorNumericSafety:
    """DT-016 to DT-021: Numeric safety validation."""

    def test_dt016_rmr_zero(self):
        """DT-016: RMR=0 → INVALID, RMR_VALUE_NON_POSITIVE."""
        inp = TDEEInput(rmr_result=_ok_rmr(0), activity_result=_ok_activity())
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert "RMR_VALUE_NON_POSITIVE" in result.issues

    def test_dt017_rmr_negative(self):
        """DT-017: RMR=-1500 → INVALID, RMR_VALUE_NON_POSITIVE."""
        rmr = RMRResult.model_construct(
            status=RMRStatus.OK,
            issues=[],
            rmr_kcal=-1500,
            rmr_method="MIFFLIN_ST_JEOR",
        )
        inp = TDEEInput(rmr_result=rmr, activity_result=_ok_activity())
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert "RMR_VALUE_NON_POSITIVE" in result.issues

    def test_dt018_factor_zero(self):
        """DT-018: Factor=0.0 → INVALID, ACTIVITY_FACTOR_NON_POSITIVE."""
        inp = TDEEInput(rmr_result=_ok_rmr(), activity_result=_ok_activity(0.0))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert "ACTIVITY_FACTOR_NON_POSITIVE" in result.issues

    def test_dt019_factor_negative(self):
        """DT-019: Factor=-1.35 → INVALID, ACTIVITY_FACTOR_NON_POSITIVE."""
        inp = TDEEInput(rmr_result=_ok_rmr(), activity_result=_ok_activity(-1.35))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.INVALID
        assert "ACTIVITY_FACTOR_NON_POSITIVE" in result.issues

    def test_dt020_rmr_nan(self):
        """DT-020: RMR=NaN → ERROR, NON_FINITE_INPUT."""
        rmr = RMRResult.model_construct(
            status=RMRStatus.OK,
            issues=[],
            rmr_kcal=float("nan"),
            rmr_method="MIFFLIN_ST_JEOR",
        )
        inp = TDEEInput(rmr_result=rmr, activity_result=_ok_activity())
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert "NON_FINITE_INPUT" in result.issues

    def test_dt021_factor_positive_infinity(self):
        """DT-021: Factor=+Infinity → ERROR, NON_FINITE_INPUT."""
        act = ActivityClassificationResult(
            status=ActivityClassificationStatus.OK,
            issues=[],
            activity_category=ActivityCategory.MODERATE,
            activity_factor=float("inf"),
        )
        inp = TDEEInput(rmr_result=_ok_rmr(), activity_result=act)
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert "NON_FINITE_INPUT" in result.issues

    def test_dt021b_rmr_negative_infinity(self):
        """RMR=-Infinity → ERROR, NON_FINITE_INPUT."""
        rmr = RMRResult.model_construct(
            status=RMRStatus.OK,
            issues=[],
            rmr_kcal=float("-inf"),
            rmr_method="MIFFLIN_ST_JEOR",
        )
        inp = TDEEInput(rmr_result=rmr, activity_result=_ok_activity())
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert "NON_FINITE_INPUT" in result.issues

    def test_dt021c_factor_negative_infinity(self):
        """Factor=-Infinity → ERROR, NON_FINITE_INPUT."""
        act = ActivityClassificationResult(
            status=ActivityClassificationStatus.OK,
            issues=[],
            activity_category=ActivityCategory.MODERATE,
            activity_factor=float("-inf"),
        )
        inp = TDEEInput(rmr_result=_ok_rmr(), activity_result=act)
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.ERROR
        assert "NON_FINITE_INPUT" in result.issues


class TestTDEECalculatorDecimalAndRounding:
    """DT-022 to DT-025: Decimal conversion and rounding."""

    def test_dt022_decimal_conversion(self):
        """DT-022: RMR=1000, factor=1.35 → 1350 (exact string boundary)."""
        inp = TDEEInput(rmr_result=_ok_rmr(1000), activity_result=_ok_activity(1.35, "light"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 1350
        assert result.activity_factor_used == Decimal("1.35")

    def test_dt023_rounding_below_half(self):
        """DT-023: 1613 × 1.55 = 2500.15 → 2500 (below .5, round down)."""
        inp = TDEEInput(rmr_result=_ok_rmr(1613), activity_result=_ok_activity(1.55, "moderate"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 2500

    def test_dt024_rounding_exact_half(self):
        """DT-024: 1510 × 1.35 = 2038.50 → 2039 (exact .5, round up)."""
        inp = TDEEInput(rmr_result=_ok_rmr(1510), activity_result=_ok_activity(1.35, "light"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 2039

    def test_dt025_rounding_above_half(self):
        """DT-025: 1425 × 1.35 = 1923.75 → 1924 (above .5, round up)."""
        inp = TDEEInput(rmr_result=_ok_rmr(1425), activity_result=_ok_activity(1.35, "light"))
        result = calculate_tdee(inp)
        assert result.status == TDEEStatus.OK
        assert result.tdee_kcal == 1924


class TestTDEECalculatorMetadataIsolation:
    """DT-026: correlation_id does not affect calculation."""

    def test_dt026_correlation_id_isolation(self):
        """DT-026: correlation_id does not change arithmetic."""
        base = dict(rmr_result=_ok_rmr(1780), activity_result=_ok_activity(1.55, "moderate"))

        result_a = calculate_tdee(TDEEInput(**base, correlation_id="test-123"))
        result_b = calculate_tdee(TDEEInput(**base, correlation_id=None))
        result_c = calculate_tdee(TDEEInput(**base, correlation_id="different-id"))

        assert result_a.tdee_kcal == result_b.tdee_kcal == result_c.tdee_kcal == 2759
        assert result_a.status == result_b.status == result_c.status == TDEEStatus.OK


# ---------------------------------------------------------------------------
# Property / Invariant Tests
# ---------------------------------------------------------------------------


class TestTDEEInvariants:
    """Mathematical invariants from the policy."""

    def test_baseline_maintenance_floor(self):
        """For positive RMR and factor >= 1.0: TDEE >= RMR."""
        for rmr_val in [500, 1000, 1500, 2000, 3000]:
            for factor in [1.0, 1.20, 1.35, 1.55, 1.75]:
                inp = TDEEInput(
                    rmr_result=_ok_rmr(rmr_val),
                    activity_result=_ok_activity(factor),
                )
                result = calculate_tdee(inp)
                assert result.tdee_kcal >= rmr_val, (
                    f"TDEE {result.tdee_kcal} < RMR {rmr_val} for factor {factor}"
                )

    def test_monotonic_activity(self):
        """Increasing factor → TDEE does not decrease (holding RMR constant)."""
        rmr_val = 1500
        factors = [1.20, 1.35, 1.55, 1.75]
        prev_tdee = 0
        for factor in factors:
            inp = TDEEInput(
                rmr_result=_ok_rmr(rmr_val),
                activity_result=_ok_activity(factor),
            )
            result = calculate_tdee(inp)
            assert result.tdee_kcal >= prev_tdee
            prev_tdee = result.tdee_kcal

    def test_monotonic_rmr(self):
        """Increasing RMR → TDEE does not decrease (holding factor constant)."""
        factor = 1.55
        rmr_values = [500, 1000, 1500, 2000, 3000]
        prev_tdee = 0
        for rmr_val in rmr_values:
            inp = TDEEInput(
                rmr_result=_ok_rmr(rmr_val),
                activity_result=_ok_activity(factor),
            )
            result = calculate_tdee(inp)
            assert result.tdee_kcal >= prev_tdee
            prev_tdee = result.tdee_kcal

    def test_correlation_id_invariance(self):
        """Changing correlation_id does not change calculation."""
        base_input = TDEEInput(
            rmr_result=_ok_rmr(1780),
            activity_result=_ok_activity(1.55),
        )
        result_1 = calculate_tdee(TDEEInput(
            rmr_result=base_input.rmr_result,
            activity_result=base_input.activity_result,
            correlation_id="id-1",
        ))
        result_2 = calculate_tdee(TDEEInput(
            rmr_result=base_input.rmr_result,
            activity_result=base_input.activity_result,
            correlation_id="id-2",
        ))
        assert result_1.tdee_kcal == result_2.tdee_kcal
        assert result_1.status == result_2.status

    def test_tdee_does_not_use_goal(self):
        """TDEE result is independent of goal-related fields."""
        rmr = _ok_rmr(1780)
        act = _ok_activity(1.55)
        result = calculate_tdee(TDEEInput(rmr_result=rmr, activity_result=act))
        # TDEE should not reference goal in any way
        assert result.tdee_kcal == 2759

    def test_tdee_does_not_recalculate_rmr(self):
        """TDEE uses rmr_kcal as-is, never recalculates."""
        rmr = _ok_rmr(1780)
        act = _ok_activity(1.55)
        result = calculate_tdee(TDEEInput(rmr_result=rmr, activity_result=act))
        assert result.rmr_kcal_used == 1780


# ---------------------------------------------------------------------------
# Traceability Tests
# ---------------------------------------------------------------------------


class TestTDEETraceability:
    """Verify traceability contract."""

    def test_traceability_populated_on_ok(self):
        """Traceability is populated when status is OK."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(1780),
            activity_result=_ok_activity(1.55),
        )
        result = calculate_tdee(inp)
        assert result.traceability is not None
        assert result.traceability.rmr_kcal_used == 1780
        assert result.traceability.activity_factor_used == "1.55"
        assert result.traceability.formula_expression == "TDEE = RMR * ActivityFactor"
        assert result.traceability.rounding_mode == "ROUND_HALF_UP"
        assert result.traceability.policy_version == "tdee-v1"

    def test_traceability_none_on_failure(self):
        """Traceability is None when status is not OK."""
        inp = TDEEInput(
            rmr_result=_non_ok_rmr(RMRStatus.INCOMPLETE),
            activity_result=_ok_activity(),
        )
        result = calculate_tdee(inp)
        assert result.traceability is None

    def test_traceability_raw_tdee_unrounded(self):
        """Traceability contains unrounded product string."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(1510),
            activity_result=_ok_activity(1.35),
        )
        result = calculate_tdee(inp)
        # 1510 × 1.35 = 2038.50
        assert result.traceability is not None
        assert "2038.5" in result.traceability.raw_tdee_unrounded

    def test_traceability_no_timestamps(self):
        """Traceability must not contain timestamps."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(1780),
            activity_result=_ok_activity(1.55),
        )
        result = calculate_tdee(inp)
        trace_dict = result.traceability.model_dump()
        for key in trace_dict:
            assert "timestamp" not in key.lower()
            assert "time" not in key.lower()


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestTDEEIntegration:
    """Integration tests using actual upstream components."""

    def setup_method(self):
        self.activity_classifier = ActivityClassifier()
        self.rmr_calculator = RMRCalculator()

    def test_full_pipeline_activity_rmr_tdee(self):
        """Full pipeline: ActivityClassifier + RMRCalculator → TDEE."""
        # Activity classification
        act_input = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=0,
        )
        act_result = self.activity_classifier.classify(act_input)
        assert act_result.status == ActivityClassificationStatus.OK

        # RMR calculation
        rmr_input = RMRInput(age=30, gender="MALE", height_cm=180.0, weight_kg=80.0)
        rmr_result = self.rmr_calculator.calculate(rmr_input)
        assert rmr_result.status == RMRStatus.OK

        # TDEE calculation
        tdee_input = TDEEInput(rmr_result=rmr_result, activity_result=act_result)
        tdee_result = calculate_tdee(tdee_input)

        assert tdee_result.status == TDEEStatus.OK
        assert tdee_result.tdee_kcal is not None
        assert tdee_result.tdee_kcal > 0
        assert tdee_result.rmr_kcal_used == rmr_result.rmr_kcal
        assert tdee_result.activity_category_used == act_result.activity_category

    def test_integration_with_moderate_activity(self):
        """Integration with moderate activity classification."""
        act_input = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=3,
            training_duration_minutes=60,
            exercise_intensity="moderate",
        )
        act_result = self.activity_classifier.classify(act_input)
        assert act_result.status == ActivityClassificationStatus.OK

        rmr_input = RMRInput(age=25, gender="FEMALE", height_cm=165.0, weight_kg=60.0)
        rmr_result = self.rmr_calculator.calculate(rmr_input)
        assert rmr_result.status == RMRStatus.OK

        tdee_result = calculate_tdee(TDEEInput(
            rmr_result=rmr_result, activity_result=act_result,
        ))
        assert tdee_result.status == TDEEStatus.OK
        assert tdee_result.tdee_kcal == 1816
        assert tdee_result.rmr_kcal_used == rmr_result.rmr_kcal

    def test_integration_upstream_error_propagation(self):
        """Integration: upstream INCOMPLETE propagates through TDEE."""
        act_input = ActivityClassificationInput(
            occupational_activity="sedentary",
            daily_movement="low",
            training_days_per_week=4,
            # Missing duration and intensity → INCOMPLETE
        )
        act_result = self.activity_classifier.classify(act_input)
        # This should be INCOMPLETE
        assert act_result.status == ActivityClassificationStatus.INCOMPLETE

        rmr_input = RMRInput(age=30, gender="MALE", height_cm=180.0, weight_kg=80.0)
        rmr_result = self.rmr_calculator.calculate(rmr_input)
        assert rmr_result.status == RMRStatus.OK

        tdee_result = calculate_tdee(TDEEInput(
            rmr_result=rmr_result, activity_result=act_result,
        ))
        assert tdee_result.status == TDEEStatus.INCOMPLETE
        assert tdee_result.tdee_kcal is None
        assert "UPSTREAM_ACTIVITY_NOT_OK" in tdee_result.issues

    def test_determinism_across_invocations(self):
        """Same input always produces same output."""
        inp = TDEEInput(
            rmr_result=_ok_rmr(1780),
            activity_result=_ok_activity(1.55),
            correlation_id="determinism-test",
        )
        results = [calculate_tdee(inp) for _ in range(100)]
        assert all(r.tdee_kcal == 2759 for r in results)
        assert all(r.status == TDEEStatus.OK for r in results)

    def test_no_llm_dependency(self):
        """Calculator does not import or use LLM modules."""
        import app.nutrition.tdee.tdee_calculator as mod
        source = open(mod.__file__).read()
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        """Calculator does not import or use network modules."""
        import app.nutrition.tdee.tdee_calculator as mod
        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source
