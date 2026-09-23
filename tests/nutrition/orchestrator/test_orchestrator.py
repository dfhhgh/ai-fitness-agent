"""Comprehensive test suite for Nutrition Core Orchestrator 2.2.9.

Covers:
- ORCH-001: Happy path (COMPLETE, full targets, no review flags)
- ORCH-002: Low calorie (target < 1200 kcal → REVIEW_REQUIRED + targets + LOW_CALORIE_REVIEW_REQUIRED)
- ORCH-003: InBody mismatch (REVIEW_REQUIRED + INBODY_WEIGHT_MISMATCH, resolved weight unchanged, targets preserved)
- ORCH-004: Activity incomplete (Core INCOMPLETE, targets None, independent RMR/Protein preserved)
- ORCH-005: RMR invalid (underage → Core INVALID, downstream energy chain skipped, independent Protein preserved)
- ORCH-006: Activity conflict (Core INVALID, energy chain skipped)
- ORCH-007: Carb invalid (negative residual → Core INVALID, targets None, carb residual preserved)
- ORCH-008: Contract immutability (frozen Pydantic contracts)
- ORCH-009: Extra fields forbidden (ValidationError)
- ORCH-010: Idempotency (identical output across invocations)
- Weight authority precedence (survey primary, profile prefill, InBody never overrides, unresolved weight)
- Option B invariant (targets present iff 4 macros non-null and Core in {COMPLETE, REVIEW_REQUIRED})
- Fiber independence (non-blocking placeholder)
- Injury isolation (macro targets bitwise identical with and without injuries)
- Planning gate and context assembly
- Determinism and isolation (no clock/random/network/DB in source)
"""

import inspect
import pytest
from pydantic import ValidationError

from app.nutrition.activity.activity_models import ActivityClassificationInput
from app.nutrition.calorie_target import LOW_CALORIE_REVIEW_REQUIRED
from app.nutrition.carbohydrate import CarbStatus
from app.nutrition.models import (
    ActivityCategory,
    DailyMovement,
    ExerciseIntensity,
    GoalType,
    InBodySnapshot,
    NutritionAssessmentInput,
    OccupationalActivity,
)
from app.nutrition.orchestrator import (
    INBODY_WEIGHT_MISMATCH,
    ORCHESTRATOR_VERSION,
    CoreAssessmentStatus,
    NutritionCoreInput,
    NutritionCoreOrchestrator,
    NutritionTargets,
    WeightAuthoritySource,
    build_planning_context,
    is_planning_allowed,
    prefill_survey_weight,
)
from app.nutrition.protein import ProteinStatus
from app.nutrition.rmr import RMRStatus
from app.profile.models import (
    ClientProfile,
    HealthInfo,
    PersonalInfo,
    TrainingInfo,
)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _make_profile(**kwargs) -> ClientProfile:
    """Create a default ClientProfile with optional overrides."""
    personal_kwargs = kwargs.pop("personal_kwargs", {})
    health_kwargs = kwargs.pop("health_kwargs", {})
    training_kwargs = kwargs.pop("training_kwargs", {})

    personal = PersonalInfo(**personal_kwargs)
    health = HealthInfo(**health_kwargs)
    training = TrainingInfo(**training_kwargs)

    return ClientProfile(
        personal=personal,
        health=health,
        training=training,
        **kwargs,
    )


def _make_survey(**kwargs) -> NutritionAssessmentInput:
    """Create a default valid NutritionAssessmentInput with sensible defaults."""
    defaults = {
        "age": 30,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 75.0,
        "goal_type": GoalType.MAINTENANCE,
        "training_days_per_week": 3,
        "work_activity": ActivityCategory.MODERATE,
        "training_duration_minutes": 45,
    }
    defaults.update(kwargs)
    return NutritionAssessmentInput(**defaults)


def _make_core_input(
    profile: ClientProfile = None,
    survey: NutritionAssessmentInput = None,
    inbody: InBodySnapshot = None,
    activity_input: ActivityClassificationInput = None,
    weight_source: WeightAuthoritySource = None,
) -> NutritionCoreInput:
    """Create a NutritionCoreInput."""
    if profile is None:
        profile = _make_profile()
    if survey is None:
        survey = _make_survey()
    return NutritionCoreInput(
        client_profile=profile,
        nutrition_input=survey,
        inbody_snapshot=inbody,
        activity_input=activity_input,
        weight_authority_source=weight_source,
    )


