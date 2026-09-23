"""Tests for Fat Calculator contracts and domain logic (fat-v1-rev1).

Layer A: Contract validation (strict Pydantic, no coercion)
Layer B: Calculator domain (calories domain, 25% formula, rounding,
         effective percentage precision, nullability)
Exact test matrix A–E from policy §Exact Test Matrix, plus Layer B
integration (GoalType adapter + target binding) and isolation suites.
"""

import inspect

import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.nutrition.models import AssessmentStatus, GoalType, NutritionTargets
from app.nutrition.fat import (
    ATWATER_FACTOR,
    FAT_ENERGY_FRACTION,
    FAT_POLICY_VERSION,
    FAT_FRACTION_DECIMAL,
    PERCENTAGE_QUANTUM,
    TARGET_CALORIES_DOMAIN_MIN,
    FatGoal,
    FatInput,
    FatIssueCode,
    FatResult,
    FatStatus,
    bind_fat_target,
    build_fat_input,
    calculate_fat,
    get_fat_energy_fraction,
    map_goal_to_fat_goal,
)
from app.nutrition.fat.calculator import (
    _quantize_effective_percentage,
    _round_fat_grams,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    target_calories: int | None = 2000,
    goal: FatGoal | None = FatGoal.MAINTENANCE,
) -> FatInput:
    return FatInput(target_calories=target_calories, goal=goal)


def _calc(
    target_calories: int | None = 2000,
    goal: FatGoal | None = FatGoal.MAINTENANCE,
) -> FatResult:
    return calculate_fat(_make_input(target_calories, goal))


def _make_targets(fat_g: float = 60.0) -> NutritionTargets:
    return NutritionTargets(
        calories_kcal=2200.0,
        protein_g=160.0,
        fat_g=fat_g,
        carbohydrates_g=250.0,
        status=AssessmentStatus.OK,
    )


# ---------------------------------------------------------------------------
# Policy Exact Test Matrix: Suite A — Standard calculations
# ---------------------------------------------------------------------------


