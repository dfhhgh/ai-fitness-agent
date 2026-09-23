"""Deterministic Fat Calculator — fat-v1-rev1 (Layer A pure calculator).

Policy version: fat-v1-rev1

Formula (five-stage pipeline, goal-invariant 25%):
    Stage 1: fat_calories_unrounded = target_calories * 0.25
    Stage 2: fat_mass_unrounded     = fat_calories_unrounded / 9
    Stage 3: fat_g = Decimal(str(mass)).quantize(1, ROUND_HALF_UP) -> int
    Stage 4: fat_calories = fat_g * 9
    Stage 5: effective_fat_percentage =
                 float((Decimal(fat_calories) / Decimal(target_calories))
                       .quantize(0.000001, ROUND_HALF_UP))

Goal invariance (locked):
    MAINTENANCE / WEIGHT_LOSS / WEIGHT_GAIN / MUSCLE_GAIN -> 0.25 energy

Calorie engineering domain:
    target_calories >= 1

Layer A / Layer B boundary:
    - Layer A: pure calculator on FatInput -> frozen FatResult.
      No medical screening, no body-weight floor, no RMR/TDEE/
      calorie/activity recalculation, no LLM/network/clock.
    - Layer B: maps shared GoalType -> FatGoal 1:1, extracts calories,
      screens clinical conditions, binds fat_g into NutritionTargets
      only when status == OK.

Schema vs domain (OPTION A):
    - Schema violations (string/bool/float/NaN/Inf/invalid enum/extra)
      raise Pydantic ValidationError — never FatResult.
    - Domain violations on a valid FatInput return FatResult with
      INCOMPLETE/INVALID statuses and issue codes.
    - Unsupported goal reaching the calculator via model_construct
      bypass raises ValueError — never falls through to maintenance.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.nutrition.models import GoalType
from app.nutrition.fat.models import (
    FatGoal,
    FatInput,
    FatIssueCode,
    FatResult,
    FatStatus,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

FAT_POLICY_VERSION: str = "fat-v1-rev1"

FAT_ENERGY_FRACTION: float = 0.25
ATWATER_FACTOR: float = 9.0

TARGET_CALORIES_DOMAIN_MIN: int = 1

OUTPUT_QUANTUM: str = "1"
PERCENTAGE_QUANTUM: str = "0.000001"

FAT_FRACTION_DECIMAL = Decimal("0.25")
ATWATER_DECIMAL = Decimal("9")
ONE_DECIMAL = Decimal(OUTPUT_QUANTUM)
SIX_DP_DECIMAL = Decimal(PERCENTAGE_QUANTUM)


def get_fat_energy_fraction(goal: FatGoal) -> Decimal:
    """Return the locked fat energy fraction for a Layer A goal.

    Goal invariance: every supported goal uses the same 25% fraction.
    Raises ValueError for any non-FatGoal — never falls through to a
    default/maintenance fraction.
    """
    if isinstance(goal, FatGoal):
        return FAT_FRACTION_DECIMAL
    raise ValueError(f"Unsupported goal for fat-v1-rev1: {goal!r}")


def _round_fat_grams(value: float) -> int:
    """Round an unrounded mass to integer grams (Decimal ROUND_HALF_UP).

    Uses Decimal(str(value)) so the decimal string representation is the
    rounding boundary (avoids binary float artifacts). This is
    arithmetic half-up, NOT Python's default round-half-even.
    """
    quantized = Decimal(str(value)).quantize(
        ONE_DECIMAL,
        rounding=ROUND_HALF_UP,
    )
    return int(quantized)


def _quantize_effective_percentage(
    fat_calories: int,
    target_calories: int,
) -> float:
    """Exact fat_calories / target_calories quantized to 6 decimal places.

    Stage 5 precision contract:
        1. Exact fraction via Decimal division
        2. quantize(Decimal('0.000001'), ROUND_HALF_UP)
        3. float() emission (trailing zeroes drop naturally)
    """
    exact = Decimal(fat_calories) / Decimal(target_calories)
    quantized = exact.quantize(SIX_DP_DECIMAL, rounding=ROUND_HALF_UP)
    return float(quantized)


def _goal_echo(goal: object) -> FatGoal | None:
    """Echo goal only when it is a valid FatGoal instance."""
    if isinstance(goal, FatGoal):
        return goal
    return None


def _calories_echo(target_calories: object) -> int | None:
    """Echo calories only when the value is domain-valid.

    bool is a subclass of int — guard so True never echoes as calories.
    Domain-valid means int and >= TARGET_CALORIES_DOMAIN_MIN.
    """
    if isinstance(target_calories, bool):
        return None
    if isinstance(target_calories, int):
        if target_calories >= TARGET_CALORIES_DOMAIN_MIN:
            return target_calories
    return None


def _result(
    *,
    status: FatStatus,
    issues: tuple[FatIssueCode, ...] | list[FatIssueCode],
    target_calories: object = None,
    goal: object = None,
    fat_g: int | None = None,
    fat_calories: int | None = None,
    target_fat_percentage: float | None = None,
    effective_fat_percentage: float | None = None,
) -> FatResult:
    """Build a FatResult with safe echoes and policy version.

    issues is always stored as an immutable tuple (nested mutability
    hardening — append/pop/extend on the result are impossible).
    """
    if isinstance(issues, list):
        issues = tuple(issues)
    return FatResult(
        status=status,
        fat_g=fat_g,
        fat_calories=fat_calories,
        target_fat_percentage=target_fat_percentage,
        effective_fat_percentage=effective_fat_percentage,
        target_calories=_calories_echo(target_calories),
        goal=_goal_echo(goal),
        issues=issues,
        policy_version=FAT_POLICY_VERSION,
    )


def _resolve_goal(goal: FatGoal | None) -> FatGoal:
    """Resolve/validate goal for calculation; raise on unsupported.

    Layer A contract already restricts goal to Optional[FatGoal].
    A model_construct bypass can inject arbitrary values — those must
    raise ValueError, never fall through to maintenance behavior.
    """
    if isinstance(goal, FatGoal):
        return goal
    raise ValueError(f"Unsupported goal for fat-v1-rev1: {goal!r}")


def calculate_fat(input_data: FatInput) -> FatResult:
    """Calculate daily fat target from validated FatInput.

    Execution order:
        1. Presence — target_calories None -> INCOMPLETE/
           MISSING_TARGET_CALORIES; goal None -> INCOMPLETE/MISSING_GOAL
        2. Calorie domain — non-int or < 1 ->
           INVALID/OUT_OF_RANGE_TARGET_CALORIES (non-int bypass ->
           INVALID_TARGET_CALORIES)
        3. Goal resolution — non-FatGoal (bypass) -> ValueError
        4. Energy fraction lookup (locked 25%; goal-invariant)
        5. Stages 1–5: float product/quotient, string Decimal
           ROUND_HALF_UP integer, fat_g * 9, 6-decimal effective %
        6. Frozen FatResult with echoes and policy_version

    Args:
        input_data: Validated FatInput (strict/frozen schema).

    Returns:
        FatResult with status, fat fields, echoes, issues.

    Raises:
        ValueError: Unsupported goal reaches calculator (bypass only).
    """
    target = input_data.target_calories
    goal = input_data.goal

    # Step 1: Presence checks (first failure wins; halt immediately)
    if target is None:
        return _result(
            status=FatStatus.INCOMPLETE,
            issues=(FatIssueCode.MISSING_TARGET_CALORIES,),
            target_calories=None,
            goal=goal,
        )
    if goal is None:
        return _result(
            status=FatStatus.INCOMPLETE,
            issues=(FatIssueCode.MISSING_GOAL,),
            target_calories=target,
            goal=None,
        )

    # Step 2: Calorie domain — type guard (bypass) then lower bound
    if isinstance(target, bool) or not isinstance(target, int):
        return _result(
            status=FatStatus.INVALID,
            issues=(FatIssueCode.INVALID_TARGET_CALORIES,),
            target_calories=target,
            goal=goal,
        )
    if target < TARGET_CALORIES_DOMAIN_MIN:
        return _result(
            status=FatStatus.INVALID,
            issues=(FatIssueCode.OUT_OF_RANGE_TARGET_CALORIES,),
            target_calories=target,
            goal=goal,
        )

    # Step 3: Goal resolution (bypass guard — explicit reject)
    resolved_goal = _resolve_goal(goal)

    # Step 4: Locked energy fraction (goal-invariant 25%)
    get_fat_energy_fraction(resolved_goal)

    # Steps 5–6: Five-stage calculation pipeline
    try:
        # Stage 1: unrounded fat energy (kcal)
        unrounded_calories = target * FAT_ENERGY_FRACTION
        # Stage 2: unrounded fat mass (g)
        unrounded_mass = unrounded_calories / ATWATER_FACTOR
        # Stage 3: Decimal fixed-point integer quantization (half-up)
        fat_g = _round_fat_grams(unrounded_mass)
        # Stage 4: realized energy from rounded integer mass
        fat_calories = fat_g * int(ATWATER_FACTOR)
        # Stage 5: target fraction report + 6-decimal effective %
        target_fat_percentage = FAT_ENERGY_FRACTION
        effective_fat_percentage = _quantize_effective_percentage(
            fat_calories,
            target,
        )
    except Exception:
        # Unexpected arithmetic/runtime failure — reserved ERROR path.
        # ValueError from goal/fraction resolution is not caught here
        # (it is raised above, outside this block).
        return _result(
            status=FatStatus.ERROR,
            issues=(FatIssueCode.INTERNAL_ERROR,),
            target_calories=target,
            goal=resolved_goal,
        )

    return _result(
        status=FatStatus.OK,
        issues=(),
        target_calories=target,
        goal=resolved_goal,
        fat_g=fat_g,
        fat_calories=fat_calories,
        target_fat_percentage=target_fat_percentage,
        effective_fat_percentage=effective_fat_percentage,
    )


# ---------------------------------------------------------------------------
# Layer B orchestration helpers (adapter + target binding)
# ---------------------------------------------------------------------------


def map_goal_to_fat_goal(goal: GoalType) -> FatGoal:
    """Layer B adapter: shared GoalType -> Layer A FatGoal (1:1).

    MUSCLE_GAIN maps explicitly to FatGoal.MUSCLE_GAIN — never silently
    remapped to WEIGHT_GAIN. Clinical screening and safety threshold
    evaluation remain Layer B responsibilities outside this pure adapter.
    """
    mapping: dict[GoalType, FatGoal] = {
        GoalType.MAINTENANCE: FatGoal.MAINTENANCE,
        GoalType.WEIGHT_LOSS: FatGoal.WEIGHT_LOSS,
        GoalType.WEIGHT_GAIN: FatGoal.WEIGHT_GAIN,
        GoalType.MUSCLE_GAIN: FatGoal.MUSCLE_GAIN,
    }
    try:
        return mapping[goal]
    except KeyError:
        raise ValueError(
            f"Unsupported GoalType for fat-v1-rev1: {goal!r}"
        ) from None


def build_fat_input(
    target_calories: int | None,
    goal: GoalType | FatGoal | None,
) -> FatInput:
    """Layer B helper: build FatInput from extracted profile fields.

    Accepts shared GoalType or Layer A FatGoal and normalizes to FatGoal
    via the explicit 1:1 adapter. None passes through so missing fields
    surface as INCOMPLETE.
    """
    if goal is None:
        fat_goal: FatGoal | None = None
    elif isinstance(goal, FatGoal):
        fat_goal = goal
    else:
        fat_goal = map_goal_to_fat_goal(goal)
    return FatInput(
        target_calories=target_calories,
        goal=fat_goal,
    )


def bind_fat_target(
    fat_result: FatResult,
    targets,  # NutritionTargets — untyped to avoid circular import
):
    """Layer B: bind FatResult.fat_g into NutritionTargets.

    Binding occurs ONLY when status == OK. Non-OK results leave the
    existing targets unchanged (no partial/null binding).
    Returns a new NutritionTargets instance (model_copy).
    """
    if fat_result.status != FatStatus.OK:
        return targets
    if fat_result.fat_g is None:
        return targets
    return targets.model_copy(
        update={"fat_g": float(fat_result.fat_g)}
    )