# ---------------------------------------------------------------------------
# 1. ORCH-001: Happy Path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_orch_001_happy_path(self):
        """ORCH-001: Valid inputs produce COMPLETE status and full Option B targets."""
        orchestrator = NutritionCoreOrchestrator()
        core_input = _make_core_input()

        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.COMPLETE
        assert assessment.resolved_current_weight_kg == 75.0
        assert assessment.weight_authority_source == WeightAuthoritySource.SURVEY
        assert assessment.review_flags == []
        assert assessment.issues == []

        # Targets must be issued with all 4 macros non-null
        assert assessment.targets is not None
        assert isinstance(assessment.targets, NutritionTargets)
        assert assessment.targets.calories_kcal > 0
        assert assessment.targets.protein_g > 0
        assert assessment.targets.fat_g > 0
        assert assessment.targets.carbohydrates_g > 0
        assert assessment.targets.fiber_g is None  # Optional / placeholder

        # All node results should be present and valid
        assert assessment.activity_result is not None
        assert assessment.rmr_result is not None
        assert assessment.rmr_result.status == RMRStatus.OK
        assert assessment.tdee_result is not None
        assert assessment.calorie_target_result is not None
        assert assessment.protein_result is not None
        assert assessment.protein_result.status == ProteinStatus.OK
        assert assessment.fat_result is not None
        assert assessment.carb_result is not None
        assert assessment.carb_result.status == CarbStatus.OK
        assert assessment.weight_target_result is not None
        assert assessment.fiber_result is not None

        # Traceability
        assert assessment.orchestrator_version == ORCHESTRATOR_VERSION
        assert assessment.policy_versions["activity"] == "activity-v1"
        assert assessment.policy_versions["rmr"] == "rmr-v1"
        assert assessment.policy_versions["tdee"] == "tdee-v1"
        assert assessment.policy_versions["calorie"] == "calorie-v1"
        assert assessment.policy_versions["protein"] == "protein-v1"
        assert assessment.policy_versions["fat"] == "fat-v1-rev1"
        assert assessment.policy_versions["carb"] == "carb-v1"
        assert assessment.policy_versions["weight_target"] == "weight-target-v1-rev1"
        assert assessment.policy_versions["fiber"] == "fiber-v1-placeholder"


# ---------------------------------------------------------------------------
# 2. ORCH-002: Low Calorie Review Trigger
# ---------------------------------------------------------------------------


class TestLowCalorieReview:
    def test_orch_002_low_calorie_review(self):
        """ORCH-002: Target < 1200 kcal yields REVIEW_REQUIRED but targets are still issued."""
        orchestrator = NutritionCoreOrchestrator()
        # Small female, sedentary, weight loss deficit: TDEE ~ 1400 -> Target ~ 900 (< 1200)
        survey = _make_survey(
            age=50,
            gender="female",
            height_cm=148.0,
            weight_kg=42.0,
            goal_type=GoalType.WEIGHT_LOSS,
            work_activity=ActivityCategory.SEDENTARY,
            training_days_per_week=0,
        )
        core_input = _make_core_input(survey=survey)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.REVIEW_REQUIRED
        assert LOW_CALORIE_REVIEW_REQUIRED in assessment.review_flags
        # Crucial Option B requirement: targets are STILL issued!
        assert assessment.targets is not None
        assert assessment.targets.calories_kcal < 1200
        assert assessment.targets.protein_g > 0
        assert assessment.targets.fat_g > 0
        assert assessment.targets.carbohydrates_g is not None


# ---------------------------------------------------------------------------
# 3. ORCH-003: InBody Discrepancy
# ---------------------------------------------------------------------------


