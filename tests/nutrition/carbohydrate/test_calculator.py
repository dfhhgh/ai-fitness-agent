"""Tests for Carbohydrate Calculator contracts and domain logic (carb-v1).

Layer A: Contract validation (strict Pydantic, no coercion)
Domain: Residual-macro calculation, rounding, nullability
Boundary: Zero/negative residual, large values, all-zero inputs
Isolation: No LLM, no network, no database, no clock, no randomness,
           no fiber subtraction, no 130g floor, no AMDR, no fat_g
"""

import inspect

import pytest
from pydantic import ValidationError

from app.nutrition.carbohydrate import (
    CARB_KCAL_PER_G,
    CARB_POLICY_VERSION,
    PROTEIN_KCAL_PER_G,
    CarbInput,
    CarbIssueCode,
    CarbResult,
    CarbStatus,
    calculate_carbohydrates,
)
from app.nutrition.carbohydrate.calculator import _round_carb_grams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _calc(
    target_calories: int = 2000,
    protein_g: int = 150,
    fat_calories: int = 504,
) -> CarbResult:
    return calculate_carbohydrates(
        CarbInput(
            target_calories=target_calories,
            protein_g=protein_g,
            fat_calories=fat_calories,
        )
    )


# ---------------------------------------------------------------------------
# 1. Normal positive residual
# ---------------------------------------------------------------------------


class TestPositiveResidual:
    def test_standard_positive_residual(self):
        """2000 - (150*4) - 504 = 896 → 224g / 896 kcal."""
        result = _calc(2000, 150, 504)
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 224
        assert result.carbohydrate_calories == 896
        assert result.residual_calories == 896
        assert result.issues == ()
        assert result.policy_version == "carb-v1"

    def test_another_positive_residual(self):
        """2500 - (180*4) - 621 = 1159 → 290g / 1160 kcal."""
        result = _calc(2500, 180, 621)
        assert result.status == CarbStatus.OK
        # 1159 / 4 = 289.75 → ROUND_HALF_UP → 290
        assert result.carbohydrates_g == 290
        assert result.carbohydrate_calories == 1160
        assert result.residual_calories == 1159
        assert result.issues == ()

    def test_residual_one_calorie(self):
        """Smallest positive residual: 1 kcal → 0g (1/4 = 0.25 rounds to 0)."""
        result = _calc(target_calories=1, protein_g=0, fat_calories=0)
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 0
        assert result.carbohydrate_calories == 0
        assert result.residual_calories == 1

    def test_residual_two_calories(self):
        """2 kcal residual → 2/4 = 0.5 → ROUND_HALF_UP → 1g."""
        result = _calc(target_calories=2, protein_g=0, fat_calories=0)
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 1
        assert result.carbohydrate_calories == 4
        assert result.residual_calories == 2


# ---------------------------------------------------------------------------
# 2. Zero residual
# ---------------------------------------------------------------------------


class TestZeroResidual:
    def test_zero_residual_exact(self):
        """target=2000, protein=200 (800kcal), fat=1200 → residual=0."""
        result = _calc(
            target_calories=2000,
            protein_g=200,
            fat_calories=1200,
        )
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 0
        assert result.carbohydrate_calories == 0
        assert result.residual_calories == 0
        assert result.issues == ()


# ---------------------------------------------------------------------------
# 3. Negative residual
# ---------------------------------------------------------------------------


