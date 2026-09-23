"""Nutrition Core Orchestrator — Milestone 2.2.9.

Deterministic Layer B composition and coordination service.
Orchestrates:
- activity-v1
- rmr-v1
- tdee-v1
- calorie-v1
- protein-v1
- fat-v1-rev1
- carb-v1
- weight-target-v1-rev1
- fiber-v1-placeholder

Strictly maintains Layer A / Layer B boundary:
- Performs ZERO mathematical calculations.
- Synchronous, in-process, deterministic execution.
- No LLM, network, database, clock, or randomness.
"""

from typing import Dict, List, Optional

from app.nutrition.activity import (
    ACTIVITY_POLICY_VERSION,
    ActivityClassificationResult,
    ActivityClassifier,
    get_activity_factor,
)
from app.nutrition.calorie_target import (
    CALORIE_TARGET_POLICY_VERSION,
    LOW_CALORIE_REVIEW_REQUIRED,
    CalorieTargetInput,
    CalorieTargetResult,
    CalorieTargetStatus,
    calculate_calorie_target,
)
from app.nutrition.carbohydrate import (
    CARB_POLICY_VERSION,
    CarbInput,
    CarbResult,
    CarbStatus,
    calculate_carbohydrates,
)
from app.nutrition.fat import (
    FAT_POLICY_VERSION,
    FatResult,
    FatStatus,
    build_fat_input,
    calculate_fat,
)
from app.nutrition.models import (
    ActivityCategory,
    ActivityClassificationStatus,
)
from app.nutrition.orchestrator.contracts import (
    STATUS_PRECEDENCE,
    CoreAssessmentStatus,
    FiberResult,
    NutritionAssessment,
    NutritionCoreInput,
    NutritionTargets,
    WeightAuthoritySource,
)
from app.nutrition.orchestrator.mappers import map_goal_to_weight_target_goal
from app.nutrition.orchestrator.resolver import WeightAuthorityResolver
from app.nutrition.protein import (
    PROTEIN_POLICY_VERSION,
    ProteinResult,
    ProteinStatus,
    build_protein_input,
    calculate_protein,
)
from app.nutrition.rmr import (
    RMR_POLICY_VERSION,
    RMRCalculator,
    RMRMapper,
    RMRResult,
    RMRStatus,
)
from app.nutrition.tdee import (
    TDEE_POLICY_VERSION,
    TDEEInput,
    TDEEResult,
    TDEEStatus,
    calculate_tdee,
)
from app.nutrition.weight_target import (
    WEIGHT_TARGET_POLICY_VERSION,
    WeightTargetInput,
    WeightTargetResult,
    WeightTargetStatus,
    determine_weight_targets,
)

ORCHESTRATOR_VERSION: str = "2.2.9"