class TestInBodyMismatch:
    def test_orch_003_inbody_weight_mismatch(self):
        """ORCH-003: InBody weight differs -> REVIEW_REQUIRED + flag; calculation mass unchanged."""
        orchestrator = NutritionCoreOrchestrator()
        survey = _make_survey(weight_kg=75.0)
        inbody = InBodySnapshot(weight_kg=72.0)  # 3 kg difference

        core_input = _make_core_input(survey=survey, inbody=inbody)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.REVIEW_REQUIRED
        assert INBODY_WEIGHT_MISMATCH in assessment.review_flags
        # Resolved weight MUST NOT be altered by InBody
        assert assessment.resolved_current_weight_kg == 75.0
        # Targets are preserved
        assert assessment.targets is not None
        assert assessment.targets.calories_kcal > 0

    def test_inbody_identical_weight_no_mismatch(self):
        """When InBody weight matches resolved weight exactly, no flag is emitted."""
        orchestrator = NutritionCoreOrchestrator()
        survey = _make_survey(weight_kg=75.0)
        inbody = InBodySnapshot(weight_kg=75.0)

        core_input = _make_core_input(survey=survey, inbody=inbody)
        assessment = orchestrator.assess(core_input)

        assert INBODY_WEIGHT_MISMATCH not in assessment.review_flags
        assert assessment.overall_status == CoreAssessmentStatus.COMPLETE


# ---------------------------------------------------------------------------
# 4. ORCH-004: Activity Incomplete
# ---------------------------------------------------------------------------


class TestActivityIncomplete:
    def test_orch_004_activity_incomplete(self):
        """ORCH-004: Incomplete activity input -> Core INCOMPLETE; targets None; independent nodes preserved."""
        orchestrator = NutritionCoreOrchestrator()
        # Missing training_duration_minutes when training_days > 0 causes ActivityClassifier INCOMPLETE
        activity_inp = ActivityClassificationInput(
            occupational_activity=OccupationalActivity.SEDENTARY,
            daily_movement=DailyMovement.LOW,
            training_days_per_week=3,
            training_duration_minutes=None,  # triggers INCOMPLETE
        )
        core_input = _make_core_input(activity_input=activity_inp)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.INCOMPLETE
        # Option B gate: targets must NOT be issued
        assert assessment.targets is None

        # Activity node ran and recorded INCOMPLETE
        assert assessment.activity_result is not None
        assert assessment.activity_result.status == "INCOMPLETE"

        # Independent nodes preserved
        assert assessment.rmr_result is not None
        assert assessment.rmr_result.status == RMRStatus.OK
        assert assessment.protein_result is not None
        assert assessment.protein_result.status == ProteinStatus.OK

        # Downstream energy chain skipped
        assert assessment.tdee_result is None
        assert assessment.calorie_target_result is None
        assert assessment.fat_result is None
        assert assessment.carb_result is None


# ---------------------------------------------------------------------------
# 5. ORCH-005: RMR Invalid (Underage)
# ---------------------------------------------------------------------------


class TestRMRInvalid:
    def test_orch_005_rmr_invalid(self):
        """ORCH-005: Underage age=16 -> RMR INVALID; Core INVALID; targets None; protein preserved."""
        orchestrator = NutritionCoreOrchestrator()
        survey = _make_survey(age=16)  # rmr-v1 only supports age >= 18
        core_input = _make_core_input(survey=survey)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.INVALID
        assert assessment.targets is None

        assert assessment.rmr_result is not None
        assert assessment.rmr_result.status == RMRStatus.INVALID
        assert "UNDERAGE_NOT_SUPPORTED" in assessment.issues

        # Energy chain skipped
        assert assessment.tdee_result is None
        assert assessment.calorie_target_result is None
        assert assessment.fat_result is None
        assert assessment.carb_result is None

        # Independent Protein node preserved!
        assert assessment.protein_result is not None
        assert assessment.protein_result.status == ProteinStatus.OK


# ---------------------------------------------------------------------------
# 6. ORCH-006: Activity Conflict
# ---------------------------------------------------------------------------


class TestActivityConflict:
    def test_orch_006_activity_conflict(self):
        """ORCH-006: Contradictory activity inputs -> Activity CONFLICT -> Core INVALID; targets None."""
        orchestrator = NutritionCoreOrchestrator()
        # activity-v1 conflict rule: training_days == 0 AND intensity in
        # {LIGHT, MODERATE, VIGOROUS} -> CONFLICT
        activity_inp = ActivityClassificationInput(
            occupational_activity=OccupationalActivity.HEAVY_MANUAL,
            daily_movement=DailyMovement.LOW,
            training_days_per_week=0,
            exercise_intensity=ExerciseIntensity.MODERATE,
        )
        core_input = _make_core_input(activity_input=activity_inp)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.INVALID
        assert assessment.targets is None
        assert assessment.activity_result is not None
        assert assessment.activity_result.status == "CONFLICT"


