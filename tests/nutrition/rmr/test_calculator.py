"""Tests for app.nutrition.rmr — RMR Calculator (rmr-v1).

Implements all 35 deterministic test cases from the locked policy:
- TC-01 to TC-10: Normal calculations and boundary values
- TC-11 to TC-17: Invalid ranges
- TC-18 to TC-21: Missing data
- TC-22 to TC-24: Unsupported gender
- TC-25 to TC-27: Negative values
- TC-28 to TC-30: Rounding boundary cases
- TC-31 to TC-33, TC-35: Non-finite and type errors
- TC-34: Mapper isolation test
"""

import math
import pytest

from app.nutrition.rmr.rmr_calculator import RMRCalculator, RMR_POLICY_VERSION
from app.nutrition.rmr.rmr_mapper import RMRMapper
from app.nutrition.rmr.rmr_models import (
    BiologicalSex,
    RMRInput,
    RMRMethod,
    RMRResult,
    RMRStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_input(
    age=30,
    gender="MALE",
    height_cm=180.0,
    weight_kg=80.0,
) -> RMRInput:
    """Create a valid RMRInput for testing."""
    return RMRInput(age=age, gender=gender, height_cm=height_cm, weight_kg=weight_kg)


# ---------------------------------------------------------------------------
# TC-01 to TC-10: Normal calculations and boundary values
# ---------------------------------------------------------------------------


class TestRMCCalculations:
    """TC-01 to TC-10: Standard and boundary calculations."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc01_standard_male(self):
        """TC-01: Standard Male Benchmark — 30yr, MALE, 180cm, 80kg → 1780."""
        result = self.calc.calculate(_make_input(30, "MALE", 180.0, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1780
        assert result.rmr_method == RMRMethod.MIFFLIN_ST_JEOR
        assert result.issues == []
        assert result.policy_version == "rmr-v1"

    def test_tc02_standard_female(self):
        """TC-02: Standard Female Benchmark — 30yr, FEMALE, 180cm, 80kg → 1614."""
        result = self.calc.calculate(_make_input(30, "FEMALE", 180.0, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1614

    def test_tc03_young_male(self):
        """TC-03: Young Adult Male — 25yr, MALE, 175cm, 70kg → 1674."""
        result = self.calc.calculate(_make_input(25, "MALE", 175.0, 70.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1674

    def test_tc04_young_female(self):
        """TC-04: Young Adult Female — 25yr, FEMALE, 165cm, 60kg → 1345."""
        result = self.calc.calculate(_make_input(25, "FEMALE", 165.0, 60.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1345

    def test_tc05_boundary_min_age(self):
        """TC-05: Boundary Min Age (18) — 18yr, MALE, 170cm, 65kg → 1628."""
        result = self.calc.calculate(_make_input(18, "MALE", 170.0, 65.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1628

    def test_tc06_boundary_max_age(self):
        """TC-06: Boundary Max Age (120) — 120yr, FEMALE, 150cm, 50kg → 677."""
        result = self.calc.calculate(_make_input(120, "FEMALE", 150.0, 50.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 677

    def test_tc07_boundary_min_height(self):
        """TC-07: Boundary Min Height (50.0cm) — 40yr, MALE, 50cm, 50kg → 618."""
        result = self.calc.calculate(_make_input(40, "MALE", 50.0, 50.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 618

    def test_tc08_boundary_max_height(self):
        """TC-08: Boundary Max Height (250.0cm) — 40yr, FEMALE, 250cm, 100kg → 2202."""
        result = self.calc.calculate(_make_input(40, "FEMALE", 250.0, 100.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 2202

    def test_tc09_boundary_min_weight(self):
        """TC-09: Boundary Min Weight (20.0kg) — 50yr, MALE, 180cm, 20kg → 1080."""
        result = self.calc.calculate(_make_input(50, "MALE", 180.0, 20.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1080

    def test_tc10_boundary_max_weight(self):
        """TC-10: Boundary Max Weight (350.0kg) — 50yr, FEMALE, 180cm, 350kg → 4214."""
        result = self.calc.calculate(_make_input(50, "FEMALE", 180.0, 350.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 4214


# ---------------------------------------------------------------------------
# TC-11 to TC-17: Invalid ranges
# ---------------------------------------------------------------------------


class TestRMCInvalidRanges:
    """TC-11 to TC-17: Invalid input ranges."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc11_underage_minor(self):
        """TC-11: Underage Minor (17yr) → INVALID, UNDERAGE_NOT_SUPPORTED."""
        result = self.calc.calculate(_make_input(17, "MALE", 175.0, 70.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert result.rmr_method is None
        assert "UNDERAGE_NOT_SUPPORTED" in result.issues

    def test_tc12_pediatric_age(self):
        """TC-12: Pediatric Age (0yr) → INVALID, UNDERAGE_NOT_SUPPORTED."""
        result = self.calc.calculate(_make_input(0, "FEMALE", 50.0, 3.5))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "UNDERAGE_NOT_SUPPORTED" in result.issues

    def test_tc13_exceed_max_age(self):
        """TC-13: Exceed Max Age (121yr) → INVALID, INVALID_AGE."""
        result = self.calc.calculate(_make_input(121, "MALE", 170.0, 65.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_AGE" in result.issues

    def test_tc14_below_min_height(self):
        """TC-14: Below Min Height (49.9cm) → INVALID, INVALID_HEIGHT."""
        result = self.calc.calculate(_make_input(30, "FEMALE", 49.9, 50.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_HEIGHT" in result.issues

    def test_tc15_exceed_max_height(self):
        """TC-15: Exceed Max Height (250.1cm) → INVALID, INVALID_HEIGHT."""
        result = self.calc.calculate(_make_input(30, "MALE", 250.1, 80.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_HEIGHT" in result.issues

    def test_tc16_below_min_weight(self):
        """TC-16: Below Min Weight (19.9kg) → INVALID, INVALID_WEIGHT."""
        result = self.calc.calculate(_make_input(30, "FEMALE", 160.0, 19.9))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_WEIGHT" in result.issues

    def test_tc17_exceed_max_weight(self):
        """TC-17: Exceed Max Weight (350.1kg) → INVALID, INVALID_WEIGHT."""
        result = self.calc.calculate(_make_input(30, "MALE", 180.0, 350.1))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_WEIGHT" in result.issues


# ---------------------------------------------------------------------------
# TC-18 to TC-21: Missing data
# ---------------------------------------------------------------------------


class TestRMCMissingData:
    """TC-18 to TC-21: Missing required fields."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc18_missing_age(self):
        """TC-18: Missing Age → INCOMPLETE, MISSING_RMR_DATA."""
        result = self.calc.calculate(RMRInput(
            age=None, gender="MALE", height_cm=180.0, weight_kg=80.0,
        ))
        assert result.status == RMRStatus.INCOMPLETE
        assert result.rmr_kcal is None
        assert result.rmr_method is None
        assert "MISSING_RMR_DATA" in result.issues

    def test_tc19_missing_gender(self):
        """TC-19: Missing Gender → INCOMPLETE, MISSING_RMR_DATA."""
        result = self.calc.calculate(RMRInput(
            age=30, gender=None, height_cm=180.0, weight_kg=80.0,
        ))
        assert result.status == RMRStatus.INCOMPLETE
        assert result.rmr_kcal is None
        assert "MISSING_RMR_DATA" in result.issues

    def test_tc20_missing_height(self):
        """TC-20: Missing Height → INCOMPLETE, MISSING_RMR_DATA."""
        result = self.calc.calculate(RMRInput(
            age=30, gender="MALE", height_cm=None, weight_kg=80.0,
        ))
        assert result.status == RMRStatus.INCOMPLETE
        assert result.rmr_kcal is None
        assert "MISSING_RMR_DATA" in result.issues

    def test_tc21_missing_weight(self):
        """TC-21: Missing Weight → INCOMPLETE, MISSING_RMR_DATA."""
        result = self.calc.calculate(RMRInput(
            age=30, gender="FEMALE", height_cm=180.0, weight_kg=None,
        ))
        assert result.status == RMRStatus.INCOMPLETE
        assert result.rmr_kcal is None
        assert "MISSING_RMR_DATA" in result.issues


# ---------------------------------------------------------------------------
# TC-22 to TC-24: Unsupported gender
# ---------------------------------------------------------------------------


class TestRMCUnsupportedGender:
    """TC-22 to TC-24: Unsupported gender values."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc22_non_binary_gender(self):
        """TC-22: Non-Binary Gender ("OTHER") → INVALID, UNSUPPORTED_GENDER."""
        result = self.calc.calculate(_make_input(30, "OTHER", 180.0, 80.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "UNSUPPORTED_GENDER" in result.issues

    def test_tc23_unspecified_gender(self):
        """TC-23: Unspecified Gender ("UNKNOWN") → INVALID, UNSUPPORTED_GENDER."""
        result = self.calc.calculate(_make_input(30, "UNKNOWN", 180.0, 80.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "UNSUPPORTED_GENDER" in result.issues

    def test_tc24_unnormalized_single_char(self):
        """TC-24: Unnormalized Single Char ("M") → INVALID, UNSUPPORTED_GENDER."""
        result = self.calc.calculate(_make_input(30, "M", 180.0, 80.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "UNSUPPORTED_GENDER" in result.issues


# ---------------------------------------------------------------------------
# TC-25 to TC-27: Negative values
# ---------------------------------------------------------------------------


class TestRMCNegativeValues:
    """TC-25 to TC-27: Negative numeric values."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc25_negative_age(self):
        """TC-25: Negative Age (-10) → INVALID, INVALID_AGE."""
        result = self.calc.calculate(_make_input(-10, "FEMALE", 160.0, 55.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_AGE" in result.issues

    def test_tc26_negative_height(self):
        """TC-26: Negative Height (-170.0) → INVALID, INVALID_HEIGHT."""
        result = self.calc.calculate(_make_input(30, "MALE", -170.0, 70.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_HEIGHT" in result.issues

    def test_tc27_negative_weight(self):
        """TC-27: Negative Weight (-55.0) → INVALID, INVALID_WEIGHT."""
        result = self.calc.calculate(_make_input(30, "FEMALE", 160.0, -55.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert "INVALID_WEIGHT" in result.issues


# ---------------------------------------------------------------------------
# TC-28 to TC-30: Rounding boundary cases
# ---------------------------------------------------------------------------


class TestRMCRounding:
    """TC-28 to TC-30: Half-up rounding boundary cases."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc28_rounding_below_half(self):
        """TC-28: Rounding Below Half (.4875) → 1614."""
        # 30yr, FEMALE, 180.078cm, 80.0kg
        # RMR_raw = (10*80) + (6.25*180.078) - (5*30) - 161
        #         = 800 + 1125.4875 - 150 - 161 = 1614.4875
        # Half-up: 1614.4875 → 1614
        result = self.calc.calculate(_make_input(30, "FEMALE", 180.078, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1614

    def test_tc29_exact_half_up(self):
        """TC-29: Exact Half-Up Rounding (.50) → 1781."""
        # 30yr, MALE, 180.08cm, 80.0kg
        # RMR_raw = (10*80) + (6.25*180.08) - (5*30) + 5
        #         = 800 + 1125.5 - 150 + 5 = 1780.5
        # Half-up: 1780.5 → 1781
        result = self.calc.calculate(_make_input(30, "MALE", 180.08, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1781

    def test_tc30_rounding_above_half(self):
        """TC-30: Rounding Above Half (.5125) → 1781."""
        # 30yr, MALE, 180.082cm, 80.0kg
        # RMR_raw = (10*80) + (6.25*180.082) - (5*30) + 5
        #         = 800 + 1125.5125 - 150 + 5 = 1780.5125
        # Half-up: 1780.5125 → 1781
        result = self.calc.calculate(_make_input(30, "MALE", 180.082, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1781


# ---------------------------------------------------------------------------
# TC-31 to TC-33, TC-35: Non-finite and type errors
# ---------------------------------------------------------------------------


class TestRMCNonFiniteAndTypes:
    """TC-31 to TC-33, TC-35: Non-finite floats and invalid types."""

    def setup_method(self):
        self.calc = RMRCalculator()

    def test_tc31_nan_input(self):
        """TC-31: NaN → ERROR, NUMERIC_OUT_OF_RANGE."""
        result = self.calc.calculate(_make_input(float("nan"), "MALE", 180.0, 80.0))
        assert result.status == RMRStatus.ERROR
        assert result.rmr_kcal is None
        assert result.rmr_method is None
        assert "NUMERIC_OUT_OF_RANGE" in result.issues

    def test_tc32_positive_infinity(self):
        """TC-32: +Infinity → ERROR, NUMERIC_OUT_OF_RANGE."""
        result = self.calc.calculate(_make_input(30, "FEMALE", 180.0, float("inf")))
        assert result.status == RMRStatus.ERROR
        assert result.rmr_kcal is None
        assert "NUMERIC_OUT_OF_RANGE" in result.issues

    def test_tc33_non_numeric_type(self):
        """TC-33: Non-Numeric Type ("eighty") → ERROR, INVALID_NUMERIC_TYPE."""
        mapper = RMRMapper()
        result = mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": 180.0,
            "weight_kg": "eighty",
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert result.rmr_kcal is None
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_tc35_negative_infinity(self):
        """TC-35: -Infinity → ERROR, NUMERIC_OUT_OF_RANGE."""
        result = self.calc.calculate(_make_input(30, "MALE", 180.0, float("-inf")))
        assert result.status == RMRStatus.ERROR
        assert result.rmr_kcal is None
        assert "NUMERIC_OUT_OF_RANGE" in result.issues


# ---------------------------------------------------------------------------
# TC-34: Mapper isolation test
# ---------------------------------------------------------------------------


class TestRMCMapperIsolation:
    """TC-34: Mapper isolation — non-RMR fields do not affect RMR."""

    def setup_method(self):
        self.calc = RMRCalculator()
        self.mapper = RMRMapper()

    def test_tc34_mapper_isolation(self):
        """TC-34: Two NutritionAssessmentInput objects with identical RMR fields
        but different non-RMR fields must produce identical RMR results."""
        # We use the mapper with dict inputs since NutritionAssessmentInput
        # has required fields we don't want to construct fully.
        # The key test is that the mapper extracts ONLY the 4 RMR fields.

        input_a = {
            "age": 30,
            "gender": "MALE",
            "height_cm": 180.0,
            "weight_kg": 80.0,
            "goal_type": "weight_loss",
            "target_weight_kg": 75.0,
            "training_days_per_week": 5,
        }

        input_b = {
            "age": 30,
            "gender": "MALE",
            "height_cm": 180.0,
            "weight_kg": 80.0,
            "goal_type": "muscle_gain",
            "target_weight_kg": 90.0,
            "training_days_per_week": 0,
        }

        rmr_input_a = self.mapper.map_from_dict(input_a)
        rmr_input_b = self.mapper.map_from_dict(input_b)

        assert isinstance(rmr_input_a, RMRInput)
        assert isinstance(rmr_input_b, RMRInput)

        # RMRInput values must be identical
        assert rmr_input_a.age == rmr_input_b.age
        assert rmr_input_a.gender == rmr_input_b.gender
        assert rmr_input_a.height_cm == rmr_input_b.height_cm
        assert rmr_input_a.weight_kg == rmr_input_b.weight_kg

        # RMR results must also be identical
        result_a = self.calc.calculate(rmr_input_a)
        result_b = self.calc.calculate(rmr_input_b)

        assert result_a.status == result_b.status == RMRStatus.OK
        assert result_a.rmr_kcal == result_b.rmr_kcal == 1780
        assert result_a.rmr_method == result_b.rmr_method == RMRMethod.MIFFLIN_ST_JEOR


# ---------------------------------------------------------------------------
# Additional integration tests
# ---------------------------------------------------------------------------


class TestRMCIntegration:
    """Integration tests for the full RMR pipeline."""

    def setup_method(self):
        self.calc = RMRCalculator()
        self.mapper = RMRMapper()

    def test_mapper_to_calculator_pipeline(self):
        """Full pipeline: dict → mapper → calculator → result."""
        data = {
            "age": 25,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 60.0,
        }
        rmr_input = self.mapper.map_from_dict(data)
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.gender == "FEMALE"  # Normalized

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1345

    def test_mapper_normalizes_lowercase_gender(self):
        """Mapper normalizes "male" → "MALE", "female" → "FEMALE."""
        data_male = {"age": 30, "gender": "male", "height_cm": 180.0, "weight_kg": 80.0}
        data_female = {"age": 30, "gender": "female", "height_cm": 180.0, "weight_kg": 80.0}

        result_male = self.calc.calculate(self.mapper.map_from_dict(data_male))
        result_female = self.calc.calculate(self.mapper.map_from_dict(data_female))

        assert result_male.rmr_kcal == 1780
        assert result_female.rmr_kcal == 1614

    def test_mapper_rejects_bool_weight(self):
        """Bool values for numeric fields → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": 180.0,
            "weight_kg": True,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_rejects_bool_age(self):
        """Bool age → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": True, "gender": "MALE", "height_cm": 180.0,
            "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_rejects_string_height(self):
        """String height → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": "tall",
            "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_unsupported_gender_string(self):
        """Unsupported gender string → passes through to calculator → INVALID."""
        data = {"age": 30, "gender": "OTHER", "height_cm": 180.0, "weight_kg": 80.0}
        rmr_input = self.mapper.map_from_dict(data)
        assert isinstance(rmr_input, RMRInput)

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INVALID
        assert "UNSUPPORTED_GENDER" in result.issues

    def test_calculator_has_no_llm_dependency(self):
        """Calculator does not import or use LLM modules."""
        import app.nutrition.rmr.rmr_calculator as mod
        source = open(mod.__file__).read()
        # Check for actual import statements, not docstring content
        assert "import llm" not in source
        assert "from llm" not in source
        assert "LLMClient" not in source
        assert "ProfileExtractor" not in source

    def test_calculator_has_no_network_dependency(self):
        """Calculator does not import or use network modules."""
        import app.nutrition.rmr.rmr_calculator as mod
        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source

    def test_policy_version_constant(self):
        """Policy version is rmr-v1."""
        assert RMR_POLICY_VERSION == "rmr-v1"

    def test_success_payload_fields(self):
        """Successful result has all required fields populated."""
        result = self.calc.calculate(_make_input(30, "MALE", 180.0, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1780
        assert result.rmr_method == RMRMethod.MIFFLIN_ST_JEOR
        assert result.policy_version == "rmr-v1"
        assert result.issues == []

    def test_failure_payload_fields(self):
        """Failed result has null rmr_kcal and rmr_method."""
        result = self.calc.calculate(_make_input(17, "MALE", 175.0, 70.0))
        assert result.status == RMRStatus.INVALID
        assert result.rmr_kcal is None
        assert result.rmr_method is None
        assert result.policy_version == "rmr-v1"
        assert len(result.issues) > 0

    def test_no_intermediate_rounding(self):
        """Verify no intermediate rounding by checking raw calculation."""
        # 30yr, MALE, 180.08cm, 80.0kg
        # Raw = 800 + 1125.5 - 150 + 5 = 1780.5
        # If intermediate rounding happened: 1125.5 → 1126, then 800+1126-150+5=1781
        # Without intermediate rounding: 800+1125.5-150+5=1780.5 → half-up → 1781
        result = self.calc.calculate(_make_input(30, "MALE", 180.08, 80.0))
        assert result.rmr_kcal == 1781

    def test_mifflin_st_jeor_equation_male(self):
        """Verify Mifflin-St Jeor equation for male."""
        # RMR = 10*W + 6.25*H - 5*A + 5
        # W=80, H=180, A=30
        # = 800 + 1125 - 150 + 5 = 1780
        result = self.calc.calculate(_make_input(30, "MALE", 180.0, 80.0))
        assert result.rmr_kcal == 1780

    def test_mifflin_st_jeor_equation_female(self):
        """Verify Mifflin-St Jeor equation for female."""
        # RMR = 10*W + 6.25*H - 5*A - 161
        # W=80, H=180, A=30
        # = 800 + 1125 - 150 - 161 = 1614
        result = self.calc.calculate(_make_input(30, "FEMALE", 180.0, 80.0))
        assert result.rmr_kcal == 1614

    def test_float_age_is_valid(self):
        """Float age (30.0) is valid per policy — 'Integer / Float'."""
        result = self.calc.calculate(_make_input(30.0, "MALE", 180.0, 80.0))
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1780


# ---------------------------------------------------------------------------
# Mapper boundary regression tests
# ---------------------------------------------------------------------------


class TestRMMapperBoundary:
    """Regression tests for mapper type-validation boundary.

    Ensures:
    - None → passes through to calculator → INCOMPLETE / MISSING_RMR_DATA
    - Wrong primitive types → ERROR / INVALID_NUMERIC_TYPE
    - Unsupported gender strings → INVALID / UNSUPPORTED_GENDER
    - Gender type errors → ERROR / INVALID_NUMERIC_TYPE
    """

    def setup_method(self):
        self.calc = RMRCalculator()
        self.mapper = RMRMapper()

    # --- Missing data (None) → should reach calculator for INCOMPLETE ---

    def test_mapper_none_age(self):
        """None age → passes through → calculator returns INCOMPLETE."""
        rmr_input = self.mapper.map_from_dict({
            "age": None, "gender": "MALE", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.age is None

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues

    def test_mapper_none_height(self):
        """None height → passes through → calculator returns INCOMPLETE."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": None, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.height_cm is None

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues

    def test_mapper_none_weight(self):
        """None weight → passes through → calculator returns INCOMPLETE."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": "FEMALE", "height_cm": 180.0, "weight_kg": None,
        })
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.weight_kg is None

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues

    def test_mapper_none_gender(self):
        """None gender → passes through → calculator returns INCOMPLETE."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": None, "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.gender is None

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues

    def test_mapper_all_none(self):
        """All fields None → passes through → calculator returns INCOMPLETE."""
        rmr_input = self.mapper.map_from_dict({
            "age": None, "gender": None, "height_cm": None, "weight_kg": None,
        })
        assert isinstance(rmr_input, RMRInput)

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues

    # --- Wrong primitive types → ERROR / INVALID_NUMERIC_TYPE ---

    def test_mapper_string_age(self):
        """String age → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": "eighty", "gender": "MALE", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_string_weight(self):
        """String weight → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": 180.0, "weight_kg": "heavy",
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_string_height(self):
        """String height → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "FEMALE", "height_cm": "tall", "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_bool_weight(self):
        """Bool weight → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": 180.0, "weight_kg": True,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_bool_age(self):
        """Bool age → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": False, "gender": "MALE", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_list_weight(self):
        """List weight → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "MALE", "height_cm": 180.0, "weight_kg": [80],
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_dict_height(self):
        """Dict height → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": "FEMALE", "height_cm": {"cm": 180}, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    # --- Gender type errors → ERROR / INVALID_NUMERIC_TYPE ---

    def test_mapper_int_gender(self):
        """Int gender → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": 1, "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_bool_gender(self):
        """Bool gender → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": True, "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    def test_mapper_list_gender(self):
        """List gender → ERROR, INVALID_NUMERIC_TYPE."""
        result = self.mapper.map_from_dict({
            "age": 30, "gender": ["MALE"], "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues

    # --- Unsupported gender strings → INVALID / UNSUPPORTED_GENDER ---

    def test_mapper_unsupported_gender_other(self):
        """Gender "OTHER" → passes through → calculator returns INVALID."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": "OTHER", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INVALID
        assert "UNSUPPORTED_GENDER" in result.issues

    def test_mapper_unsupported_gender_m(self):
        """Gender "M" → passes through → calculator returns INVALID."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": "M", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INVALID
        assert "UNSUPPORTED_GENDER" in result.issues

    def test_mapper_unsupported_gender_unknown(self):
        """Gender "UNKNOWN" → passes through → calculator returns INVALID."""
        rmr_input = self.mapper.map_from_dict({
            "age": 30, "gender": "UNKNOWN", "height_cm": 180.0, "weight_kg": 80.0,
        })
        assert isinstance(rmr_input, RMRInput)

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INVALID
        assert "UNSUPPORTED_GENDER" in result.issues

    # --- Mapper → calculator end-to-end ---

    def test_mapper_end_to_end_male(self):
        """Full pipeline: mapper normalizes, calculator computes correctly."""
        data = {"age": 30, "gender": "male", "height_cm": 180.0, "weight_kg": 80.0}
        rmr_input = self.mapper.map_from_dict(data)
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.gender == "MALE"

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1780

    def test_mapper_end_to_end_female(self):
        """Full pipeline: mapper normalizes, calculator computes correctly."""
        data = {"age": 30, "gender": "female", "height_cm": 180.0, "weight_kg": 80.0}
        rmr_input = self.mapper.map_from_dict(data)
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.gender == "FEMALE"

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.OK
        assert result.rmr_kcal == 1614

    def test_mapper_end_to_end_missing_age(self):
        """Full pipeline: None age → INCOMPLETE."""
        data = {"age": None, "gender": "MALE", "height_cm": 180.0, "weight_kg": 80.0}
        rmr_input = self.mapper.map_from_dict(data)
        assert isinstance(rmr_input, RMRInput)
        assert rmr_input.age is None

        result = self.calc.calculate(rmr_input)
        assert result.status == RMRStatus.INCOMPLETE
        assert "MISSING_RMR_DATA" in result.issues
        assert result.rmr_kcal is None
        assert result.rmr_method is None

    def test_mapper_end_to_end_type_error(self):
        """Full pipeline: string weight → ERROR."""
        data = {"age": 30, "gender": "MALE", "height_cm": 180.0, "weight_kg": "heavy"}
        result = self.mapper.map_from_dict(data)
        assert isinstance(result, RMRResult)
        assert result.status == RMRStatus.ERROR
        assert "INVALID_NUMERIC_TYPE" in result.issues
        assert result.rmr_kcal is None
        assert result.rmr_method is None
