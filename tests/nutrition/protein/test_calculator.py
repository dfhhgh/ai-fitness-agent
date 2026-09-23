"""Tests for Protein Calculator contracts and domain logic (protein-v1).

Layer A: Contract validation (strict Pydantic, no coercion)
Layer B: Calculator domain (goals, weight domain, rounding, nullability)
Suites A–J per policy §21 and project handoff:
  A Happy path, B Goal validation, C Weight validation, D Strict contract,
  E Non-finite, F Rounding, G Output contract, H Immutability,
  I Threshold isolation, J Integration (GoalType adapter + target binding)
"""

import inspect
import math

import pytest
from pydantic import ValidationError

from app.nutrition.models import AssessmentStatus, GoalType, NutritionTargets
from app.nutrition.protein import (
    GOAL_FACTORS,
    PROTEIN_FACTOR_DEFAULT,
    PROTEIN_FACTOR_MAINTENANCE,
    PROTEIN_POLICY_VERSION,
    WEIGHT_DOMAIN_MAX_KG,
    WEIGHT_DOMAIN_MIN_KG,
    ProteinGoal,
    ProteinInput,
    ProteinIssueCode,
    ProteinResult,
    ProteinStatus,
    bind_protein_target,
    build_protein_input,
    calculate_protein,
    get_protein_factor,
    map_goal_to_protein_goal,
)
from app.nutrition.protein.calculator import _round_protein_grams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    weight: float | None = 70.0,
    goal: ProteinGoal | None = ProteinGoal.MAINTENANCE,
) -> ProteinInput:
    return ProteinInput(current_weight_kg=weight, goal=goal)


def _calc(
    weight: float | None = 70.0,
    goal: ProteinGoal | None = ProteinGoal.MAINTENANCE,
) -> ProteinResult:
    return calculate_protein(_make_input(weight, goal))


def _make_targets(protein_g: float = 160.0) -> NutritionTargets:
    return NutritionTargets(
        calories_kcal=2200.0,
        protein_g=protein_g,
        fat_g=61.0,
        carbohydrates_g=250.0,
        status=AssessmentStatus.OK,
    )


# ---------------------------------------------------------------------------
# Suite A: Happy Path (all four goals)
# ---------------------------------------------------------------------------