class TestMatrixAStandard:
    """A-01..A-04 + B-09 + C-01..C-04 + E-01 happy/rounding rows."""

    def test_a01_standard_maintenance(self):
        """A-01: 2000 MAINTENANCE -> OK, 56g / 504 kcal / 0.252."""
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 56
        assert result.fat_calories == 504
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.252
        assert result.target_calories == 2000
        assert result.goal == FatGoal.MAINTENANCE
        assert result.policy_version == "fat-v1-rev1"

    def test_a02_standard_weight_loss(self):
        """A-02: 2330 WEIGHT_LOSS -> OK, 65g / 585 kcal / 0.251073."""
        result = _calc(2330, FatGoal.WEIGHT_LOSS)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 65
        assert result.fat_calories == 585
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.251073

    def test_a03_standard_weight_gain(self):
        """A-03: 2830 WEIGHT_GAIN -> OK, 79g / 711 kcal / 0.251237."""
        result = _calc(2830, FatGoal.WEIGHT_GAIN)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 79
        assert result.fat_calories == 711
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.251237

    def test_a04_standard_muscle_gain(self):
        """A-04: 2500 MUSCLE_GAIN -> OK, 69g / 621 kcal / 0.2484."""
        result = _calc(2500, FatGoal.MUSCLE_GAIN)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 69
        assert result.fat_calories == 621
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.2484

    def test_b09_extreme_hypercaloric(self):
        """B-09: 12000 -> OK, 333g / 2997 kcal / 0.24975."""
        result = _calc(12000, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 333
        assert result.fat_calories == 2997
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.24975

    def test_c01_exact_integer_boundary(self):
        """C-01: 1800 -> OK, 50g / 450 kcal / 0.25 exact."""
        result = _calc(1800, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 50
        assert result.fat_calories == 450
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.25

    def test_c02_rounding_floor(self):
        """C-02: 1814 -> 50.388.. floors to 50; 450/1814 -> 0.248071."""
        result = _calc(1814, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 50
        assert result.fat_calories == 450
        assert result.effective_fat_percentage == 0.248071

    def test_c03_rounding_half_up(self):
        """C-03: 1818 -> exactly 50.5 -> half-up 51; 459/1818 -> 0.252475."""
        result = _calc(1818, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 51
        assert result.fat_calories == 459
        assert result.effective_fat_percentage == 0.252475

    def test_c04_rounding_ceiling(self):
        """C-04: 1822 -> 50.611.. ceils to 51; 459/1822 -> 0.251921."""
        result = _calc(1822, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 51
        assert result.fat_calories == 459
        assert result.effective_fat_percentage == 0.251921

    def test_e01_low_calorie(self):
        """E-01: 1000 WEIGHT_LOSS -> OK, 28g / 252 kcal / 0.252."""
        result = _calc(1000, FatGoal.WEIGHT_LOSS)
        assert result.status == FatStatus.OK
        assert result.issues == ()
        assert result.fat_g == 28
        assert result.fat_calories == 252
        assert result.target_fat_percentage == 0.25
        assert result.effective_fat_percentage == 0.252


# ---------------------------------------------------------------------------
# Matrix: Suite B — Calorie validation (domain)
# ---------------------------------------------------------------------------


class TestMatrixBCalorieValidation:
    """B-01..B-08: missing/zero/negative and schema rejections."""

    def test_b01_missing_calories(self):
        """B-01: None + MAINTENANCE -> INCOMPLETE / MISSING_TARGET_CALORIES."""
        result = _calc(None, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.INCOMPLETE
        assert result.issues == (FatIssueCode.MISSING_TARGET_CALORIES,)
        assert result.fat_g is None
        assert result.fat_calories is None
        assert result.target_fat_percentage is None
        assert result.effective_fat_percentage is None
        assert result.target_calories is None
        assert result.goal == FatGoal.MAINTENANCE

    def test_b02_zero_calories(self):
        """B-02: 0 -> INVALID / OUT_OF_RANGE_TARGET_CALORIES."""
        result = _calc(0, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.INVALID
        assert result.issues == (FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES,)
        assert result.fat_g is None
        assert result.fat_calories is None
        assert result.target_fat_percentage is None
        assert result.effective_fat_percentage is None
        assert result.target_calories is None  # not domain-valid
        assert result.goal == FatGoal.MAINTENANCE

    def test_b03_negative_calories(self):
        """B-03: -2000 -> INVALID / OUT_OF_RANGE_TARGET_CALORIES."""
        result = _calc(-2000, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.INVALID
        assert result.issues == (FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES,)
        assert result.fat_g is None
        assert result.target_calories is None
        assert result.goal == FatGoal.MAINTENANCE

    def test_b04_string_calories_schema(self):
        """B-04: '2000' rejected at strict schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories="2000", goal=FatGoal.MAINTENANCE)

    def test_b05_boolean_calories_schema(self):
        """B-05: True rejected at strict schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=True, goal=FatGoal.MAINTENANCE)

    def test_b06_float_calories_schema(self):
        """B-06: 2000.0 rejected at strict schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=2000.0, goal=FatGoal.MAINTENANCE)

    def test_b07_nan_calories_schema(self):
        """B-07: NaN (float) rejected at strict int schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=float("nan"), goal=FatGoal.MAINTENANCE)

    def test_b08_pos_inf_calories_schema(self):
        """B-08: +Infinity rejected at strict int schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=float("inf"), goal=FatGoal.MAINTENANCE)

    def test_b08_neg_inf_calories_schema(self):
        """B-08b: -Infinity rejected at strict int schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=float("-inf"), goal=FatGoal.MAINTENANCE)

    def test_domain_min_boundary_one(self):
        """target_calories == 1 is the lower domain boundary (valid)."""
        result = _calc(1, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.target_calories == 1

    def test_domain_below_min_rejected(self):
        """target_calories == 0 is out of domain (>= 1 required)."""
        assert TARGET_CALORIES_DOMAIN_MIN == 1
        result = _calc(0, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.INVALID


# ---------------------------------------------------------------------------
# Matrix: Suite D — Goal validation
# ---------------------------------------------------------------------------


class TestMatrixDGoalValidation:
    """D-01..D-03: missing/unsupported/lowercase goal."""

    def test_d01_missing_goal(self):
        """D-01: 2000 + None -> INCOMPLETE / MISSING_GOAL."""
        result = _calc(2000, None)
        assert result.status == FatStatus.INCOMPLETE
        assert result.issues == (FatIssueCode.MISSING_GOAL,)
        assert result.fat_g is None
        assert result.fat_calories is None
        assert result.target_fat_percentage is None
        assert result.effective_fat_percentage is None
        assert result.target_calories == 2000  # domain-valid echo
        assert result.goal is None

    def test_d02_unsupported_goal_string_schema(self):
        """D-02: 'KETO' rejected at strict schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=2000, goal="KETO")

    def test_d03_lowercase_goal_string_schema(self):
        """D-03: 'maintenance' rejected at strict schema -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=2000, goal="maintenance")

    def test_missing_both_calories_first(self):
        """Both missing -> first failure is MISSING_TARGET_CALORIES."""
        result = _calc(None, None)
        assert result.status == FatStatus.INCOMPLETE
        assert result.issues == (FatIssueCode.MISSING_TARGET_CALORIES,)
        assert result.fat_g is None

    def test_all_four_goals_accepted(self):
        """All four FatGoal members are accepted at schema level."""
        for goal in (
            FatGoal.MAINTENANCE,
            FatGoal.WEIGHT_LOSS,
            FatGoal.WEIGHT_GAIN,
            FatGoal.MUSCLE_GAIN,
        ):
            inp = FatInput(target_calories=2000, goal=goal)
            assert inp.goal == goal

    def test_bypass_unsupported_goal_raises_value_error(self):
        """model_construct bypass with bad goal -> ValueError, never OK."""
        bypass = FatInput.model_construct(
            target_calories=2000,
            goal="KETO",
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_fat(bypass)

    def test_bypass_lowercase_goal_raises_value_error(self):
        """Bypass with lowercase 'maintenance' -> ValueError (case-sensitive)."""
        bypass = FatInput.model_construct(
            target_calories=2000,
            goal="maintenance",
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_fat(bypass)

    def test_bypass_shared_goaltype_raises_value_error(self):
        """Shared GoalType must not enter Layer A without adapter mapping."""
        bypass = FatInput.model_construct(
            target_calories=2000,
            goal=GoalType.MUSCLE_GAIN,
        )
        with pytest.raises(ValueError, match="Unsupported goal"):
            calculate_fat(bypass)

    def test_bypass_never_falls_through(self):
        """Regression: bad goal never returns OK."""
        bypass = FatInput.model_construct(
            target_calories=2000,
            goal="KETO",
        )
        with pytest.raises(ValueError):
            calculate_fat(bypass)


# ---------------------------------------------------------------------------
# Matrix: Suite E — Extra fields / immutability / schema
# ---------------------------------------------------------------------------


class TestMatrixESchemaAndImmutability:
    """E-02..E-04: extra forbid, frozen result, tuple issues."""

    def test_e02_extra_fields_input(self):
        """E-02: unknown key rejected (extra='forbid') -> ValidationError."""
        with pytest.raises(ValidationError):
            FatInput(
                target_calories=2000,
                goal=FatGoal.MAINTENANCE,
                protein_g=120,
            )

    def test_e03_frozen_result_mutation(self):
        """E-03: assignment on FatResult raises ValidationError."""
        result = _calc(2000, FatGoal.MAINTENANCE)
        with pytest.raises(ValidationError):
            result.status = FatStatus.ERROR
        with pytest.raises(ValidationError):
            result.fat_g = 999
        with pytest.raises(ValidationError):
            result.policy_version = "tampered"
        with pytest.raises(ValidationError):
            result.effective_fat_percentage = 1.0
        with pytest.raises(ValidationError):
            result.issues = (FatIssueCode.INTERNAL_ERROR,)

    def test_e04_tuple_issues_immutability(self):
        """E-04: issues is a tuple; append raises AttributeError."""
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert isinstance(result.issues, tuple)
        assert result.issues == ()
        with pytest.raises(AttributeError):
            result.issues.append(FatIssueCode.INTERNAL_ERROR)  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.extend([FatIssueCode.MISSING_GOAL])  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.pop()  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.clear()  # type: ignore[attr-defined]
        assert result.issues == ()

        bad = _calc(0, FatGoal.MAINTENANCE)
        assert isinstance(bad.issues, tuple)
        with pytest.raises(AttributeError):
            bad.issues.append(FatIssueCode.INTERNAL_ERROR)  # type: ignore[attr-defined]
        assert bad.issues == (FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES,)

    def test_issues_rejects_list_under_strict(self):
        """strict=True on FatResult rejects list for tuple issues."""
        with pytest.raises(ValidationError):
            FatResult(
                status=FatStatus.INVALID,
                issues=[FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES],  # type: ignore[arg-type]
                policy_version="fat-v1-rev1",
            )

    def test_input_frozen(self):
        inp = _make_input()
        with pytest.raises(ValidationError):
            inp.target_calories = 1800
        with pytest.raises(ValidationError):
            inp.goal = FatGoal.WEIGHT_LOSS

    def test_input_config_strict_frozen_forbid(self):
        config = FatInput.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_result_config_strict_frozen_forbid(self):
        config = FatResult.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_result_rejects_string_status(self):
        with pytest.raises(ValidationError):
            FatResult(status="ok")

    def test_result_rejects_float_fat_g_strict(self):
        """fat_g must be int under strict=True."""
        with pytest.raises(ValidationError):
            FatResult(
                status=FatStatus.OK,
                fat_g=56.0,
                fat_calories=504,
                target_fat_percentage=0.25,
                effective_fat_percentage=0.252,
            )

    def test_shared_goaltype_rejected_at_schema(self):
        """GoalType members do not match FatGoal values (adapter required)."""
        with pytest.raises(ValidationError):
            FatInput(target_calories=2000, goal=GoalType.MAINTENANCE)

    def test_missing_both_fields_defaults_none(self):
        inp = FatInput()
        assert inp.target_calories is None
        assert inp.goal is None


# ---------------------------------------------------------------------------
# Rounding / precision (Decimal ROUND_HALF_UP, 6-dp contract)
# ---------------------------------------------------------------------------


class TestRoundingAndPrecision:
    def test_half_up_not_bankers(self):
        """_round_fat_grams uses half-up, not Python round()."""
        assert _round_fat_grams(2.5) == 3
        assert round(2.5) == 2  # documents the distinction
        assert _round_fat_grams(50.5) == 51
        assert _round_fat_grams(50.4) == 50
        assert _round_fat_grams(50.6) == 51

    def test_half_up_point_five(self):
        assert _round_fat_grams(0.5) == 1
        assert _round_fat_grams(1.5) == 2
        assert _round_fat_grams(3.5) == 4

    def test_string_decimal_boundary_used(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        assert "Decimal(str(" in source
        assert "ROUND_HALF_UP" in source
        assert "quantize" in source

    def test_no_builtin_round_in_calculator(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        assert "round(" not in source

    def test_percentage_quantum_six_decimals(self):
        assert PERCENTAGE_QUANTUM == "0.000001"
        assert Decimal(PERCENTAGE_QUANTUM) == Decimal("0.000001")

    def test_effective_percentage_quantize_contract(self):
        """Stage 5: exact division -> quantize 0.000001 HALF_UP -> float."""
        # 504/2000 = 0.252 exactly
        assert _quantize_effective_percentage(504, 2000) == 0.252
        # 585/2330 = 0.251072961... -> 0.251073
        assert _quantize_effective_percentage(585, 2330) == 0.251073
        # 621/2500 = 0.2484 exactly (trailing zero drop)
        assert _quantize_effective_percentage(621, 2500) == 0.2484
        # half-up at 6th decimal: 0.1234565 -> 0.123457
        assert _quantize_effective_percentage(1234565, 10000000) == 0.123457

    def test_effective_percentage_is_float(self):
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert isinstance(result.effective_fat_percentage, float)

    def test_effective_percentage_at_most_six_decimals(self):
        for calories in (1000, 1814, 1818, 1822, 2000, 2330, 2830, 12000):
            result = _calc(calories, FatGoal.MAINTENANCE)
            assert result.status == FatStatus.OK
            quantized = Decimal(str(result.effective_fat_percentage)).quantize(
                Decimal("0.000001")
            )
            assert Decimal(str(result.effective_fat_percentage)) == quantized


# ---------------------------------------------------------------------------
# Output contract / nullability / constants
# ---------------------------------------------------------------------------


class TestOutputContract:
    def test_ok_implies_non_null_calculation(self):
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert result.status == FatStatus.OK
        assert result.fat_g is not None
        assert result.fat_calories is not None
        assert result.target_fat_percentage is not None
        assert result.effective_fat_percentage is not None
        assert result.issues == ()

    @pytest.mark.parametrize(
        "calories,goal,expected_issues",
        [
            (None, FatGoal.MAINTENANCE, FatIssueCode.MISSING_TARGET_CALORIES),
            (2000, None, FatIssueCode.MISSING_GOAL),
            (0, FatGoal.MAINTENANCE, FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES),
            (
                -2000,
                FatGoal.MAINTENANCE,
                FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES,
            ),
        ],
    )
    def test_non_ok_nulls_calculation_fields(self, calories, goal, expected_issues):
        result = _calc(calories, goal)
        assert result.status != FatStatus.OK
        assert result.fat_g is None
        assert result.fat_calories is None
        assert result.target_fat_percentage is None
        assert result.effective_fat_percentage is None
        assert result.issues == (expected_issues,)

    def test_policy_version_exact(self):
        assert FAT_POLICY_VERSION == "fat-v1-rev1"
        for result in (
            _calc(2000, FatGoal.MAINTENANCE),
            _calc(None, FatGoal.MAINTENANCE),
            _calc(0, FatGoal.MAINTENANCE),
        ):
            assert result.policy_version == "fat-v1-rev1"

    def test_status_enum_values(self):
        assert FatStatus.OK.value == "OK"
        assert FatStatus.INCOMPLETE.value == "INCOMPLETE"
        assert FatStatus.INVALID.value == "INVALID"
        assert FatStatus.ERROR.value == "ERROR"
        assert len(FatStatus) == 4
        assert not any(s.name == "REVIEW_REQUIRED" for s in FatStatus)

    def test_goal_enum_values_uppercase(self):
        assert FatGoal.MAINTENANCE.value == "MAINTENANCE"
        assert FatGoal.WEIGHT_LOSS.value == "WEIGHT_LOSS"
        assert FatGoal.WEIGHT_GAIN.value == "WEIGHT_GAIN"
        assert FatGoal.MUSCLE_GAIN.value == "MUSCLE_GAIN"

    def test_issue_codes_exact_set(self):
        """Only the six policy operational issue codes exist."""
        assert {c.name for c in FatIssueCode} == {
            "MISSING_TARGET_CALORIES",
            "INVALID_TARGET_CALORIES",
            "OUT_OF_RANGE_TARGET_CALORIES",
            "MISSING_GOAL",
            "UNSUPPORTED_GOAL",
            "INTERNAL_ERROR",
        }

    def test_goal_invariance_constants(self):
        assert FAT_ENERGY_FRACTION == 0.25
        assert FAT_FRACTION_DECIMAL == Decimal("0.25")
        assert ATWATER_FACTOR == 9.0
        for goal in FatGoal:
            assert get_fat_energy_fraction(goal) == Decimal("0.25")

    def test_get_fat_energy_fraction_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unsupported goal"):
            get_fat_energy_fraction("KETO")  # type: ignore[arg-type]

    def test_goal_invariance_same_output_across_goals(self):
        """Same calories across all four goals -> identical fat outputs."""
        for calories in (1000, 1800, 2000, 2500, 2830):
            results = [_calc(calories, g) for g in FatGoal]
            first = results[0]
            for r in results:
                assert r.status == FatStatus.OK
                assert r.fat_g == first.fat_g
                assert r.fat_calories == first.fat_calories
                assert (
                    r.effective_fat_percentage == first.effective_fat_percentage
                )
                assert r.target_fat_percentage == 0.25

    def test_ok_issues_always_empty_tuple(self):
        for goal in FatGoal:
            result = _calc(1800, goal)
            assert result.status == FatStatus.OK
            assert result.issues == ()
            assert isinstance(result.issues, tuple)

    def test_fat_g_is_int_on_ok(self):
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert type(result.fat_g) is int
        assert type(result.fat_calories) is int

    def test_fat_calories_equals_fat_g_times_nine(self):
        """Stage 4 internal consistency: fat_calories = fat_g * 9."""
        for calories in (1000, 1814, 1818, 1822, 2000, 2330, 12000):
            result = _calc(calories, FatGoal.MAINTENANCE)
            assert result.fat_calories == result.fat_g * 9

    def test_result_on_error_path_construction(self):
        """Direct ERROR result construction is allowed (reserved path)."""
        result = FatResult(
            status=FatStatus.ERROR,
            issues=(FatIssueCode.INTERNAL_ERROR,),
            policy_version="fat-v1-rev1",
        )
        assert result.status == FatStatus.ERROR
        assert result.fat_g is None
        assert result.issues == (FatIssueCode.INTERNAL_ERROR,)

    def test_result_rejects_non_tuple_issues_list(self):
        with pytest.raises(ValidationError):
            FatResult(
                status=FatStatus.OK,
                issues=[],
                policy_version="fat-v1-rev1",
            )


# ---------------------------------------------------------------------------
# Source isolation / determinism / no medical logic
# ---------------------------------------------------------------------------


class TestSourceIsolation:
    def test_no_llm_dependency(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        for token in ("httpx", "httpcore", "telegram", "requests", "aiohttp"):
            assert token not in source

    def test_no_database_dependency(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        for token in ("sqlite", "sqlalchemy", "postgres", "redis"):
            assert token not in source

    def test_no_clock_or_random(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        assert "datetime.now" not in source
        assert "time.time" not in source
        assert "import random" not in source
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_no_upstream_recalculation(self):
        import app.nutrition.fat.calculator as mod

        source = inspect.getsource(mod)
        for token in (
            "ActivityClassifier",
            "RMRCalculator",
            "calculate_tdee",
            "calculate_calorie_target",
            "Mifflin",
            "Cunningham",
            "calculate_protein",
            "ProteinResult",
        ):
            assert token not in source

    def test_no_medical_fields_or_logic(self):
        import app.nutrition.fat.calculator as calc_mod
        import app.nutrition.fat.models as models_mod

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
            "pancreat",
            "gallbladder",
            "lipid",
            "malabsorp",
        )
        for mod in (calc_mod, models_mod):
            for name in dir(mod):
                lowered = name.lower()
                for fragment in forbidden:
                    assert fragment not in lowered, (mod.__name__, name)

        for field_name in list(FatInput.model_fields) + list(
            FatResult.model_fields
        ):
            lowered = field_name.lower()
            for fragment in forbidden:
                assert fragment not in lowered, field_name

    def test_no_body_weight_floor(self):
        """No g/kg minimum or body-weight scaling in Layer A."""
        import ast

        import app.nutrition.fat.calculator as mod

        tree = ast.parse(inspect.getsource(mod))
        identifiers = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        identifiers |= {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        identifiers |= {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        for token in ("BODY_WEIGHT", "MIN_FAT", "FAT_FLOOR"):
            assert token not in identifiers
        assert set(FatInput.model_fields) == {"target_calories", "goal"}

    def test_no_cross_macronutrient_fields(self):
        fields = set(FatInput.model_fields)
        for forbidden in ("protein", "carbohydrate", "carb", "fiber"):
            assert forbidden not in "".join(fields)

    def test_determinism_same_input_twice(self):
        inp = _make_input(2330, FatGoal.WEIGHT_LOSS)
        a = calculate_fat(inp)
        b = calculate_fat(inp)
        assert a.model_dump() == b.model_dump()

    def test_determinism_100_invocations(self):
        inp = _make_input(1814, FatGoal.MUSCLE_GAIN)
        results = [calculate_fat(inp) for _ in range(100)]
        first = results[0].model_dump()
        assert all(r.model_dump() == first for r in results)

    def test_input_not_mutated(self):
        inp = _make_input(2000, FatGoal.MAINTENANCE)
        before = inp.model_dump()
        calculate_fat(inp)
        assert inp.model_dump() == before

    def test_calculate_returns_result_not_none(self):
        assert isinstance(_calc(), FatResult)


# ---------------------------------------------------------------------------
# Layer B integration (GoalType adapter + NutritionTargets binding)
# ---------------------------------------------------------------------------


class TestLayerBIntegration:
    @pytest.mark.parametrize(
        "shared,expected",
        [
            (GoalType.MAINTENANCE, FatGoal.MAINTENANCE),
            (GoalType.WEIGHT_LOSS, FatGoal.WEIGHT_LOSS),
            (GoalType.WEIGHT_GAIN, FatGoal.WEIGHT_GAIN),
            (GoalType.MUSCLE_GAIN, FatGoal.MUSCLE_GAIN),
        ],
    )
    def test_goaltype_maps_1_to_1(self, shared, expected):
        assert map_goal_to_fat_goal(shared) is expected

    def test_muscle_gain_not_remapped_to_weight_gain(self):
        mapped = map_goal_to_fat_goal(GoalType.MUSCLE_GAIN)
        assert mapped == FatGoal.MUSCLE_GAIN
        assert mapped != FatGoal.WEIGHT_GAIN

    def test_shared_goaltype_values_differ_from_fat_goal(self):
        assert GoalType.MAINTENANCE.value == "maintenance"
        assert FatGoal.MAINTENANCE.value == "MAINTENANCE"

    def test_build_fat_input_from_goaltype(self):
        inp = build_fat_input(2000, GoalType.MAINTENANCE)
        assert inp.target_calories == 2000
        assert inp.goal == FatGoal.MAINTENANCE
        result = calculate_fat(inp)
        assert result.status == FatStatus.OK
        assert result.fat_g == 56

    def test_build_fat_input_none_goal(self):
        inp = build_fat_input(2000, None)
        assert inp.goal is None
        result = calculate_fat(inp)
        assert result.status == FatStatus.INCOMPLETE
        assert result.issues == (FatIssueCode.MISSING_GOAL,)

    def test_build_fat_input_none_calories(self):
        inp = build_fat_input(None, GoalType.MAINTENANCE)
        assert inp.target_calories is None
        assert inp.goal == FatGoal.MAINTENANCE
        result = calculate_fat(inp)
        assert result.status == FatStatus.INCOMPLETE
        assert result.issues == (FatIssueCode.MISSING_TARGET_CALORIES,)

    def test_build_fat_input_passes_through_fat_goal(self):
        inp = build_fat_input(2000, FatGoal.WEIGHT_LOSS)
        assert inp.goal == FatGoal.WEIGHT_LOSS

    def test_bind_fat_target_on_ok(self):
        result = _calc(2000, FatGoal.MAINTENANCE)
        assert result.fat_g == 56
        targets = _make_targets(fat_g=0.0)
        bound = bind_fat_target(result, targets)
        assert bound.fat_g == 56.0
        assert targets.fat_g == 0.0  # original unchanged (model_copy)

    def test_bind_fat_target_skipped_on_incomplete(self):
        result = _calc(None, FatGoal.MAINTENANCE)
        targets = _make_targets(fat_g=60.0)
        bound = bind_fat_target(result, targets)
        assert bound.fat_g == 60.0

    def test_bind_fat_target_skipped_on_invalid(self):
        result = _calc(0, FatGoal.MAINTENANCE)
        targets = _make_targets(fat_g=60.0)
        bound = bind_fat_target(result, targets)
        assert bound.fat_g == 60.0

    def test_bind_fat_target_skipped_on_missing_goal(self):
        result = _calc(2000, None)
        targets = _make_targets(fat_g=45.0)
        bound = bind_fat_target(result, targets)
        assert bound.fat_g == 45.0

    def test_end_to_end_goaltype_to_targets(self):
        inp = build_fat_input(2330, GoalType.WEIGHT_LOSS)
        result = calculate_fat(inp)
        assert result.status == FatStatus.OK
        assert result.fat_g == 65
        targets = bind_fat_target(result, _make_targets(fat_g=0.0))
        assert targets.fat_g == 65.0
        assert targets.policy_version == "nutrition-v1"

    def test_nutrition_targets_fat_g_field_exists(self):
        targets = _make_targets(fat_g=50.0)
        assert targets.fat_g == 50.0
