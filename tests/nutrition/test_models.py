"""Tests for app.nutrition.models — Nutrition Core V1 contracts.

Tests cover:
- Valid contract construction
- Optional field handling
- Missing required field rejection
- Enum validity
- Structural validation (types, ranges)
- Serialization/deserialization
- Extra field rejection
- No silent defaults
- No derived values as inputs
- ClientProfile not mutated
"""

import json

import pytest

from app.nutrition.models import (
    ActivityCategory,
    AssessmentIssue,
    AssessmentStatus,
    GoalType,
    InputStatus,
    InBodySnapshot,
    NutritionAssessment,
    NutritionAssessmentInput,
    NutritionCalculation,
    NutritionPlanningContext,
    NutritionTargets,
    RMRMethod,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_assessment_input(**overrides) -> NutritionAssessmentInput:
    """Create a valid NutritionAssessmentInput with sensible defaults."""
    defaults = {
        "age": 25,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 80.0,
        "goal_type": GoalType.WEIGHT_LOSS,
        "training_days_per_week": 4,
        "work_activity": ActivityCategory.MODERATE,
    }
    defaults.update(overrides)
    return NutritionAssessmentInput(**defaults)


def _make_targets(**overrides) -> NutritionTargets:
    """Create valid NutritionTargets with sensible defaults."""
    defaults = {
        "calories_kcal": 2200.0,
        "protein_g": 160.0,
        "fat_g": 61.0,
        "carbohydrates_g": 250.0,
        "fiber_g": 30.0,
        "status": AssessmentStatus.OK,
    }
    defaults.update(overrides)
    return NutritionTargets(**defaults)


def _make_calculation(**overrides) -> NutritionCalculation:
    """Create valid NutritionCalculation with sensible defaults."""
    defaults = {
        "rmr_kcal": 1800.0,
        "rmr_method": RMRMethod.MIFFLIN_ST_JEOR,
        "activity_factor": 1.55,
        "activity_category": ActivityCategory.MODERATE,
        "tdee_kcal": 2790.0,
        "target_calories_kcal": 2290.0,
        "protein_g": 160.0,
        "fat_g": 63.0,
        "carbohydrates_g": 280.0,
        "fiber_g": 32.0,
        "goal_type": GoalType.WEIGHT_LOSS,
        "current_weight_kg": 80.0,
    }
    defaults.update(overrides)
    return NutritionCalculation(**defaults)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestEnums:
    """Verify all enums have correct values."""

    def test_goal_type_values(self):
        assert GoalType.MAINTENANCE == "maintenance"
        assert GoalType.WEIGHT_LOSS == "weight_loss"
        assert GoalType.WEIGHT_GAIN == "weight_gain"
        assert GoalType.MUSCLE_GAIN == "muscle_gain"

    def test_activity_category_values(self):
        assert ActivityCategory.SEDENTARY == "sedentary"
        assert ActivityCategory.LIGHT == "light"
        assert ActivityCategory.MODERATE == "moderate"
        assert ActivityCategory.HIGH == "high"

    def test_rmr_method_values(self):
        assert RMRMethod.MIFFLIN_ST_JEOR == "mifflin_st_jeor"
        assert RMRMethod.CUNNINGHAM == "cunningham"

    def test_input_status_values(self):
        assert InputStatus.COMPLETE == "COMPLETE"
        assert InputStatus.INCOMPLETE == "INCOMPLETE"
        assert InputStatus.INVALID == "INVALID"

    def test_assessment_status_values(self):
        assert AssessmentStatus.OK == "OK"
        assert AssessmentStatus.WARNING == "WARNING"
        assert AssessmentStatus.REVIEW_REQUIRED == "REVIEW_REQUIRED"
        assert AssessmentStatus.ERROR == "ERROR"

    def test_enums_are_str_enums(self):
        """All enums should be str Enums for JSON serialization."""
        assert isinstance(GoalType.WEIGHT_LOSS, str)
        assert isinstance(ActivityCategory.MODERATE, str)
        assert isinstance(RMRMethod.MIFFLIN_ST_JEOR, str)
        assert isinstance(InputStatus.COMPLETE, str)
        assert isinstance(AssessmentStatus.OK, str)


# ---------------------------------------------------------------------------
# NutritionAssessmentInput tests
# ---------------------------------------------------------------------------

class TestNutritionAssessmentInput:
    """NutritionAssessmentInput contract tests."""

    def test_valid_construction(self):
        """Valid input with all required fields."""
        inp = _make_assessment_input()
        assert inp.age == 25
        assert inp.gender == "male"
        assert inp.height_cm == 175.0
        assert inp.weight_kg == 80.0
        assert inp.goal_type == GoalType.WEIGHT_LOSS
        assert inp.training_days_per_week == 4
        assert inp.work_activity == ActivityCategory.MODERATE

    def test_optional_fields_default_to_none(self):
        """Optional fields default to None, not silent defaults."""
        inp = _make_assessment_input()
        assert inp.target_weight_kg is None
        assert inp.weight_change_target_kg is None
        assert inp.training_duration_minutes is None
        assert inp.exercise_intensity is None
        assert inp.assessment_date is None

    def test_optional_fields_can_be_set(self):
        """Optional fields can be explicitly provided."""
        inp = _make_assessment_input(
            target_weight_kg=70.0,
            weight_change_target_kg=10.0,
            training_duration_minutes=60,
            assessment_date="2026-01-15",
        )
        assert inp.target_weight_kg == 70.0
        assert inp.weight_change_target_kg == 10.0
        assert inp.training_duration_minutes == 60
        assert inp.assessment_date == "2026-01-15"

    def test_missing_age_rejected(self):
        """Missing required field 'age' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(age=None)

    def test_missing_gender_rejected(self):
        """Missing required field 'gender' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(gender=None)

    def test_missing_height_rejected(self):
        """Missing required field 'height_cm' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(height_cm=None)

    def test_missing_weight_rejected(self):
        """Missing required field 'weight_kg' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(weight_kg=None)

    def test_missing_goal_type_rejected(self):
        """Missing required field 'goal_type' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(goal_type=None)

    def test_missing_training_days_rejected(self):
        """Missing required field 'training_days_per_week' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(training_days_per_week=None)

    def test_missing_work_activity_rejected(self):
        """Missing required field 'work_activity' raises validation error."""
        with pytest.raises(Exception):
            _make_assessment_input(work_activity=None)

    def test_negative_age_rejected(self):
        """Negative age is rejected."""
        with pytest.raises(Exception):
            _make_assessment_input(age=-1)

    def test_zero_height_rejected(self):
        """Zero height is rejected (must be > 0)."""
        with pytest.raises(Exception):
            _make_assessment_input(height_cm=0)

    def test_negative_weight_rejected(self):
        """Negative weight is rejected."""
        with pytest.raises(Exception):
            _make_assessment_input(weight_kg=-5)

    def test_training_days_out_of_range_rejected(self):
        """Training days > 7 is rejected."""
        with pytest.raises(Exception):
            _make_assessment_input(training_days_per_week=8)

    def test_negative_training_days_rejected(self):
        """Negative training days is rejected."""
        with pytest.raises(Exception):
            _make_assessment_input(training_days_per_week=-1)

    def test_extra_fields_rejected(self):
        """Extra fields are rejected (extra="forbid")."""
        with pytest.raises(Exception):
            _make_assessment_input(bmr=1800)

    def test_no_derived_values_as_inputs(self):
        """Derived values like BMR, TDEE, activity_factor are not in the contract."""
        inp = _make_assessment_input()
        assert not hasattr(inp, "bmr")
        assert not hasattr(inp, "rmr")
        assert not hasattr(inp, "tdee")
        assert not hasattr(inp, "activity_factor")
        assert not hasattr(inp, "target_calories")
        assert not hasattr(inp, "protein_target")

    def test_serialization_roundtrip(self):
        """JSON serialization/deserialization preserves all fields."""
        inp = _make_assessment_input(
            target_weight_kg=70.0,
            assessment_date="2026-01-15",
        )
        data = inp.model_dump()
        restored = NutritionAssessmentInput.model_validate(data)
        assert restored == inp

    def test_to_json(self):
        """Can serialize to JSON string."""
        inp = _make_assessment_input()
        json_str = inp.model_dump_json()
        assert '"age":25' in json_str
        assert '"gender":"male"' in json_str

    def test_weight_kg_is_selected_authoritative(self):
        """weight_kg represents the selected authoritative assessment weight,
        not necessarily the source (InBody vs profile)."""
        # Weight from profile source
        inp = _make_assessment_input(weight_kg=80.0)
        assert inp.weight_kg == 80.0

        # Weight from InBody source — same contract, different origin
        inp2 = _make_assessment_input(weight_kg=75.0)
        assert inp2.weight_kg == 75.0

        # Both are valid — the mapper selects the source
        assert inp.weight_kg != inp2.weight_kg

    def test_work_activity_is_normalized_category(self):
        """work_activity accepts a normalized ActivityCategory, not raw text."""
        inp = _make_assessment_input(work_activity=ActivityCategory.SEDENTARY)
        assert inp.work_activity == ActivityCategory.SEDENTARY

        inp2 = _make_assessment_input(work_activity=ActivityCategory.HIGH)
        assert inp2.work_activity == ActivityCategory.HIGH

    def test_from_json(self):
        """Can deserialize from JSON string."""
        data = {
            "age": 30,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 60.0,
            "goal_type": "maintenance",
            "training_days_per_week": 3,
            "work_activity": "light",
        }
        inp = NutritionAssessmentInput.model_validate(data)
        assert inp.age == 30
        assert inp.gender == "female"
        assert inp.goal_type == GoalType.MAINTENANCE


# ---------------------------------------------------------------------------
# InBodySnapshot tests
# ---------------------------------------------------------------------------

class TestInBodySnapshot:
    """InBodySnapshot contract tests."""

    def test_empty_snapshot(self):
        """All fields optional — empty snapshot is valid."""
        snap = InBodySnapshot()
        assert snap.weight_kg is None
        assert snap.body_fat_percent is None

    def test_partial_snapshot(self):
        """Partial data is valid."""
        snap = InBodySnapshot(weight_kg=75.0, body_fat_percent=18.5)
        assert snap.weight_kg == 75.0
        assert snap.body_fat_percent == 18.5
        assert snap.fat_mass_kg is None

    def test_full_snapshot(self):
        """All fields provided."""
        snap = InBodySnapshot(
            measurement_date="2026-01-15",
            weight_kg=75.0,
            body_fat_percent=18.5,
            fat_mass_kg=13.9,
            skeletal_muscle_mass_kg=35.0,
            bmi=24.5,
            visceral_fat_level=8.0,
        )
        assert snap.weight_kg == 75.0
        assert snap.body_fat_percent == 18.5

    def test_negative_weight_rejected(self):
        """Negative weight is rejected."""
        with pytest.raises(Exception):
            InBodySnapshot(weight_kg=-5)

    def test_body_fat_out_of_range_rejected(self):
        """Body fat > 100 is rejected."""
        with pytest.raises(Exception):
            InBodySnapshot(body_fat_percent=105)

    def test_negative_body_fat_rejected(self):
        """Negative body fat is rejected."""
        with pytest.raises(Exception):
            InBodySnapshot(body_fat_percent=-5)

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            InBodySnapshot(unknown_field="bad")

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields."""
        snap = InBodySnapshot(weight_kg=75.0, body_fat_percent=18.5)
        data = snap.model_dump()
        restored = InBodySnapshot.model_validate(data)
        assert restored == snap

    def test_inbody_independent_from_assessment_input(self):
        """InBodySnapshot is an independent measurement, not part of assessment input."""
        snap = InBodySnapshot(weight_kg=75.0, body_fat_percent=18.5)
        inp = _make_assessment_input(weight_kg=80.0)

        # InBody says 75, assessment input says 80 — both are valid
        assert snap.weight_kg == 75.0
        assert inp.weight_kg == 80.0

        # InBody does NOT automatically override assessment weight
        # The mapper decides according to an explicit future policy


# ---------------------------------------------------------------------------
# AssessmentIssue tests
# ---------------------------------------------------------------------------

class TestAssessmentIssue:
    """AssessmentIssue contract tests."""

    def test_valid_construction(self):
        """Valid issue with code and message."""
        issue = AssessmentIssue(code="MISSING_GOAL", message="Goal type not provided")
        assert issue.code == "MISSING_GOAL"
        assert issue.message == "Goal type not provided"
        assert issue.field is None

    def test_with_field_reference(self):
        """Issue can reference a specific field."""
        issue = AssessmentIssue(
            code="INVALID_WEIGHT",
            message="Weight must be > 0",
            field="weight_kg",
        )
        assert issue.field == "weight_kg"

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            AssessmentIssue(code="X", message="Y", unknown="Z")

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields."""
        issue = AssessmentIssue(code="X", message="Y", field="z")
        data = issue.model_dump()
        restored = AssessmentIssue.model_validate(data)
        assert restored == issue


# ---------------------------------------------------------------------------
# NutritionCalculation tests
# ---------------------------------------------------------------------------

class TestNutritionCalculation:
    """NutritionCalculation contract tests."""

    def test_valid_construction(self):
        """Valid calculation with all fields."""
        calc = _make_calculation()
        assert calc.rmr_kcal == 1800.0
        assert calc.tdee_kcal == 2790.0
        assert calc.goal_type == GoalType.WEIGHT_LOSS

    def test_negative_rmr_rejected(self):
        """Negative RMR is rejected."""
        with pytest.raises(Exception):
            _make_calculation(rmr_kcal=-100)

    def test_zero_activity_factor_rejected(self):
        """Zero activity factor is rejected."""
        with pytest.raises(Exception):
            _make_calculation(activity_factor=0)

    def test_negative_calories_rejected(self):
        """Negative calorie target is rejected."""
        with pytest.raises(Exception):
            _make_calculation(target_calories_kcal=-100)

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            _make_calculation(unknown_field="bad")

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields."""
        calc = _make_calculation()
        data = calc.model_dump()
        restored = NutritionCalculation.model_validate(data)
        assert restored == calc


# ---------------------------------------------------------------------------
# NutritionAssessment tests
# ---------------------------------------------------------------------------

class TestNutritionAssessment:
    """NutritionAssessment contract tests."""

    def test_ok_assessment(self):
        """Valid assessment with OK status and calculation."""
        calc = _make_calculation()
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
            calculation=calc,
            policy_version="nutrition-v1",
        )
        assert assessment.input_status == InputStatus.COMPLETE
        assert assessment.status == AssessmentStatus.OK
        assert assessment.calculation is not None
        assert assessment.warnings == []
        assert assessment.review_flags == []
        assert assessment.issues == []

    def test_incomplete_input_no_calculation(self):
        """Incomplete input produces no calculation."""
        assessment = NutritionAssessment(
            input_status=InputStatus.INCOMPLETE,
            status=AssessmentStatus.ERROR,
            calculation=None,
            issues=[
                AssessmentIssue(
                    code="MISSING_GOAL",
                    message="Goal type not provided",
                    field="goal_type",
                )
            ],
        )
        assert assessment.calculation is None
        assert len(assessment.issues) == 1
        assert assessment.issues[0].code == "MISSING_GOAL"

    def test_review_required(self):
        """Assessment can have REVIEW_REQUIRED status with calculation."""
        calc = _make_calculation(target_calories_kcal=1100.0)
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.REVIEW_REQUIRED,
            calculation=calc,
            review_flags=["CALORIES_BELOW_1200"],
            issues=[
                AssessmentIssue(
                    code="CALORIES_BELOW_1200",
                    message="Target calories below 1200 kcal",
                )
            ],
        )
        assert assessment.status == AssessmentStatus.REVIEW_REQUIRED
        assert "CALORIES_BELOW_1200" in assessment.review_flags

    def test_warning_status(self):
        """Assessment can have WARNING status."""
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.WARNING,
            calculation=_make_calculation(),
            warnings=["Unusual activity level"],
        )
        assert assessment.status == AssessmentStatus.WARNING
        assert "Unusual activity level" in assessment.warnings

    def test_error_status(self):
        """Assessment can have ERROR status."""
        assessment = NutritionAssessment(
            input_status=InputStatus.INVALID,
            status=AssessmentStatus.ERROR,
            issues=[
                AssessmentIssue(code="INVALID_WEIGHT", message="Weight must be > 0")
            ],
        )
        assert assessment.status == AssessmentStatus.ERROR
        assert assessment.calculation is None

    def test_default_policy_version(self):
        """Default policy version is 'nutrition-v1'."""
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
        )
        assert assessment.policy_version == "nutrition-v1"

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            NutritionAssessment(
                input_status=InputStatus.COMPLETE,
                status=AssessmentStatus.OK,
                unknown="bad",
            )

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields including nested issues."""
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.WARNING,
            calculation=_make_calculation(),
            warnings=["Test warning"],
            review_flags=["Test flag"],
            issues=[AssessmentIssue(code="X", message="Y")],
        )
        data = assessment.model_dump()
        restored = NutritionAssessment.model_validate(data)
        assert restored == assessment

    def test_calculation_none_not_required(self):
        """Calculation is optional — None is valid."""
        assessment = NutritionAssessment(
            input_status=InputStatus.INCOMPLETE,
            status=AssessmentStatus.ERROR,
        )
        assert assessment.calculation is None