class TestNegativeResidual:
    def test_negative_residual_basic(self):
        """2000 - (150*4) - 1450 = -50 → INVALID."""
        result = _calc(
            target_calories=2000,
            protein_g=150,
            fat_calories=1450,
        )
        assert result.status == CarbStatus.INVALID
        assert result.carbohydrates_g is None
        assert result.carbohydrate_calories is None
        assert result.residual_calories == -50
        assert result.issues == (CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL,)
        assert result.policy_version == "carb-v1"

    def test_negative_residual_preserved_exactly(self):
        """The exact negative value must be preserved, never clamped to 0."""
        result = _calc(
            target_calories=1000,
            protein_g=200,
            fat_calories=500,
        )
        # 1000 - 800 - 500 = -300
        assert result.residual_calories == -300
        assert result.status == CarbStatus.INVALID

    def test_negative_residual_large(self):
        """Large negative residual preserves exact value."""
        result = _calc(
            target_calories=100,
            protein_g=500,
            fat_calories=9000,
        )
        # 100 - 2000 - 9000 = -10900
        assert result.residual_calories == -10900
        assert result.status == CarbStatus.INVALID
        assert result.carbohydrates_g is None
        assert result.carbohydrate_calories is None


# ---------------------------------------------------------------------------
# 4. All-zero inputs
# ---------------------------------------------------------------------------


class TestAllZeroInputs:
    def test_all_zeros_ok(self):
        """target=0, protein=0, fat=0 → OK, carbs=0, residual=0."""
        result = _calc(
            target_calories=0,
            protein_g=0,
            fat_calories=0,
        )
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 0
        assert result.carbohydrate_calories == 0
        assert result.residual_calories == 0
        assert result.issues == ()


# ---------------------------------------------------------------------------
# 5. target_calories=0 with non-zero macros
# ---------------------------------------------------------------------------


class TestZeroTargetWithMacros:
    def test_zero_target_one_protein(self):
        """target=0, protein=1, fat=0 → INVALID, residual=-4."""
        result = _calc(
            target_calories=0,
            protein_g=1,
            fat_calories=0,
        )
        assert result.status == CarbStatus.INVALID
        assert result.residual_calories == -4
        assert result.carbohydrates_g is None
        assert result.carbohydrate_calories is None
        assert result.issues == (CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL,)

    def test_zero_target_nonzero_fat(self):
        """target=0, protein=0, fat=1 → INVALID, residual=-1."""
        result = _calc(
            target_calories=0,
            protein_g=0,
            fat_calories=1,
        )
        assert result.status == CarbStatus.INVALID
        assert result.residual_calories == -1


# ---------------------------------------------------------------------------
# 6. Pydantic schema rejection — negative values
# ---------------------------------------------------------------------------


class TestNegativeInputRejection:
    def test_negative_target_calories(self):
        """target_calories=-1 → ValidationError (ge=0)."""
        with pytest.raises(ValidationError):
            CarbInput(target_calories=-1, protein_g=0, fat_calories=0)

    def test_negative_protein_g(self):
        """protein_g=-1 → ValidationError (ge=0)."""
        with pytest.raises(ValidationError):
            CarbInput(target_calories=2000, protein_g=-1, fat_calories=0)

    def test_negative_fat_calories(self):
        """fat_calories=-1 → ValidationError (ge=0)."""
        with pytest.raises(ValidationError):
            CarbInput(target_calories=2000, protein_g=0, fat_calories=-1)


# ---------------------------------------------------------------------------
# 7–9. Missing/extra field rejections
# ---------------------------------------------------------------------------


class TestMissingAndExtraFields:
    def test_missing_target_calories(self):
        with pytest.raises(ValidationError):
            CarbInput(protein_g=100, fat_calories=500)  # type: ignore[call-arg]

    def test_missing_protein_g(self):
        with pytest.raises(ValidationError):
            CarbInput(target_calories=2000, fat_calories=500)  # type: ignore[call-arg]

    def test_missing_fat_calories(self):
        with pytest.raises(ValidationError):
            CarbInput(target_calories=2000, protein_g=100)  # type: ignore[call-arg]

    def test_missing_all_fields(self):
        with pytest.raises(ValidationError):
            CarbInput()  # type: ignore[call-arg]

    def test_extra_field_rejected(self):
        """extra='forbid' rejects unknown keys."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g=100,
                fat_calories=500,
                fiber_g=25,
            )

    def test_fat_g_extra_field_rejected(self):
        """fat_g is explicitly not a field — extra='forbid' rejects it."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g=100,
                fat_calories=500,
                fat_g=55,
            )