# ---------------------------------------------------------------------------
# 7. ORCH-007: Carb Invalid (Negative Residual)
# ---------------------------------------------------------------------------


class TestCarbInvalid:
    def test_orch_007_carb_invalid_negative_residual(self):
        """ORCH-007: Negative residual -> Carb INVALID -> Core INVALID; targets None; negative residual preserved."""
        orchestrator = NutritionCoreOrchestrator()
        # Small/older female, weight loss, sedentary:
        # low target calories vs protein (1.6 g/kg) + fat (25%) energy
        # yields residual_calories < 0 under carb-v1.
        survey = _make_survey(
            age=70,
            gender="female",
            height_cm=130.0,
            weight_kg=35.0,
            goal_type=GoalType.WEIGHT_LOSS,
            work_activity=ActivityCategory.SEDENTARY,
            training_days_per_week=0,
        )
        core_input = _make_core_input(survey=survey)
        assessment = orchestrator.assess(core_input)

        assert assessment.overall_status == CoreAssessmentStatus.INVALID
        assert assessment.targets is None
        assert assessment.carb_result is not None
        assert assessment.carb_result.status == CarbStatus.INVALID
        # Exact negative residual must be preserved
        assert assessment.carb_result.residual_calories < 0
        assert assessment.carb_result.carbohydrates_g is None


# ---------------------------------------------------------------------------
# 8. ORCH-008: Contract Immutability
# ---------------------------------------------------------------------------


class TestContractImmutability:
    def test_orch_008_frozen_contracts(self):
        """ORCH-008: NutritionCoreInput, NutritionAssessment, NutritionTargets cannot be mutated."""
        core_input = _make_core_input()
        with pytest.raises(ValidationError):
            core_input.nutrition_input = _make_survey()

        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(core_input)

        with pytest.raises(ValidationError):
            assessment.overall_status = CoreAssessmentStatus.INVALID
        with pytest.raises(ValidationError):
            assessment.resolved_current_weight_kg = 999.0
        with pytest.raises(ValidationError):
            assessment.targets = None

        targets = assessment.targets
        with pytest.raises(ValidationError):
            targets.calories_kcal = 1000.0


# ---------------------------------------------------------------------------
# 9. ORCH-009: Extra Fields Forbidden
# ---------------------------------------------------------------------------