class TestSuiteAHappyPath:
    """A-01..A-04: standard calculations for all four goals."""

    def test_a01_standard_maintenance(self):
        """A-01: 70.0 MAINTENANCE -> OK, protein_g = 84."""
        result = _calc(70.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 84
        assert result.protein_factor_g_per_kg == 1.2
        assert result.current_weight_kg == 70.0
        assert result.goal == ProteinGoal.MAINTENANCE
        assert result.policy_version == "protein-v1"

    def test_a02_standard_weight_loss(self):
        """A-02: 85.0 WEIGHT_LOSS -> OK, protein_g = 136."""
        result = _calc(85.0, ProteinGoal.WEIGHT_LOSS)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 136
        assert result.protein_factor_g_per_kg == 1.6

    def test_a03_standard_weight_gain(self):
        """A-03: 60.0 WEIGHT_GAIN -> OK, protein_g = 96."""
        result = _calc(60.0, ProteinGoal.WEIGHT_GAIN)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 96
        assert result.protein_factor_g_per_kg == 1.6

    def test_a04_standard_muscle_gain(self):
        """A-04: 90.0 MUSCLE_GAIN -> OK, protein_g = 144."""
        result = _calc(90.0, ProteinGoal.MUSCLE_GAIN)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 144
        assert result.protein_factor_g_per_kg == 1.6


# ---------------------------------------------------------------------------
# Suite B: Goal Validation
# ---------------------------------------------------------------------------


class TestSuiteBGoalValidation:
    """B: missing goal, unsupported goal strings, bypass reject."""

    def test_b01_missing_goal(self):
        """B-01: goal None -> INCOMPLETE / MISSING_GOAL; weight echoed."""
        result = _calc(70.0, None)
        assert result.status == ProteinStatus.INCOMPLETE
        assert result.issues == (ProteinIssueCode.MISSING_GOAL,)
        assert result.protein_g is None
        assert result.protein_factor_g_per_kg is None
        assert result.current_weight_kg == 70.0
        assert result.goal is None

    def test_b02_unsupported_goal_string_schema(self):
        """B-02: 'BULK' rejected at strict schema (OPTION A -> ValidationError)."""
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=70.0, goal="BULK")

    def test_b03_incorrect_case_string_schema(self):
        """B-03: 'maintenance' rejected at strict schema (case-sensitive)."""
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=70.0, goal="maintenance")

    def test_b_missing_both_weight_first(self):
        """Both missing -> first failure is MISSING_WEIGHT."""
        result = _calc(None, None)
        assert result.status == ProteinStatus.INCOMPLETE
        assert result.issues == (ProteinIssueCode.MISSING_WEIGHT,)
        assert result.protein_g is None

    def test_all_four_goals_accepted(self):
        """All four ProteinGoal members are accepted at schema level."""
        for goal in (
            ProteinGoal.MAINTENANCE,
            ProteinGoal.WEIGHT_LOSS,
            ProteinGoal.WEIGHT_GAIN,
            ProteinGoal.MUSCLE_GAIN,
        ):
            inp = ProteinInput(current_weight_kg=70.0, goal=goal)
            assert inp.goal == goal

    def test_bypass_unsupported_goal_raises_value_error(self):
        """model_construct bypass with bad goal -> ValueError, never OK."""
        bypass = ProteinInput.model_construct(
            current_weight_kg=70.0,
            goal="BULK",
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_protein(bypass)

    def test_bypass_lowercase_goal_raises_value_error(self):
        """Bypass with lowercase 'maintenance' -> ValueError (case-sensitive)."""
        bypass = ProteinInput.model_construct(
            current_weight_kg=70.0,
            goal="maintenance",
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_protein(bypass)

    def test_bypass_shared_goaltype_raises_value_error(self):
        """Shared GoalType must not enter Layer A without adapter mapping."""
        bypass = ProteinInput.model_construct(
            current_weight_kg=70.0,
            goal=GoalType.MUSCLE_GAIN,
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_protein(bypass)

    def test_bypass_never_falls_through_to_maintenance(self):
        """Regression: bad goal never returns maintenance-style OK @ 1.2."""
        bypass = ProteinInput.model_construct(
            current_weight_kg=70.0,
            goal="BULK",
        )
        with pytest.raises(ValueError):
            calculate_protein(bypass)

    def test_bypass_muscle_gain_as_goaltype_raises(self):
        """GoalType.MUSCLE_GAIN (lowercase value) is not ProteinGoal."""
        bypass = ProteinInput.model_construct(
            current_weight_kg=90.0,
            goal=GoalType.MUSCLE_GAIN,
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_protein(bypass)


# ---------------------------------------------------------------------------
# Suite C: Weight Validation
# ---------------------------------------------------------------------------


class TestSuiteCWeightValidation:
    """C: missing/zero/negative/string/bool/non-finite/boundaries."""

    def test_c01_missing_weight(self):
        """C-01: weight None, valid goal -> INCOMPLETE / MISSING_WEIGHT."""
        result = _calc(None, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INCOMPLETE
        assert result.issues == (ProteinIssueCode.MISSING_WEIGHT,)
        assert result.protein_g is None
        assert result.protein_factor_g_per_kg is None
        assert result.current_weight_kg is None
        assert result.goal == ProteinGoal.MAINTENANCE

    def test_c02_zero_weight(self):
        """C-02: 0.0 -> INVALID / INVALID_WEIGHT."""
        result = _calc(0.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)
        assert result.protein_g is None

    def test_c03_negative_weight(self):
        """C-03: -70.0 -> INVALID / INVALID_WEIGHT."""
        result = _calc(-70.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)
        assert result.protein_g is None

    def test_c04_string_weight_schema(self):
        """C-04: '70.0' rejected at strict schema (OPTION A -> ValidationError)."""
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg="70.0", goal=ProteinGoal.MAINTENANCE)

    def test_c05_boolean_weight_schema(self):
        """C-05: True rejected at strict schema (no bool->float coercion)."""
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=True, goal=ProteinGoal.MAINTENANCE)

    def test_c06_nan_weight(self):
        """C-06: NaN passes float schema; domain rejects INVALID_WEIGHT."""
        result = _calc(float("nan"), ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)
        assert result.protein_g is None
        assert result.protein_factor_g_per_kg is None
        assert math.isnan(result.current_weight_kg)

    def test_c07_pos_inf_weight(self):
        """C-07: +Infinity -> INVALID / INVALID_WEIGHT."""
        result = _calc(float("inf"), ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)
        assert result.protein_g is None

    def test_c07_neg_inf_weight(self):
        """C-07b: -Infinity -> INVALID / INVALID_WEIGHT."""
        result = _calc(float("-inf"), ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)
        assert result.protein_g is None

    def test_c08_below_range_weight(self):
        """C-08: 0.4 (< 0.5) -> INVALID / OUT_OF_RANGE_WEIGHT."""
        result = _calc(0.4, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.OUT_OF_RANGE_WEIGHT,)
        assert result.protein_g is None

    def test_c09_above_range_weight(self):
        """C-09: 500.1 (> 500.0) -> INVALID / OUT_OF_RANGE_WEIGHT."""
        result = _calc(500.1, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.OUT_OF_RANGE_WEIGHT,)
        assert result.protein_g is None

    def test_c10_lower_range_boundary(self):
        """C-10: 0.5 WEIGHT_LOSS -> OK, protein_g = 1 (0.8 -> half-up 1)."""
        result = _calc(0.5, ProteinGoal.WEIGHT_LOSS)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 1

    def test_c11_upper_range_boundary(self):
        """C-11: 500.0 WEIGHT_LOSS -> OK, protein_g = 800."""
        result = _calc(500.0, ProteinGoal.WEIGHT_LOSS)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 800

    def test_just_inside_low_boundary(self):
        """0.5000001 is within domain."""
        result = _calc(0.5000001, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK

    def test_just_inside_high_boundary(self):
        """499.9999 is within domain."""
        result = _calc(499.9999, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK

    def test_weight_zero_point_five_maintenance(self):
        """0.5 MAINTENANCE: 0.6 -> 1 gram."""
        result = _calc(0.5, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 1

    def test_negative_zero_weight(self):
        """-0.0 is <= 0 -> INVALID_WEIGHT."""
        result = _calc(-0.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.INVALID
        assert result.issues == (ProteinIssueCode.INVALID_WEIGHT,)


# ---------------------------------------------------------------------------
# Suite D: Strict Contract (schema -> ValidationError)
# ---------------------------------------------------------------------------


class TestSuiteDStrictContract:
    """D: schema violations raise ValidationError, never ProteinResult."""

    def test_string_weight_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ProteinInput(current_weight_kg="70.0", goal=ProteinGoal.MAINTENANCE)
        assert not isinstance(exc_info.value, ProteinResult)

    def test_bool_weight_rejected(self):
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=True, goal=ProteinGoal.MAINTENANCE)

    def test_list_weight_rejected(self):
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=[], goal=ProteinGoal.MAINTENANCE)

    def test_int_weight_accepted_as_float(self):
        """Pydantic strict float still accepts int (promoted to float).

        Policy hardening targets string/bool coercion, not int->float.
        """
        inp = ProteinInput(current_weight_kg=70, goal=ProteinGoal.MAINTENANCE)
        assert inp.current_weight_kg == 70.0
        assert isinstance(inp.current_weight_kg, float)

    def test_invalid_goal_string_rejected(self):
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=70.0, goal="BULK")

    def test_shared_goaltype_rejected(self):
        """GoalType members do not match ProteinGoal values (adapter required)."""
        with pytest.raises(ValidationError):
            ProteinInput(current_weight_kg=70.0, goal=GoalType.MAINTENANCE)

    def test_extra_fields_rejected(self):
        """extra='forbid' on input."""
        with pytest.raises(ValidationError):
            ProteinInput(
                current_weight_kg=70.0,
                goal=ProteinGoal.MAINTENANCE,
                body_fat=12.0,
            )

    def test_missing_both_fields_defaults_none(self):
        """Optional defaults allow empty input -> domain INCOMPLETE."""
        inp = ProteinInput()
        assert inp.current_weight_kg is None
        assert inp.goal is None

    def test_result_strict_rejects_string_status(self):
        """ProteinResult status is strict enum, not free string."""
        with pytest.raises(ValidationError):
            ProteinResult(status="ok")

    def test_result_rejects_float_protein_g_strict(self):
        """protein_g must be int under strict=True."""
        with pytest.raises(ValidationError):
            ProteinResult(
                status=ProteinStatus.OK,
                protein_g=84.0,
                protein_factor_g_per_kg=1.2,
            )

    def test_input_config_strict_frozen_forbid(self):
        config = ProteinInput.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_result_config_strict_frozen_forbid(self):
        config = ProteinResult.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"


# ---------------------------------------------------------------------------
# Suite E: Threshold Isolation (no 0.8 / 3.0 flags in Layer A)
# ---------------------------------------------------------------------------


class TestSuiteEThresholdIsolation:
    """E: Layer A has no clinical threshold flags or issue codes."""

    def test_e01_maintenance_no_threshold_flags(self):
        """E-01: 100.0 MAINTENANCE -> OK, empty issues, no threshold codes."""
        result = _calc(100.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 120

    def test_e02_muscle_gain_no_threshold_flags(self):
        """E-02: 100.0 MUSCLE_GAIN -> OK, empty issues."""
        result = _calc(100.0, ProteinGoal.MUSCLE_GAIN)
        assert result.status == ProteinStatus.OK
        assert result.issues == ()
        assert result.protein_g == 160

    def test_no_threshold_issue_codes_in_enum(self):
        """ProteinIssueCode has no BELOW_REFERENCE / ABOVE_UPPER flags."""
        names = {c.name for c in ProteinIssueCode}
        assert "PROTEIN_BELOW_REFERENCE" not in names
        assert "PROTEIN_ABOVE_UPPER_WARNING" not in names
        assert "BELOW_RDA" not in names

    def test_no_threshold_literals_in_calculator_source(self):
        """Calculator executable code has no threshold checks/flags."""
        import ast

        import app.nutrition.protein.calculator as mod

        tree = ast.parse(inspect.getsource(mod))
        # Collect string constants only from non-docstring contexts via
        # full source scan of comparisons is overkill — assert no flag
        # identifiers and no bare threshold numeric compares in code.
        source = inspect.getsource(mod)
        assert "BELOW_REFERENCE" not in source
        assert "ABOVE_UPPER" not in source
        assert "0.8" not in source
        assert "3.0" not in source
        # ensure module still parses (sanity)
        assert tree is not None

    def test_no_threshold_fields_on_result(self):
        """Result model has no threshold flag fields."""
        fields = set(ProteinResult.model_fields)
        for forbidden in (
            "below_reference",
            "above_upper",
            "safety_flags",
            "review_flags",
            "threshold_flags",
        ):
            assert forbidden not in fields

    def test_issue_codes_are_only_operational(self):
        """Only the six policy operational issue codes exist."""
        assert {c.name for c in ProteinIssueCode} == {
            "MISSING_WEIGHT",
            "INVALID_WEIGHT",
            "OUT_OF_RANGE_WEIGHT",
            "MISSING_GOAL",
            "UNSUPPORTED_GOAL",
            "INTERNAL_ERROR",
        }


# ---------------------------------------------------------------------------
# Suite F: Rounding (Decimal ROUND_HALF_UP, string boundary)
# ---------------------------------------------------------------------------


class TestSuiteFRounding:
    """F: integer half-up rounding via Decimal(str(...)); never round()."""

    def test_f01_exact_integer_product(self):
        """D/F-01: 50.0 WEIGHT_LOSS -> 80.0 -> 80."""
        result = _calc(50.0, ProteinGoal.WEIGHT_LOSS)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 80

    def test_f02_fractional_floor(self):
        """77.0 MAINTENANCE: 92.4 -> 92."""
        result = _calc(77.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 92

    def test_f03_fractional_ceiling(self):
        """85.5 WEIGHT_LOSS: 136.8 -> 137."""
        result = _calc(85.5, ProteinGoal.WEIGHT_LOSS)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 137

    def test_f04_half_up_boundary(self):
        """62.5 MAINTENANCE: 75.0 exactly -> 75; half-up not half-even."""
        result = _calc(62.5, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 75

    def test_half_up_not_bankers(self):
        """_round_protein_grams uses half-up, not Python round()."""
        # 2.5 -> half-up 3; Python round(2.5) == 2 (banker's)
        assert _round_protein_grams(2.5) == 3
        assert round(2.5) == 2  # documents the distinction

    def test_half_up_x_point_five(self):
        assert _round_protein_grams(0.5) == 1
        assert _round_protein_grams(1.5) == 2
        assert _round_protein_grams(3.5) == 4

    def test_round_down_below_half(self):
        assert _round_protein_grams(2.4) == 2
        assert _round_protein_grams(92.4) == 92
        assert _round_protein_grams(136.4) == 136

    def test_round_up_above_half(self):
        assert _round_protein_grams(2.6) == 3
        assert _round_protein_grams(136.8) == 137

    def test_string_decimal_boundary_used(self):
        """Rounding converts via str() before Decimal (policy Stage 2)."""
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        assert "Decimal(str(" in source
        assert "ROUND_HALF_UP" in source
        assert "quantize" in source

    def test_no_builtin_round_in_calculator(self):
        """No Python builtin round() for protein grams."""
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        # allow no round( at all in calculator
        assert "round(" not in source

    def test_worked_example_1(self):
        """Example 1: 70.0 MAINTENANCE -> 84."""
        assert _calc(70.0, ProteinGoal.MAINTENANCE).protein_g == 84

    def test_worked_example_2(self):
        """Example 2: 85.0 WEIGHT_LOSS -> 136."""
        assert _calc(85.0, ProteinGoal.WEIGHT_LOSS).protein_g == 136

    def test_worked_example_3(self):
        """Example 3: 85.5 WEIGHT_LOSS -> 137."""
        assert _calc(85.5, ProteinGoal.WEIGHT_LOSS).protein_g == 137


# ---------------------------------------------------------------------------
# Suite G: Output Contract / Nullability
# ---------------------------------------------------------------------------


class TestSuiteGOutputContract:
    """G: nullability rules, echoes, policy_version, issue emptiness."""

    def test_ok_implies_non_null_calculation(self):
        """status OK -> protein_g and factor non-null; issues empty."""
        result = _calc(70.0, ProteinGoal.MAINTENANCE)
        assert result.status == ProteinStatus.OK
        assert result.protein_g is not None
        assert result.protein_factor_g_per_kg is not None
        assert result.issues == ()

    @pytest.mark.parametrize(
        "weight,goal,expected_issues",
        [
            (None, ProteinGoal.MAINTENANCE, ProteinIssueCode.MISSING_WEIGHT),
            (70.0, None, ProteinIssueCode.MISSING_GOAL),
            (0.0, ProteinGoal.MAINTENANCE, ProteinIssueCode.INVALID_WEIGHT),
            (-1.0, ProteinGoal.MAINTENANCE, ProteinIssueCode.INVALID_WEIGHT),
            (
                float("nan"),
                ProteinGoal.MAINTENANCE,
                ProteinIssueCode.INVALID_WEIGHT,
            ),
            (0.4, ProteinGoal.MAINTENANCE, ProteinIssueCode.OUT_OF_RANGE_WEIGHT),
            (500.1, ProteinGoal.MAINTENANCE, ProteinIssueCode.OUT_OF_RANGE_WEIGHT),
        ],
    )
    def test_non_ok_nulls_calculation_fields(self, weight, goal, expected_issues):
        """status != OK -> protein_g and factor strictly None."""
        result = _calc(weight, goal)
        assert result.status != ProteinStatus.OK
        assert result.protein_g is None
        assert result.protein_factor_g_per_kg is None
        assert result.issues == (expected_issues,)

    def test_missing_goal_preserves_weight_echo(self):
        """Valid weight echoed when only goal is missing."""
        result = _calc(75.0, None)
        assert result.current_weight_kg == 75.0
        assert result.goal is None

    def test_missing_weight_preserves_goal_echo(self):
        """Valid goal echoed when only weight is missing."""
        result = _calc(None, ProteinGoal.WEIGHT_LOSS)
        assert result.current_weight_kg is None
        assert result.goal == ProteinGoal.WEIGHT_LOSS

    def test_invalid_weight_preserves_goal_echo(self):
        """Valid goal echoed when weight fails domain validation."""
        result = _calc(0.0, ProteinGoal.MUSCLE_GAIN)
        assert result.status == ProteinStatus.INVALID
        assert result.goal == ProteinGoal.MUSCLE_GAIN
        assert result.current_weight_kg == 0.0

    def test_policy_version_exact(self):
        """policy_version always equals 'protein-v1'."""
        assert PROTEIN_POLICY_VERSION == "protein-v1"
        for result in (
            _calc(70.0, ProteinGoal.MAINTENANCE),
            _calc(None, ProteinGoal.MAINTENANCE),
            _calc(0.0, ProteinGoal.MAINTENANCE),
        ):
            assert result.policy_version == "protein-v1"

    def test_status_enum_values(self):
        assert ProteinStatus.OK.value == "OK"
        assert ProteinStatus.INCOMPLETE.value == "INCOMPLETE"
        assert ProteinStatus.INVALID.value == "INVALID"
        assert ProteinStatus.ERROR.value == "ERROR"
        assert len(ProteinStatus) == 4
        assert not any(s.name == "REVIEW_REQUIRED" for s in ProteinStatus)

    def test_goal_enum_values_uppercase(self):
        assert ProteinGoal.MAINTENANCE.value == "MAINTENANCE"
        assert ProteinGoal.WEIGHT_LOSS.value == "WEIGHT_LOSS"
        assert ProteinGoal.WEIGHT_GAIN.value == "WEIGHT_GAIN"
        assert ProteinGoal.MUSCLE_GAIN.value == "MUSCLE_GAIN"

    def test_factors_locked(self):
        """Locked factor map matches policy."""
        assert GOAL_FACTORS == {
            ProteinGoal.MAINTENANCE: 1.2,
            ProteinGoal.WEIGHT_LOSS: 1.6,
            ProteinGoal.WEIGHT_GAIN: 1.6,
            ProteinGoal.MUSCLE_GAIN: 1.6,
        }
        assert PROTEIN_FACTOR_MAINTENANCE == 1.2
        assert PROTEIN_FACTOR_DEFAULT == 1.6
        assert get_protein_factor(ProteinGoal.MAINTENANCE) == 1.2
        assert get_protein_factor(ProteinGoal.MUSCLE_GAIN) == 1.6

    def test_weight_domain_constants(self):
        assert WEIGHT_DOMAIN_MIN_KG == 0.5
        assert WEIGHT_DOMAIN_MAX_KG == 500.0

    def test_ok_issues_always_empty_tuple(self):
        """Multiple OK calls all have issues == ()."""
        for goal in ProteinGoal:
            result = _calc(80.0, goal)
            assert result.status == ProteinStatus.OK
            assert result.issues == ()
            assert isinstance(result.issues, tuple)

    def test_protein_g_is_int_on_ok(self):
        """protein_g is a Python int (not float) on success."""
        result = _calc(70.0, ProteinGoal.MAINTENANCE)
        assert isinstance(result.protein_g, int)
        assert type(result.protein_g) is int


# ---------------------------------------------------------------------------
# Suite H: Immutability
# ---------------------------------------------------------------------------


class TestSuiteHImmutability:
    """H: frozen input/result; policy_version cannot be mutated."""

    def test_input_frozen(self):
        inp = _make_input()
        with pytest.raises(ValidationError):
            inp.current_weight_kg = 80.0

    def test_input_goal_frozen(self):
        inp = _make_input()
        with pytest.raises(ValidationError):
            inp.goal = ProteinGoal.WEIGHT_LOSS

    def test_result_frozen(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.status = ProteinStatus.ERROR

    def test_result_policy_version_immutable(self):
        result = _calc()
        assert result.policy_version == "protein-v1"
        with pytest.raises(ValidationError):
            result.policy_version = "tampered"

    def test_result_protein_g_immutable(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.protein_g = 999

    def test_result_factor_immutable(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.protein_factor_g_per_kg = 9.9

    def test_result_weight_echo_immutable(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.current_weight_kg = 1.0

    def test_result_goal_echo_immutable(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.goal = ProteinGoal.WEIGHT_GAIN

    def test_result_issues_immutable(self):
        result = _calc()
        with pytest.raises(ValidationError):
            result.issues = (ProteinIssueCode.INTERNAL_ERROR,)

    def test_result_issues_not_in_place_mutable(self):
        """Nested mutability hardening: issues is an immutable tuple.

        frozen=True alone does not stop result.issues.append(...) when
        the field is a list. Regression: in-place mutation must fail.
        """
        result = _calc(70.0, ProteinGoal.MAINTENANCE)
        assert isinstance(result.issues, tuple)
        assert result.issues == ()

        with pytest.raises(AttributeError):
            result.issues.append(ProteinIssueCode.INTERNAL_ERROR)  # type: ignore[attr-defined]

        with pytest.raises(AttributeError):
            result.issues.extend([ProteinIssueCode.MISSING_GOAL])  # type: ignore[attr-defined]

        with pytest.raises(AttributeError):
            result.issues.pop()  # type: ignore[attr-defined]

        with pytest.raises(AttributeError):
            result.issues.clear()  # type: ignore[attr-defined]

        # Failed mutation attempts leave issues unchanged
        assert result.issues == ()

        # Non-OK result also has immutable issues
        bad = _calc(0.0, ProteinGoal.MAINTENANCE)
        assert isinstance(bad.issues, tuple)
        with pytest.raises(AttributeError):
            bad.issues.append(ProteinIssueCode.INTERNAL_ERROR)  # type: ignore[attr-defined]
        assert bad.issues == (ProteinIssueCode.INVALID_WEIGHT,)

    def test_issues_rejects_list_under_strict(self):
        """strict=True on ProteinResult rejects list for tuple issues."""
        with pytest.raises(ValidationError):
            ProteinResult(
                status=ProteinStatus.INVALID,
                issues=[ProteinIssueCode.INVALID_WEIGHT],  # type: ignore[arg-type]
                policy_version="protein-v1",
            )

    def test_issue_codes_enum_frozen_by_enum(self):
        """Enum members are not reassigned via instance mutation."""
        assert ProteinIssueCode.MISSING_WEIGHT.value == "MISSING_WEIGHT"


# ---------------------------------------------------------------------------
# Suite I: Source Isolation / Determinism / No Medical Logic
# ---------------------------------------------------------------------------


class TestSuiteISourceIsolation:
    """I: pure Layer A — no LLM/net/db/clock/random/medical/upstream."""

    def test_no_llm_dependency(self):
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        for token in ("httpx", "httpcore", "telegram", "requests", "aiohttp"):
            assert token not in source

    def test_no_database_dependency(self):
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        for token in ("sqlite", "sqlalchemy", "postgres", "redis"):
            assert token not in source

    def test_no_clock_or_random(self):
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        assert "datetime.now" not in source
        assert "time.time" not in source
        assert "import random" not in source
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_no_upstream_recalculation(self):
        import app.nutrition.protein.calculator as mod

        source = inspect.getsource(mod)
        for token in (
            "ActivityClassifier",
            "RMRCalculator",
            "calculate_tdee",
            "calculate_calorie_target",
            "Mifflin",
            "Cunningham",
        ):
            assert token not in source

    def test_no_medical_fields_or_logic(self):
        """No renal/pregnancy/eGFR/eating-disorder fields or names."""
        import app.nutrition.protein.calculator as calc_mod
        import app.nutrition.protein.models as models_mod

        forbidden = (
            "diagnos",
            "disorder",
            "anorexia",
            "bulimia",
            "pregnan",
            "egfr",
            "renal",
            "hepatic",
            "liver",
            "pediatric",
            "lactat",
        )
        for mod in (calc_mod, models_mod):
            for name in dir(mod):
                lowered = name.lower()
                for fragment in forbidden:
                    assert fragment not in lowered, (mod.__name__, name)

        for field_name in list(ProteinInput.model_fields) + list(
            ProteinResult.model_fields
        ):
            lowered = field_name.lower()
            for fragment in forbidden:
                assert fragment not in lowered, field_name

    def test_no_body_composition_fields(self):
        """No FFM/LBM/InBody/DEXA/body-fat inputs in Layer A."""
        fields = set(ProteinInput.model_fields)
        assert fields == {"current_weight_kg", "goal"}

    def test_no_calorie_tdee_fields(self):
        fields = set(ProteinInput.model_fields)
        for forbidden in (
            "calories",
            "tdee",
            "rmr",
            "bmr",
            "activity",
            "target_weight",
        ):
            assert forbidden not in "".join(fields)

    def test_determinism_same_input_twice(self):
        inp = _make_input(85.5, ProteinGoal.WEIGHT_LOSS)
        a = calculate_protein(inp)
        b = calculate_protein(inp)
        assert a.model_dump() == b.model_dump()

    def test_determinism_100_invocations(self):
        inp = _make_input(77.3, ProteinGoal.MUSCLE_GAIN)
        results = [calculate_protein(inp) for _ in range(100)]
        first = results[0].model_dump()
        assert all(r.model_dump() == first for r in results)

    def test_input_not_mutated(self):
        inp = _make_input(70.0, ProteinGoal.MAINTENANCE)
        before = inp.model_dump()
        calculate_protein(inp)
        assert inp.model_dump() == before

    def test_calculate_returns_result_not_none(self):
        assert isinstance(_calc(), ProteinResult)

    def test_get_protein_factor_rejects_unknown(self):
        """Unknown goal raises ValueError — never returns a default factor."""
        with pytest.raises(ValueError, match="Unsupported goal"):
            get_protein_factor("BULK")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Suite J: Integration (GoalType adapter + NutritionTargets binding)
# ---------------------------------------------------------------------------


class TestSuiteJIntegration:
    """J: Layer B GoalType->ProteinGoal map and protein_g binding."""

    @pytest.mark.parametrize(
        "shared,expected",
        [
            (GoalType.MAINTENANCE, ProteinGoal.MAINTENANCE),
            (GoalType.WEIGHT_LOSS, ProteinGoal.WEIGHT_LOSS),
            (GoalType.WEIGHT_GAIN, ProteinGoal.WEIGHT_GAIN),
            (GoalType.MUSCLE_GAIN, ProteinGoal.MUSCLE_GAIN),
        ],
    )
    def test_goaltype_maps_1_to_1(self, shared, expected):
        assert map_goal_to_protein_goal(shared) is expected

    def test_muscle_gain_not_remapped_to_weight_gain(self):
        """MUSCLE_GAIN must map to ProteinGoal.MUSCLE_GAIN, not WEIGHT_GAIN."""
        mapped = map_goal_to_protein_goal(GoalType.MUSCLE_GAIN)
        assert mapped == ProteinGoal.MUSCLE_GAIN
        assert mapped != ProteinGoal.WEIGHT_GAIN

    def test_shared_goaltype_values_differ_from_protein_goal(self):
        """Shared GoalType lowercase values differ from ProteinGoal uppercase."""
        assert GoalType.MAINTENANCE.value == "maintenance"
        assert ProteinGoal.MAINTENANCE.value == "MAINTENANCE"

    def test_build_protein_input_from_goaltype(self):
        inp = build_protein_input(85.0, GoalType.WEIGHT_LOSS)
        assert inp.current_weight_kg == 85.0
        assert inp.goal == ProteinGoal.WEIGHT_LOSS
        result = calculate_protein(inp)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 136

    def test_build_protein_input_muscle_gain_goaltype(self):
        inp = build_protein_input(90.0, GoalType.MUSCLE_GAIN)
        assert inp.goal == ProteinGoal.MUSCLE_GAIN
        result = calculate_protein(inp)
        assert result.protein_g == 144
        assert result.protein_factor_g_per_kg == 1.6

    def test_build_protein_input_none_goal(self):
        inp = build_protein_input(70.0, None)
        assert inp.goal is None
        result = calculate_protein(inp)
        assert result.status == ProteinStatus.INCOMPLETE
        assert result.issues == (ProteinIssueCode.MISSING_GOAL,)

    def test_build_protein_input_none_weight(self):
        inp = build_protein_input(None, GoalType.MAINTENANCE)
        assert inp.current_weight_kg is None
        assert inp.goal == ProteinGoal.MAINTENANCE
        result = calculate_protein(inp)
        assert result.status == ProteinStatus.INCOMPLETE
        assert result.issues == (ProteinIssueCode.MISSING_WEIGHT,)

    def test_build_protein_input_passes_through_protein_goal(self):
        inp = build_protein_input(70.0, ProteinGoal.MAINTENANCE)
        assert inp.goal == ProteinGoal.MAINTENANCE

    def test_bind_protein_target_on_ok(self):
        """OK result binds protein_g into NutritionTargets."""
        result = _calc(70.0, ProteinGoal.MAINTENANCE)
        assert result.protein_g == 84
        targets = _make_targets(protein_g=0.0)
        bound = bind_protein_target(result, targets)
        assert bound.protein_g == 84.0
        # original unchanged (model_copy)
        assert targets.protein_g == 0.0

    def test_bind_protein_target_skipped_on_incomplete(self):
        """Non-OK (INCOMPLETE) does not bind — targets unchanged."""
        result = _calc(None, ProteinGoal.MAINTENANCE)
        targets = _make_targets(protein_g=160.0)
        bound = bind_protein_target(result, targets)
        assert bound.protein_g == 160.0

    def test_bind_protein_target_skipped_on_invalid(self):
        """Non-OK (INVALID) does not bind."""
        result = _calc(0.0, ProteinGoal.MAINTENANCE)
        targets = _make_targets(protein_g=160.0)
        bound = bind_protein_target(result, targets)
        assert bound.protein_g == 160.0

    def test_bind_protein_target_skipped_on_missing_goal(self):
        result = _calc(70.0, None)
        targets = _make_targets(protein_g=99.0)
        bound = bind_protein_target(result, targets)
        assert bound.protein_g == 99.0

    def test_end_to_end_goaltype_to_targets(self):
        """Full Layer B flow: GoalType -> ProteinInput -> Result -> Targets."""
        inp = build_protein_input(85.5, GoalType.WEIGHT_LOSS)
        result = calculate_protein(inp)
        assert result.status == ProteinStatus.OK
        assert result.protein_g == 137
        targets = bind_protein_target(result, _make_targets(protein_g=0.0))
        assert targets.protein_g == 137.0
        assert targets.policy_version == "nutrition-v1"

    def test_nutrition_targets_protein_g_field_exists(self):
        """NutritionTargets.protein_g is the binding target."""
        targets = _make_targets(protein_g=120.0)
        assert targets.protein_g == 120.0


# ---------------------------------------------------------------------------
# Extra: edge cases and ERROR path
# ---------------------------------------------------------------------------


class TestExtraEdgeCases:
    def test_all_goals_at_same_weight_factors(self):
        """Same weight: maintenance uses 1.2, others 1.6."""
        w = 80.0
        m = _calc(w, ProteinGoal.MAINTENANCE)
        l = _calc(w, ProteinGoal.WEIGHT_LOSS)
        g = _calc(w, ProteinGoal.WEIGHT_GAIN)
        mg = _calc(w, ProteinGoal.MUSCLE_GAIN)
        assert m.protein_g == 96  # 96.0
        assert l.protein_g == 128
        assert g.protein_g == 128
        assert mg.protein_g == 128

    def test_muscle_gain_equals_weight_gain_factor(self):
        """Policy: MUSCLE_GAIN and WEIGHT_GAIN both use 1.6 identically."""
        for w in (50.0, 70.0, 100.0, 150.0):
            wg = _calc(w, ProteinGoal.WEIGHT_GAIN)
            mg = _calc(w, ProteinGoal.MUSCLE_GAIN)
            assert wg.protein_factor_g_per_kg == mg.protein_factor_g_per_kg == 1.6
            assert wg.protein_g == mg.protein_g

    def test_result_on_error_path_construction(self):
        """Direct ERROR result construction is allowed (reserved path)."""
        result = ProteinResult(
            status=ProteinStatus.ERROR,
            issues=(ProteinIssueCode.INTERNAL_ERROR,),
            policy_version="protein-v1",
        )
        assert result.status == ProteinStatus.ERROR
        assert result.protein_g is None
        assert result.protein_factor_g_per_kg is None
        assert result.issues == (ProteinIssueCode.INTERNAL_ERROR,)

    def test_unsupported_goal_factor_raises(self):
        with pytest.raises(ValueError, match="Unsupported goal"):
            get_protein_factor(object())  # type: ignore[arg-type]

    def test_python_version_and_pydantic_config_used(self):
        """Sanity: models are Pydantic v2 BaseModel."""
        assert hasattr(ProteinInput, "model_config")
        assert hasattr(ProteinResult, "model_fields")