# ---------------------------------------------------------------------------
# NutritionTargets tests
# ---------------------------------------------------------------------------

class TestNutritionTargets:
    """NutritionTargets contract tests."""

    def test_valid_construction(self):
        """Valid targets with all required fields."""
        targets = _make_targets()
        assert targets.calories_kcal == 2200.0
        assert targets.protein_g == 160.0
        assert targets.status == AssessmentStatus.OK

    def test_fiber_optional(self):
        """Fiber is optional."""
        targets = _make_targets(fiber_g=None)
        assert targets.fiber_g is None

    def test_negative_calories_rejected(self):
        """Negative calories are rejected."""
        with pytest.raises(Exception):
            _make_targets(calories_kcal=-100)

    def test_negative_protein_rejected(self):
        """Negative protein is rejected."""
        with pytest.raises(Exception):
            _make_targets(protein_g=-10)

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            _make_targets(unknown="bad")

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields."""
        targets = _make_targets()
        data = targets.model_dump()
        restored = NutritionTargets.model_validate(data)
        assert restored == targets

    def test_to_json(self):
        """Can serialize to JSON string."""
        targets = _make_targets()
        json_str = targets.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["calories_kcal"] == 2200.0
        assert parsed["status"] == "OK"

    def test_default_policy_version(self):
        """Default policy version is 'nutrition-v1'."""
        targets = _make_targets()
        assert targets.policy_version == "nutrition-v1"


# ---------------------------------------------------------------------------
# NutritionPlanningContext tests
# ---------------------------------------------------------------------------

class TestNutritionPlanningContext:
    """NutritionPlanningContext contract tests."""

    def test_valid_construction(self):
        """Valid context with all required fields."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            work_activity=ActivityCategory.MODERATE,
            targets=_make_targets(),
        )
        assert ctx.age == 25
        assert ctx.current_weight_kg == 80.0
        assert ctx.targets.calories_kcal == 2200.0

    def test_inbody_optional(self):
        """InBody snapshot is optional."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MAINTENANCE,
            training_days_per_week=3,
            work_activity=ActivityCategory.LIGHT,
            targets=_make_targets(),
        )
        assert ctx.inbody is None

    def test_with_inbody(self):
        """Context can include InBody snapshot."""
        inbody = InBodySnapshot(weight_kg=75.0, body_fat_percent=18.0)
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            work_activity=ActivityCategory.MODERATE,
            inbody=inbody,
            targets=_make_targets(),
        )
        assert ctx.inbody is not None
        assert ctx.inbody.weight_kg == 75.0

    def test_empty_preferences(self):
        """Food preferences default to empty lists."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MAINTENANCE,
            training_days_per_week=3,
            work_activity=ActivityCategory.SEDENTARY,
            targets=_make_targets(),
        )
        assert ctx.injuries == []
        assert ctx.food_preferences == []
        assert ctx.disliked_foods == []
        assert ctx.disliked_activities == []

    def test_with_preferences(self):
        """Food preferences can be provided."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MAINTENANCE,
            training_days_per_week=3,
            work_activity=ActivityCategory.LIGHT,
            injuries=["Lower back pain"],
            food_preferences=["Chicken", "Rice"],
            disliked_foods=["Fish"],
            disliked_activities=["Running"],
            targets=_make_targets(),
        )
        assert "Lower back pain" in ctx.injuries
        assert "Chicken" in ctx.food_preferences
        assert "Fish" in ctx.disliked_foods
        assert "Running" in ctx.disliked_activities

    def test_training_context_fields(self):
        """Training context fields are available for the LLM planner."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            training_duration="2 months",
            training_experience="beginner",
            work_activity=ActivityCategory.MODERATE,
            activity_description="Office job, minimal movement",
            targets=_make_targets(),
        )
        assert ctx.training_duration == "2 months"
        assert ctx.training_experience == "beginner"
        assert ctx.activity_description == "Office job, minimal movement"

    def test_training_context_fields_optional(self):
        """Training context fields default to None."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MAINTENANCE,
            training_days_per_week=3,
            work_activity=ActivityCategory.LIGHT,
            targets=_make_targets(),
        )
        assert ctx.training_duration is None
        assert ctx.training_experience is None
        assert ctx.activity_description is None
        assert ctx.exercise_intensity is None

    def test_exercise_intensity_optional(self):
        """Exercise intensity is optional and carries through if available."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MUSCLE_GAIN,
            training_days_per_week=5,
            work_activity=ActivityCategory.HIGH,
            exercise_intensity="high",
            targets=_make_targets(),
        )
        assert ctx.exercise_intensity == "high"

    def test_extra_fields_rejected(self):
        """Extra fields are rejected."""
        with pytest.raises(Exception):
            NutritionPlanningContext(
                age=25,
                gender="male",
                height_cm=175.0,
                current_weight_kg=80.0,
                goal_type=GoalType.MAINTENANCE,
                training_days_per_week=3,
                work_activity=ActivityCategory.LIGHT,
                targets=_make_targets(),
                bmr=1800,
            )

    def test_serialization_roundtrip(self):
        """JSON roundtrip preserves all fields including nested targets."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.WEIGHT_LOSS,
            training_days_per_week=4,
            training_duration="2 months",
            training_experience="beginner",
            work_activity=ActivityCategory.MODERATE,
            activity_description="Office job",
            exercise_intensity="moderate",
            inbody=InBodySnapshot(weight_kg=75.0),
            food_preferences=["Chicken"],
            disliked_activities=["Running"],
            targets=_make_targets(),
        )
        data = ctx.model_dump()
        restored = NutritionPlanningContext.model_validate(data)
        assert restored == ctx

    def test_no_derived_values_in_context(self):
        """Context does not contain derived values like BMR, TDEE."""
        ctx = NutritionPlanningContext(
            age=25,
            gender="male",
            height_cm=175.0,
            current_weight_kg=80.0,
            goal_type=GoalType.MAINTENANCE,
            training_days_per_week=3,
            work_activity=ActivityCategory.LIGHT,
            targets=_make_targets(),
        )
        assert not hasattr(ctx, "bmr")
        assert not hasattr(ctx, "rmr")
        assert not hasattr(ctx, "tdee")
        assert not hasattr(ctx, "activity_factor")


# ---------------------------------------------------------------------------
# Cross-contract consistency tests
# ---------------------------------------------------------------------------

class TestCrossContractConsistency:
    """Verify contracts work together without mutation."""

    def test_planning_context_from_assessment_input(self):
        """PlanningContext can be constructed from AssessmentInput fields."""
        inp = _make_assessment_input()
        targets = _make_targets()

        ctx = NutritionPlanningContext(
            age=inp.age,
            gender=inp.gender,
            height_cm=inp.height_cm,
            current_weight_kg=inp.weight_kg,
            goal_type=inp.goal_type,
            training_days_per_week=inp.training_days_per_week,
            work_activity=inp.work_activity,
            targets=targets,
        )
        assert ctx.age == inp.age
        assert ctx.gender == inp.gender

    def test_assessment_input_not_mutated(self):
        """Creating PlanningContext does not mutate AssessmentInput."""
        inp = _make_assessment_input()
        original_age = inp.age
        original_weight = inp.weight_kg

        _ = NutritionPlanningContext(
            age=inp.age,
            gender=inp.gender,
            height_cm=inp.height_cm,
            current_weight_kg=inp.weight_kg,
            goal_type=inp.goal_type,
            training_days_per_week=inp.training_days_per_week,
            work_activity=inp.work_activity,
            targets=_make_targets(),
        )
        assert inp.age == original_age
        assert inp.weight_kg == original_weight

    def test_assessment_holds_calculation(self):
        """NutritionAssessment contains NutritionCalculation."""
        calc = _make_calculation()
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
            calculation=calc,
        )
        assert assessment.calculation.rmr_kcal == 1800.0
        assert assessment.calculation.goal_type == GoalType.WEIGHT_LOSS

    def test_targets_from_assessment(self):
        """NutritionTargets can be derived from NutritionAssessment."""
        calc = _make_calculation()
        assessment = NutritionAssessment(
            input_status=InputStatus.COMPLETE,
            status=AssessmentStatus.OK,
            calculation=calc,
        )

        targets = NutritionTargets(
            calories_kcal=calc.target_calories_kcal,
            protein_g=calc.protein_g,
            fat_g=calc.fat_g,
            carbohydrates_g=calc.carbohydrates_g,
            fiber_g=calc.fiber_g,
            status=assessment.status,
            policy_version=assessment.policy_version,
        )
        assert targets.calories_kcal == calc.target_calories_kcal
        assert targets.status == AssessmentStatus.OK

    def test_all_enums_importable_from_package(self):
        """All enums are importable from app.nutrition."""
        from app.nutrition import (
            ActivityCategory,
            AssessmentStatus,
            GoalType,
            InputStatus,
            RMRMethod,
        )
        assert GoalType.MAINTENANCE == "maintenance"
        assert ActivityCategory.SEDENTARY == "sedentary"
        assert InputStatus.COMPLETE == "COMPLETE"
        assert AssessmentStatus.OK == "OK"
        assert RMRMethod.MIFFLIN_ST_JEOR == "mifflin_st_jeor"

    def test_all_models_importable_from_package(self):
        """All models are importable from app.nutrition."""
        from app.nutrition import (
            AssessmentIssue,
            InBodySnapshot,
            NutritionAssessment,
            NutritionAssessmentInput,
            NutritionCalculation,
            NutritionPlanningContext,
            NutritionTargets,
        )
        assert NutritionAssessmentInput is not None
        assert NutritionTargets is not None