# ---------------------------------------------------------------------------
# 10–12. Strict type enforcement — wrong types / coercion / bool
# ---------------------------------------------------------------------------


class TestStrictTypeEnforcement:
    def test_string_target_calories_rejected(self):
        """strict=True rejects string → int coercion."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories="2000",  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )

    def test_float_target_calories_rejected(self):
        """strict=True rejects float → int coercion."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000.0,  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )

    def test_bool_target_calories_rejected(self):
        """strict=True rejects bool even though bool is subclass of int."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=True,  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )

    def test_bool_false_target_calories_rejected(self):
        """False is also a bool and must be rejected."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=False,  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )

    def test_bool_protein_g_rejected(self):
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g=True,  # type: ignore[arg-type]
                fat_calories=500,
            )

    def test_bool_fat_calories_rejected(self):
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g=100,
                fat_calories=True,  # type: ignore[arg-type]
            )

    def test_string_protein_g_rejected(self):
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g="100",  # type: ignore[arg-type]
                fat_calories=500,
            )

    def test_float_protein_g_rejected(self):
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=2000,
                protein_g=100.5,  # type: ignore[arg-type]
                fat_calories=500,
            )

    def test_list_target_calories_rejected(self):
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=[2000],  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )

    def test_none_target_calories_rejected(self):
        """None is not valid for required int field with ge=0."""
        with pytest.raises(ValidationError):
            CarbInput(
                target_calories=None,  # type: ignore[arg-type]
                protein_g=100,
                fat_calories=500,
            )


# ---------------------------------------------------------------------------
# 13. Rounding — ROUND_HALF_UP
# ---------------------------------------------------------------------------