class NutritionCoreOrchestrator:
    """Layer B composition service coordinating deterministic nutrition calculators."""

    def __init__(self) -> None:
        self._resolver = WeightAuthorityResolver()
        self._activity_classifier = ActivityClassifier()
        self._rmr_mapper = RMRMapper()
        self._rmr_calculator = RMRCalculator()

    def assess(self, input_data: NutritionCoreInput) -> NutritionAssessment:
        """Execute deterministic nutrition DAG and assemble assessment record.

        Args:
            input_data: Validated, frozen composite input.

        Returns:
            NutritionAssessment preserving all executed node results, aggregated
            status, consolidated review flags, and Option B NutritionTargets.
        """
        issues: List[str] = []
        warnings: List[str] = []
        review_flags: List[str] = []
        contributions: List[CoreAssessmentStatus] = []

        # -------------------------------------------------------------------
        # Step 1: Current Weight Authority Resolution
        # -------------------------------------------------------------------
        weight_res = self._resolver.resolve(
            nutrition_input=input_data.nutrition_input,
            client_profile=input_data.client_profile,
            inbody_snapshot=input_data.inbody_snapshot,
            forced_source=input_data.weight_authority_source,
        )

        resolved_weight_kg = weight_res.resolved_weight_kg
        weight_source = weight_res.source
        review_flags.extend(weight_res.review_flags)

        if weight_source == WeightAuthoritySource.UNRESOLVED or resolved_weight_kg is None:
            contributions.append(CoreAssessmentStatus.INCOMPLETE)
            issues.append("MISSING_WEIGHT")
        else:
            contributions.append(CoreAssessmentStatus.COMPLETE)

        # -------------------------------------------------------------------
        # Step 2: Stage 1 Independent Nodes
        # -------------------------------------------------------------------

        # A. Activity Classifier
        if input_data.activity_input is not None:
            activity_result: Optional[ActivityClassificationResult] = (
                self._activity_classifier.classify(input_data.activity_input)
            )
            if activity_result is not None:
                issues.extend(activity_result.issues)
                if activity_result.status == ActivityClassificationStatus.OK:
                    contributions.append(CoreAssessmentStatus.COMPLETE)
                elif activity_result.status == ActivityClassificationStatus.INCOMPLETE:
                    contributions.append(CoreAssessmentStatus.INCOMPLETE)
                elif activity_result.status == ActivityClassificationStatus.CONFLICT:
                    contributions.append(CoreAssessmentStatus.INVALID)
                elif activity_result.status == ActivityClassificationStatus.ERROR:
                    contributions.append(CoreAssessmentStatus.ERROR)
        else:
            # Survey work_activity pre-classified path
            work_cat = input_data.nutrition_input.work_activity
            factor = get_activity_factor(work_cat)
            activity_result = ActivityClassificationResult(
                status=ActivityClassificationStatus.OK,
                issues=[],
                activity_category=work_cat,
                activity_factor=factor,
            )
            contributions.append(CoreAssessmentStatus.COMPLETE)

        # B. RMR Calculator (weight-dependent)
        rmr_result: Optional[RMRResult] = None
        if resolved_weight_kg is not None:
            rmr_mapped = self._rmr_mapper.map_from_dict(
                {
                    "age": input_data.nutrition_input.age,
                    "gender": input_data.nutrition_input.gender,
                    "height_cm": input_data.nutrition_input.height_cm,
                    "weight_kg": resolved_weight_kg,
                }
            )
            if isinstance(rmr_mapped, RMRResult):
                rmr_result = rmr_mapped
            else:
                rmr_result = self._rmr_calculator.calculate(rmr_mapped)

            if rmr_result is not None:
                issues.extend(rmr_result.issues)
                if rmr_result.status == RMRStatus.OK:
                    contributions.append(CoreAssessmentStatus.COMPLETE)
                elif rmr_result.status == RMRStatus.INCOMPLETE:
                    contributions.append(CoreAssessmentStatus.INCOMPLETE)
                elif rmr_result.status == RMRStatus.INVALID:
                    contributions.append(CoreAssessmentStatus.INVALID)
                elif rmr_result.status == RMRStatus.ERROR:
                    contributions.append(CoreAssessmentStatus.ERROR)

        # C. Protein Calculator (weight-dependent)
        protein_result: Optional[ProteinResult] = None
        if resolved_weight_kg is not None:
            p_input = build_protein_input(
                current_weight_kg=resolved_weight_kg,
                goal=input_data.nutrition_input.goal_type,
            )
            protein_result = calculate_protein(p_input)
            issues.extend(i.value for i in protein_result.issues)
            if protein_result.status == ProteinStatus.OK:
                contributions.append(CoreAssessmentStatus.COMPLETE)
            elif protein_result.status == ProteinStatus.INCOMPLETE:
                contributions.append(CoreAssessmentStatus.INCOMPLETE)
            elif protein_result.status == ProteinStatus.INVALID:
                contributions.append(CoreAssessmentStatus.INVALID)
            elif protein_result.status == ProteinStatus.ERROR:
                contributions.append(CoreAssessmentStatus.ERROR)

        # D. Weight Target Calculator (weight-dependent, independent of macros)
        weight_target_result: Optional[WeightTargetResult] = None
        if resolved_weight_kg is not None:
            wt_goal = map_goal_to_weight_target_goal(input_data.nutrition_input.goal_type)
            if wt_goal is not None:
                wt_input = WeightTargetInput(
                    age_years=input_data.nutrition_input.age,
                    height_cm=input_data.nutrition_input.height_cm,
                    current_weight_kg=resolved_weight_kg,
                    goal=wt_goal,
                    user_requested_target_weight_kg=input_data.nutrition_input.target_weight_kg,
                )
                weight_target_result = determine_weight_targets(wt_input)
                review_flags.extend(f.value for f in weight_target_result.review_flags)
                warnings.extend(f.value for f in weight_target_result.validation_flags)

                if weight_target_result.status == WeightTargetStatus.OK:
                    contributions.append(CoreAssessmentStatus.COMPLETE)
                elif weight_target_result.status == WeightTargetStatus.REVIEW_REQUIRED:
                    contributions.append(CoreAssessmentStatus.REVIEW_REQUIRED)
                elif weight_target_result.status == WeightTargetStatus.ERROR:
                    contributions.append(CoreAssessmentStatus.ERROR)

        # -------------------------------------------------------------------
        # Step 3: Stage 2 TDEE Calculation (Activity + RMR)
        # -------------------------------------------------------------------
        tdee_result: Optional[TDEEResult] = None
        if (
            activity_result is not None
            and activity_result.status == ActivityClassificationStatus.OK
            and rmr_result is not None
            and rmr_result.status == RMRStatus.OK
        ):
            tdee_input = TDEEInput(rmr_result=rmr_result, activity_result=activity_result)
            tdee_result = calculate_tdee(tdee_input)
            issues.extend(tdee_result.issues)
            if tdee_result.status == TDEEStatus.OK:
                contributions.append(CoreAssessmentStatus.COMPLETE)
            elif tdee_result.status == TDEEStatus.INCOMPLETE:
                contributions.append(CoreAssessmentStatus.INCOMPLETE)
            elif tdee_result.status == TDEEStatus.INVALID:
                contributions.append(CoreAssessmentStatus.INVALID)
            elif tdee_result.status == TDEEStatus.ERROR:
                contributions.append(CoreAssessmentStatus.ERROR)

        # -------------------------------------------------------------------
        # Step 4: Stage 3 Calorie Target Calculation (TDEE + Goal)
        # -------------------------------------------------------------------
        calorie_target_result: Optional[CalorieTargetResult] = None
        if (
            tdee_result is not None
            and tdee_result.status == TDEEStatus.OK
            and tdee_result.tdee_kcal is not None
        ):
            cal_input = CalorieTargetInput(
                tdee_result=tdee_result,
                goal_type=input_data.nutrition_input.goal_type,
            )
            calorie_target_result = calculate_calorie_target(cal_input)
            issues.extend(calorie_target_result.issues)

            if calorie_target_result.status == CalorieTargetStatus.OK:
                if LOW_CALORIE_REVIEW_REQUIRED in calorie_target_result.safety_flags:
                    contributions.append(CoreAssessmentStatus.REVIEW_REQUIRED)
                    review_flags.append(LOW_CALORIE_REVIEW_REQUIRED)
                else:
                    contributions.append(CoreAssessmentStatus.COMPLETE)
            elif calorie_target_result.status == CalorieTargetStatus.INCOMPLETE:
                contributions.append(CoreAssessmentStatus.INCOMPLETE)
            elif calorie_target_result.status == CalorieTargetStatus.INVALID:
                contributions.append(CoreAssessmentStatus.INVALID)
            elif calorie_target_result.status == CalorieTargetStatus.ERROR:
                contributions.append(CoreAssessmentStatus.ERROR)

        # -------------------------------------------------------------------
        # Step 5: Stage 4 Fat Target Calculation (Calorie Target + Goal)
        # -------------------------------------------------------------------
        fat_result: Optional[FatResult] = None
        if (
            calorie_target_result is not None
            and calorie_target_result.status == CalorieTargetStatus.OK
            and calorie_target_result.target_calories_kcal is not None
        ):
            fat_input = build_fat_input(
                target_calories=calorie_target_result.target_calories_kcal,
                goal=input_data.nutrition_input.goal_type,
            )
            fat_result = calculate_fat(fat_input)
            issues.extend(i.value for i in fat_result.issues)
            if fat_result.status == FatStatus.OK:
                contributions.append(CoreAssessmentStatus.COMPLETE)
            elif fat_result.status == FatStatus.INCOMPLETE:
                contributions.append(CoreAssessmentStatus.INCOMPLETE)
            elif fat_result.status == FatStatus.INVALID:
                contributions.append(CoreAssessmentStatus.INVALID)
            elif fat_result.status == FatStatus.ERROR:
                contributions.append(CoreAssessmentStatus.ERROR)

        # -------------------------------------------------------------------
        # Step 6: Stage 5 Carbohydrate Calculation (Calories + Protein + Fat)
        # -------------------------------------------------------------------
        carb_result: Optional[CarbResult] = None
        if (
            calorie_target_result is not None
            and calorie_target_result.status == CalorieTargetStatus.OK
            and calorie_target_result.target_calories_kcal is not None
            and protein_result is not None
            and protein_result.status == ProteinStatus.OK
            and protein_result.protein_g is not None
            and fat_result is not None
            and fat_result.status == FatStatus.OK
            and fat_result.fat_calories is not None
        ):
            c_input = CarbInput(
                target_calories=calorie_target_result.target_calories_kcal,
                protein_g=protein_result.protein_g,
                fat_calories=fat_result.fat_calories,
            )
            carb_result = calculate_carbohydrates(c_input)
            issues.extend(i.value for i in carb_result.issues)
            if carb_result.status == CarbStatus.OK:
                contributions.append(CoreAssessmentStatus.COMPLETE)
            elif carb_result.status == CarbStatus.INVALID:
                contributions.append(CoreAssessmentStatus.INVALID)

        # -------------------------------------------------------------------
        # Step 7: Fiber Placeholder (neutral to status)
        # -------------------------------------------------------------------
        fiber_result = FiberResult(
            status="NOT_IMPLEMENTED",
            fiber_g=None,
            policy_version="fiber-v1-placeholder",
        )

        # -------------------------------------------------------------------
        # Step 8: Macro Chain Completeness
        # -------------------------------------------------------------------
        # If any required macro node was skipped, contribute INCOMPLETE
        if (
            calorie_target_result is None
            or protein_result is None
            or fat_result is None
            or carb_result is None
        ):
            contributions.append(CoreAssessmentStatus.INCOMPLETE)

        # -------------------------------------------------------------------
        # Step 9: Status Aggregation via Locked Precedence
        # -------------------------------------------------------------------
        # Sort contributions by precedence descending (highest precedence first)
        sorted_contributions = sorted(
            contributions,
            key=lambda s: STATUS_PRECEDENCE[s],
            reverse=True,
        )
        highest_status = sorted_contributions[0] if sorted_contributions else CoreAssessmentStatus.COMPLETE

        # If highest status is COMPLETE but review_flags exist, upgrade to REVIEW_REQUIRED
        if highest_status == CoreAssessmentStatus.COMPLETE and review_flags:
            overall_status = CoreAssessmentStatus.REVIEW_REQUIRED
        else:
            overall_status = highest_status

        # -------------------------------------------------------------------
        # Step 10: Option B NutritionTargets Assembly
        # -------------------------------------------------------------------
        targets: Optional[NutritionTargets] = None
        if (
            calorie_target_result is not None
            and calorie_target_result.status == CalorieTargetStatus.OK
            and calorie_target_result.target_calories_kcal is not None
            and protein_result is not None
            and protein_result.status == ProteinStatus.OK
            and protein_result.protein_g is not None
            and fat_result is not None
            and fat_result.status == FatStatus.OK
            and fat_result.fat_g is not None
            and carb_result is not None
            and carb_result.status == CarbStatus.OK
            and carb_result.carbohydrates_g is not None
        ):
            targets = NutritionTargets(
                calories_kcal=float(calorie_target_result.target_calories_kcal),
                protein_g=float(protein_result.protein_g),
                fat_g=float(fat_result.fat_g),
                carbohydrates_g=float(carb_result.carbohydrates_g),
                fiber_g=None,
            )

        policy_versions: Dict[str, str] = {
            "activity": ACTIVITY_POLICY_VERSION,
            "rmr": RMR_POLICY_VERSION,
            "tdee": TDEE_POLICY_VERSION,
            "calorie": CALORIE_TARGET_POLICY_VERSION,
            "protein": PROTEIN_POLICY_VERSION,
            "fat": FAT_POLICY_VERSION,
            "carb": CARB_POLICY_VERSION,
            "weight_target": WEIGHT_TARGET_POLICY_VERSION,
            "fiber": "fiber-v1-placeholder",
        }

        # Deduplicate diagnostic lists while preserving order
        unique_issues = list(dict.fromkeys(issues))
        unique_warnings = list(dict.fromkeys(warnings))
        unique_review_flags = list(dict.fromkeys(review_flags))

        return NutritionAssessment(
            overall_status=overall_status,
            input_snapshot=input_data,
            resolved_current_weight_kg=resolved_weight_kg,
            weight_authority_source=weight_source,
            targets=targets,
            activity_result=activity_result,
            rmr_result=rmr_result,
            tdee_result=tdee_result,
            calorie_target_result=calorie_target_result,
            protein_result=protein_result,
            fat_result=fat_result,
            carb_result=carb_result,
            weight_target_result=weight_target_result,
            fiber_result=fiber_result,
            issues=unique_issues,
            warnings=unique_warnings,
            review_flags=unique_review_flags,
            orchestrator_version=ORCHESTRATOR_VERSION,
            policy_versions=policy_versions,
        )