class TestExtraFieldsForbidden:
    def test_orch_009_extra_fields(self):
        """ORCH-009: Extra fields raise ValidationError."""
        profile = _make_profile()
        survey = _make_survey()

        with pytest.raises(ValidationError):
            NutritionCoreInput(
                client_profile=profile,
                nutrition_input=survey,
                forbidden_extra="invalid",  # type: ignore[call-arg]
            )

        with pytest.raises(ValidationError):
            NutritionTargets(
                calories_kcal=2000,
                protein_g=150,
                fat_g=60,
                carbohydrates_g=200,
                unknown_extra=123,  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# 10. ORCH-010: Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_orch_010_idempotent_execution(self):
        """ORCH-010: Consecutive executions on identical input yield byte-identical payloads."""
        orchestrator = NutritionCoreOrchestrator()
        core_input = _make_core_input()

        res1 = orchestrator.assess(core_input)
        res2 = orchestrator.assess(core_input)

        assert res1.model_dump() == res2.model_dump()


# ---------------------------------------------------------------------------
# 11. Weight Authority Precedence & Unresolved Mass
# ---------------------------------------------------------------------------


class TestWeightAuthorityPrecedence:
    def test_survey_weight_wins_over_profile(self):
        """Survey weight is authoritative when profile weight is also present."""
        profile = _make_profile(personal_kwargs={"weight_kg": 85.0})
        survey = _make_survey(weight_kg=75.0)

        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(_make_core_input(profile=profile, survey=survey))

        assert assessment.resolved_current_weight_kg == 75.0
        assert assessment.weight_authority_source == WeightAuthoritySource.SURVEY

    def test_profile_prefill_source_recording(self):
        """Explicit prefill source is preserved in assessment."""
        profile = _make_profile(personal_kwargs={"weight_kg": 80.0})
        survey = _make_survey(weight_kg=80.0)

        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(
            _make_core_input(
                profile=profile,
                survey=survey,
                weight_source=WeightAuthoritySource.PROFILE_PREFILL,
            )
        )
        assert assessment.resolved_current_weight_kg == 80.0
        assert assessment.weight_authority_source == WeightAuthoritySource.PROFILE_PREFILL

    def test_prefill_survey_weight_helper(self):
        """Helper correctly determines source."""
        # 1. Survey available
        w, src = prefill_survey_weight(70.0, _make_profile(personal_kwargs={"weight_kg": 80.0}))
        assert w == 70.0
        assert src == WeightAuthoritySource.SURVEY

        # 2. Survey missing, profile available
        w, src = prefill_survey_weight(None, _make_profile(personal_kwargs={"weight_kg": 80.0}))
        assert w == 80.0
        assert src == WeightAuthoritySource.PROFILE_PREFILL

        # 3. Both missing
        w, src = prefill_survey_weight(None, _make_profile(personal_kwargs={"weight_kg": None}))
        assert w is None
        assert src == WeightAuthoritySource.UNRESOLVED

    def test_profile_prefill_regression_three_way_precedence(self):
        """Regression: PROFILE_PREFILL is pre-assembly fill only — never a runtime override.

        Proves:
        1. Survey weight present -> SURVEY (profile must not replace it).
        2. Survey weight missing + profile weight -> PROFILE_PREFILL via
           prefill_survey_weight before NutritionAssessmentInput construction.
        3. Neither -> UNRESOLVED.
        4. Forced PROFILE_PREFILL only records lineage; resolved mass still
           comes from the survey input, not ClientProfile.personal.weight_kg.
        """
        # 1. Survey present wins; profile difference is ignored
        w, src = prefill_survey_weight(
            75.0, _make_profile(personal_kwargs={"weight_kg": 99.0})
        )
        assert w == 75.0
        assert src == WeightAuthoritySource.SURVEY

        profile = _make_profile(personal_kwargs={"weight_kg": 99.0})
        survey = _make_survey(weight_kg=75.0)
        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(
            _make_core_input(profile=profile, survey=survey)
        )
        assert assessment.resolved_current_weight_kg == 75.0
        assert assessment.weight_authority_source == WeightAuthoritySource.SURVEY

        # 2. Survey missing -> pre-assembly fill from profile, then construct input
        filled_weight, filled_src = prefill_survey_weight(
            None, _make_profile(personal_kwargs={"weight_kg": 80.0})
        )
        assert filled_weight == 80.0
        assert filled_src == WeightAuthoritySource.PROFILE_PREFILL

        prefill_survey = _make_survey(weight_kg=filled_weight)
        prefill_assessment = orchestrator.assess(
            _make_core_input(
                survey=prefill_survey,
                weight_source=filled_src,
            )
        )
        assert prefill_assessment.resolved_current_weight_kg == 80.0
        assert prefill_assessment.weight_authority_source == (
            WeightAuthoritySource.PROFILE_PREFILL
        )

        # 3. Neither source -> UNRESOLVED
        w, src = prefill_survey_weight(
            None, _make_profile(personal_kwargs={"weight_kg": None})
        )
        assert w is None
        assert src == WeightAuthoritySource.UNRESOLVED

        # 4. Forced PROFILE_PREFILL must NOT swap in profile weight at runtime
        runtime_assessment = orchestrator.assess(
            _make_core_input(
                profile=_make_profile(personal_kwargs={"weight_kg": 99.0}),
                survey=_make_survey(weight_kg=75.0),
                weight_source=WeightAuthoritySource.PROFILE_PREFILL,
            )
        )
        assert runtime_assessment.resolved_current_weight_kg == 75.0
        assert runtime_assessment.weight_authority_source == (
            WeightAuthoritySource.PROFILE_PREFILL
        )

    def test_unresolved_weight_blocks_dependent_nodes(self):
        """Unresolved weight sets Core INCOMPLETE, blocks RMR/Protein, preserves Activity."""
        survey = _make_survey()
        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(
            _make_core_input(
                survey=survey,
                weight_source=WeightAuthoritySource.UNRESOLVED,
            )
        )

        assert assessment.overall_status == CoreAssessmentStatus.INCOMPLETE
        assert assessment.resolved_current_weight_kg is None
        assert assessment.weight_authority_source == WeightAuthoritySource.UNRESOLVED
        assert "MISSING_WEIGHT" in assessment.issues
        assert assessment.targets is None

        # Weight-dependent nodes skipped
        assert assessment.rmr_result is None
        assert assessment.protein_result is None
        assert assessment.weight_target_result is None
        # Activity executed
        assert assessment.activity_result is not None


# ---------------------------------------------------------------------------
# 12. Fiber Independence
# ---------------------------------------------------------------------------


class TestFiberIndependence:
    def test_fiber_neutrality(self):
        """Fiber placeholder does not contribute to Core status or block macros."""
        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(_make_core_input())

        assert assessment.overall_status == CoreAssessmentStatus.COMPLETE
        assert assessment.fiber_result is not None
        assert assessment.fiber_result.status == "NOT_IMPLEMENTED"
        assert assessment.targets is not None
        assert assessment.targets.fiber_g is None


# ---------------------------------------------------------------------------
# 13. Injury Isolation (Context Only)
# ---------------------------------------------------------------------------


class TestInjuryIsolation:
    def test_injury_does_not_affect_macro_calculation(self):
        """Injuries in profile must not alter calculated calories or macros."""
        orchestrator = NutritionCoreOrchestrator()
        survey = _make_survey()

        # Run A: No injuries
        profile_a = _make_profile(health_kwargs={"injuries": []})
        res_a = orchestrator.assess(_make_core_input(profile=profile_a, survey=survey))

        # Run B: With multiple reported injuries
        profile_b = _make_profile(
            health_kwargs={"injuries": ["left_knee_acl_tear", "lumbar_disc_herniation"]}
        )
        res_b = orchestrator.assess(_make_core_input(profile=profile_b, survey=survey))

        # Macro targets must be 100% BITWISE IDENTICAL
        assert res_a.targets.calories_kcal == res_b.targets.calories_kcal
        assert res_a.targets.protein_g == res_b.targets.protein_g
        assert res_a.targets.fat_g == res_b.targets.fat_g
        assert res_a.targets.carbohydrates_g == res_b.targets.carbohydrates_g

        # Injuries must be preserved in planning context
        ctx_b = build_planning_context(res_b)
        assert ctx_b is not None
        assert "left_knee_acl_tear" in ctx_b.injuries


# ---------------------------------------------------------------------------
# 14. Planning Gate & Context Assembly
# ---------------------------------------------------------------------------


class TestPlanningGate:
    def test_planning_gate_allowed(self):
        orchestrator = NutritionCoreOrchestrator()
        assessment = orchestrator.assess(_make_core_input())
        assert is_planning_allowed(assessment.targets) is True

        ctx = build_planning_context(assessment)
        assert ctx is not None
        assert ctx.targets == assessment.targets
        assert ctx.current_weight_kg == 75.0

    def test_planning_gate_disallowed_on_failure(self):
        orchestrator = NutritionCoreOrchestrator()
        survey = _make_survey(age=16)  # invalid RMR
        assessment = orchestrator.assess(_make_core_input(survey=survey))

        assert is_planning_allowed(assessment.targets) is False
        assert build_planning_context(assessment) is None


# ---------------------------------------------------------------------------
# 15. Source Isolation (No Clock, Random, Network, DB)
# ---------------------------------------------------------------------------


class TestSourceIsolation:
    def test_orchestrator_source_isolation(self):
        """Orchestrator module must not depend on clock, random, network, or DB."""
        import app.nutrition.orchestrator.orchestrator as orch_mod
        import app.nutrition.orchestrator.resolver as res_mod

        for mod in (orch_mod, res_mod):
            source = inspect.getsource(mod)
            assert "datetime.now" not in source
            assert "time.time" not in source
            assert "import random" not in source
            assert "uuid" not in source
            for token in ("httpx", "httpcore", "requests", "aiohttp", "sqlite", "sqlalchemy"):
                assert token not in source