class TestRounding:
    def test_half_up_not_bankers(self):
        """_round_carb_grams uses half-up, not Python round()."""
        assert _round_carb_grams(2) == 1   # 2/4 = 0.5 → half-up → 1
        assert round(0.5) == 0             # documents the distinction
        assert _round_carb_grams(6) == 2   # 6/4 = 1.5 → half-up → 2
        assert _round_carb_grams(10) == 3  # 10/4 = 2.5 → half-up → 3

    def test_half_up_exact_integer(self):
        """Exact integer → no rounding needed."""
        assert _round_carb_grams(4) == 1   # 4/4 = 1.0
        assert _round_carb_grams(8) == 2   # 8/4 = 2.0
        assert _round_carb_grams(400) == 100  # 400/4 = 100.0

    def test_half_up_below_half(self):
        """Below .5 → rounds down."""
        assert _round_carb_grams(1) == 0   # 1/4 = 0.25 → 0
        assert _round_carb_grams(5) == 1   # 5/4 = 1.25 → 1

    def test_half_up_above_half(self):
        """Above .5 → rounds up."""
        assert _round_carb_grams(3) == 1   # 3/4 = 0.75 → 1
        assert _round_carb_grams(7) == 2   # 7/4 = 1.75 → 2

    def test_rounding_in_full_calculation(self):
        """End-to-end rounding: residual=1159, 1159/4=289.75 → 290."""
        result = _calc(2500, 180, 621)
        assert result.carbohydrates_g == 290
        assert result.carbohydrate_calories == 1160

    def test_rounding_half_case_in_full_calculation(self):
        """End-to-end rounding: residual=2, 2/4=0.5 → ROUND_HALF_UP → 1."""
        result = _calc(target_calories=2, protein_g=0, fat_calories=0)
        assert result.carbohydrates_g == 1

    def test_string_decimal_boundary_used(self):
        """Calculator source uses Decimal arithmetic, not float."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "Decimal(" in source
        assert "ROUND_HALF_UP" in source
        assert "quantize" in source

    def test_no_builtin_round_in_calculator(self):
        """No Python round() anywhere in calculator source."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "round(" not in source


# ---------------------------------------------------------------------------
# 14. Large valid values
# ---------------------------------------------------------------------------


class TestLargeValues:
    def test_large_target(self):
        """Large input values produce correct results."""
        result = _calc(
            target_calories=50000,
            protein_g=500,
            fat_calories=10000,
        )
        # 50000 - 2000 - 10000 = 38000
        assert result.status == CarbStatus.OK
        assert result.residual_calories == 38000
        assert result.carbohydrates_g == 9500  # 38000/4 = 9500
        assert result.carbohydrate_calories == 38000

    def test_very_large_target(self):
        """Very large values don't overflow."""
        result = _calc(
            target_calories=1_000_000,
            protein_g=0,
            fat_calories=0,
        )
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g == 250_000
        assert result.carbohydrate_calories == 1_000_000
        assert result.residual_calories == 1_000_000


# ---------------------------------------------------------------------------
# 15. Result immutability
# ---------------------------------------------------------------------------


class TestResultImmutability:
    def test_result_frozen(self):
        """Assignment on CarbResult raises ValidationError."""
        result = _calc()
        with pytest.raises(ValidationError):
            result.status = CarbStatus.INVALID
        with pytest.raises(ValidationError):
            result.carbohydrates_g = 999
        with pytest.raises(ValidationError):
            result.carbohydrate_calories = 999
        with pytest.raises(ValidationError):
            result.residual_calories = 999
        with pytest.raises(ValidationError):
            result.policy_version = "tampered"
        with pytest.raises(ValidationError):
            result.issues = (CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL,)

    def test_issues_tuple_immutability(self):
        """issues is a tuple; list mutation methods raise AttributeError."""
        result = _calc()
        assert isinstance(result.issues, tuple)
        assert result.issues == ()
        with pytest.raises(AttributeError):
            result.issues.append(CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL)  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.extend([CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL])  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.pop()  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            result.issues.clear()  # type: ignore[attr-defined]

    def test_invalid_result_issues_tuple_immutability(self):
        """INVALID result issues are also an immutable tuple."""
        result = _calc(target_calories=0, protein_g=1, fat_calories=0)
        assert isinstance(result.issues, tuple)
        assert result.issues == (CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL,)
        with pytest.raises(AttributeError):
            result.issues.append(CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 16. Result extra fields forbidden
# ---------------------------------------------------------------------------


class TestResultExtraFields:
    def test_result_rejects_extra_fields(self):
        """CarbResult extra='forbid' rejects unknown keys."""
        with pytest.raises(ValidationError):
            CarbResult(
                status=CarbStatus.OK,
                carbohydrates_g=100,
                carbohydrate_calories=400,
                residual_calories=400,
                issues=(),
                policy_version="carb-v1",
                fiber_g=25,
            )

    def test_result_rejects_non_tuple_issues_list(self):
        """strict=True on CarbResult rejects list for tuple issues."""
        with pytest.raises(ValidationError):
            CarbResult(
                status=CarbStatus.OK,
                carbohydrates_g=100,
                carbohydrate_calories=400,
                residual_calories=400,
                issues=[],  # type: ignore[arg-type]
                policy_version="carb-v1",
            )


# ---------------------------------------------------------------------------
# 17. Input immutability
# ---------------------------------------------------------------------------


class TestInputImmutability:
    def test_input_frozen(self):
        """CarbInput is frozen — assignment raises ValidationError."""
        inp = CarbInput(
            target_calories=2000,
            protein_g=150,
            fat_calories=504,
        )
        with pytest.raises(ValidationError):
            inp.target_calories = 1800
        with pytest.raises(ValidationError):
            inp.protein_g = 100
        with pytest.raises(ValidationError):
            inp.fat_calories = 400


# ---------------------------------------------------------------------------
# 18. CarbStatus enum shape
# ---------------------------------------------------------------------------


class TestCarbStatusEnum:
    def test_exactly_two_members(self):
        """CarbStatus has exactly OK and INVALID — no more."""
        assert len(CarbStatus) == 2

    def test_ok_value(self):
        assert CarbStatus.OK.value == "OK"

    def test_invalid_value(self):
        assert CarbStatus.INVALID.value == "INVALID"

    def test_no_incomplete(self):
        assert not any(s.name == "INCOMPLETE" for s in CarbStatus)

    def test_no_review_required(self):
        assert not any(s.name == "REVIEW_REQUIRED" for s in CarbStatus)

    def test_no_error(self):
        assert not any(s.name == "ERROR" for s in CarbStatus)


# ---------------------------------------------------------------------------
# 19. CarbInput field shape — exactly 3 fields, no fat_g
# ---------------------------------------------------------------------------


class TestCarbInputShape:
    def test_exactly_three_fields(self):
        """CarbInput has exactly target_calories, protein_g, fat_calories."""
        assert set(CarbInput.model_fields.keys()) == {
            "target_calories",
            "protein_g",
            "fat_calories",
        }

    def test_no_fat_g_field(self):
        """fat_g is explicitly absent from CarbInput."""
        assert "fat_g" not in CarbInput.model_fields

    def test_no_goal_field(self):
        """goal is explicitly absent from CarbInput."""
        assert "goal" not in CarbInput.model_fields

    def test_input_config_strict_frozen_forbid(self):
        config = CarbInput.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"

    def test_result_config_strict_frozen_forbid(self):
        config = CarbResult.model_config
        assert config.get("strict") is True
        assert config.get("frozen") is True
        assert config.get("extra") == "forbid"


# ---------------------------------------------------------------------------
# 20. Negative residual preserves exact value
# ---------------------------------------------------------------------------


class TestNegativeResidualPreservation:
    def test_minus_fifty(self):
        """Traceability example from policy: residual must be exactly -50."""
        result = _calc(
            target_calories=2000,
            protein_g=150,
            fat_calories=1450,
        )
        # protein_calories = 600
        # residual = 2000 - 600 - 1450 = -50
        assert result.residual_calories == -50
        assert result.residual_calories != 0

    def test_minus_four(self):
        """target=0, protein=1 → residual=-4 exactly."""
        result = _calc(
            target_calories=0,
            protein_g=1,
            fat_calories=0,
        )
        assert result.residual_calories == -4


# ---------------------------------------------------------------------------
# Output contract / nullability / constants
# ---------------------------------------------------------------------------


class TestOutputContract:
    def test_ok_implies_non_null_fields(self):
        result = _calc()
        assert result.status == CarbStatus.OK
        assert result.carbohydrates_g is not None
        assert result.carbohydrate_calories is not None
        assert result.residual_calories is not None
        assert result.issues == ()

    def test_invalid_implies_null_carb_fields(self):
        result = _calc(target_calories=0, protein_g=1, fat_calories=0)
        assert result.status == CarbStatus.INVALID
        assert result.carbohydrates_g is None
        assert result.carbohydrate_calories is None
        assert result.residual_calories is not None  # never null
        assert len(result.issues) == 1

    def test_residual_never_none_on_ok(self):
        result = _calc()
        assert result.residual_calories is not None

    def test_residual_never_none_on_invalid(self):
        result = _calc(target_calories=0, protein_g=1, fat_calories=0)
        assert result.residual_calories is not None

    def test_policy_version_exact(self):
        assert CARB_POLICY_VERSION == "carb-v1"
        for result in (
            _calc(),
            _calc(target_calories=0, protein_g=0, fat_calories=0),
            _calc(target_calories=0, protein_g=1, fat_calories=0),
        ):
            assert result.policy_version == "carb-v1"

    def test_issue_code_exactly_one_member(self):
        """Only NEGATIVE_CARBOHYDRATE_RESIDUAL exists."""
        assert len(CarbIssueCode) == 1
        assert CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL.value == (
            "NEGATIVE_CARBOHYDRATE_RESIDUAL"
        )

    def test_ok_issues_always_empty_tuple(self):
        for tc, pg, fc in [
            (2000, 150, 504),
            (0, 0, 0),
            (100, 0, 0),
        ]:
            result = _calc(tc, pg, fc)
            assert result.status == CarbStatus.OK
            assert result.issues == ()
            assert isinstance(result.issues, tuple)

    def test_carb_g_is_int_on_ok(self):
        result = _calc()
        assert type(result.carbohydrates_g) is int
        assert type(result.carbohydrate_calories) is int

    def test_carb_calories_equals_carb_g_times_four(self):
        """Internal consistency: carbohydrate_calories = carbohydrates_g * 4."""
        for tc, pg, fc in [
            (2000, 150, 504),
            (2500, 180, 621),
            (1000, 50, 252),
            (50000, 500, 10000),
        ]:
            result = _calc(tc, pg, fc)
            assert result.status == CarbStatus.OK
            assert result.carbohydrate_calories == result.carbohydrates_g * 4

    def test_constants(self):
        assert PROTEIN_KCAL_PER_G == 4
        assert CARB_KCAL_PER_G == 4


# ---------------------------------------------------------------------------
# Source isolation / determinism / no medical logic
# ---------------------------------------------------------------------------


class TestSourceIsolation:
    def test_no_fat_g_times_nine(self):
        """Calculator source never computes fat_g * 9."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "fat_g" not in source
        assert "* 9" not in source

    def test_no_llm_dependency(self):
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source

    def test_no_network_dependency(self):
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        for token in ("httpx", "httpcore", "telegram", "requests", "aiohttp"):
            assert token not in source

    def test_no_database_dependency(self):
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        for token in ("sqlite", "sqlalchemy", "postgres", "redis"):
            assert token not in source

    def test_no_clock_or_random(self):
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "datetime.now" not in source
        assert "time.time" not in source
        assert "import random" not in source
        assert "os.environ" not in source
        assert "getenv" not in source

    def test_no_upstream_recalculation(self):
        import app.nutrition.carbohydrate.calculator as mod

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
            "calculate_fat",
            "FatResult",
        ):
            assert token not in source

    def test_no_fiber_subtraction(self):
        """No fiber logic anywhere in calculator source."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "fiber" not in source.lower()

    def test_no_130g_floor(self):
        """No 130g carbohydrate floor or warning."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "130" not in source

    def test_no_amdr(self):
        """No AMDR 45–65% enforcement."""
        import app.nutrition.carbohydrate.calculator as mod

        source = inspect.getsource(mod)
        assert "amdr" not in source.lower()
        assert "45" not in source or "65" not in source  # not both

    def test_no_medical_fields_or_logic(self):
        import app.nutrition.carbohydrate.calculator as calc_mod
        import app.nutrition.carbohydrate.models as models_mod

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
            "glycemic",
            "net_carb",
        )
        for mod in (calc_mod, models_mod):
            for name in dir(mod):
                lowered = name.lower()
                for fragment in forbidden:
                    assert fragment not in lowered, (mod.__name__, name)

        for field_name in list(CarbInput.model_fields) + list(
            CarbResult.model_fields
        ):
            lowered = field_name.lower()
            for fragment in forbidden:
                assert fragment not in lowered, field_name

    def test_determinism_same_input_twice(self):
        inp = CarbInput(
            target_calories=2000, protein_g=150, fat_calories=504
        )
        a = calculate_carbohydrates(inp)
        b = calculate_carbohydrates(inp)
        assert a.model_dump() == b.model_dump()

    def test_determinism_100_invocations(self):
        inp = CarbInput(
            target_calories=2500, protein_g=180, fat_calories=621
        )
        results = [calculate_carbohydrates(inp) for _ in range(100)]
        first = results[0].model_dump()
        assert all(r.model_dump() == first for r in results)

    def test_input_not_mutated(self):
        inp = CarbInput(
            target_calories=2000, protein_g=150, fat_calories=504
        )
        before = inp.model_dump()
        calculate_carbohydrates(inp)
        assert inp.model_dump() == before

    def test_calculate_returns_result_not_none(self):
        assert isinstance(_calc(), CarbResult)
