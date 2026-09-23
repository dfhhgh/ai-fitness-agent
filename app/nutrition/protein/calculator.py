"""Deterministic Protein Calculator — protein-v1 (Layer A pure calculator).

Policy version: protein-v1 (Rev 1.1)

Formula (three-stage pipeline):
    Stage 1: unrounded = current_weight_kg * factor   (float64)
    Stage 2: Decimal(str(unrounded))                  (string boundary)
    Stage 3: quantize(Decimal("1"), ROUND_HALF_UP) -> int

Goal factors (locked):
    MAINTENANCE -> 1.2 g/kg
    WEIGHT_LOSS / WEIGHT_GAIN / MUSCLE_GAIN -> 1.6 g/kg

Weight engineering domain:
    0.5 <= current_weight_kg <= 500.0

Layer A / Layer B boundary:
    - Layer A: pure calculator on ProteinInput -> frozen ProteinResult.
      No medical screening, no clinical thresholds (moved to Layer B),
      no RMR/TDEE/calorie/activity recalculation, no LLM/network/clock.
    - Layer B: maps shared GoalType -> ProteinGoal 1:1, extracts weight,
      screens medical contraindications, binds protein_g into
      NutritionTargets only when status == OK.

Schema vs domain (OPTION A):
    - Schema violations (string/bool/list/extra/invalid enum) raise
      Pydantic ValidationError — never ProteinResult.
    - Domain violations on a valid ProteinInput return ProteinResult
      with INCOMPLETE/INVALID statuses and issue codes.
    - Unsupported goal reaching the calculator via model_construct
      bypass raises ValueError — never falls through to maintenance.
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from app.nutrition.models import GoalType
from app.nutrition.protein.models import (
    ProteinGoal,
    ProteinInput,
    ProteinIssueCode,
    ProteinResult,
    ProteinStatus,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

PROTEIN_POLICY_VERSION: str = "protein-v1"

PROTEIN_FACTOR_MAINTENANCE: float = 1.2
PROTEIN_FACTOR_DEFAULT: float = 1.6

WEIGHT_DOMAIN_MIN_KG: float = 0.5
WEIGHT_DOMAIN_MAX_KG: float = 500.0

OUTPUT_QUANTUM: str = "1"

# Locked factor map — MUSCLE_GAIN is explicitly supported at 1.6.
GOAL_FACTORS: dict[ProteinGoal, float] = {
    ProteinGoal.MAINTENANCE: PROTEIN_FACTOR_MAINTENANCE,
    ProteinGoal.WEIGHT_LOSS: PROTEIN_FACTOR_DEFAULT,
    ProteinGoal.WEIGHT_GAIN: PROTEIN_FACTOR_DEFAULT,
    ProteinGoal.MUSCLE_GAIN: PROTEIN_FACTOR_DEFAULT,
}


def get_protein_factor(goal: ProteinGoal) -> float:
    """Return the locked protein factor for a Layer A goal.

    Raises ValueError for any goal not in the locked factor map —
    never falls through to a default/maintenance factor.
    """
    try:
        return GOAL_FACTORS[goal]
    except KeyError:
        raise ValueError(
            f"Unsupported goal for protein-v1: {goal!r}"
        ) from None


def _round_protein_grams(value: float) -> int:
    """Round an unrounded product to integer grams (Decimal ROUND_HALF_UP).

    Uses Decimal(str(value)) so the decimal string representation is the
    rounding boundary (avoids binary float artifacts). This is
    arithmetic half-up, NOT Python's default round-half-even.
    """
    quantized = Decimal(str(value)).quantize(
        Decimal(OUTPUT_QUANTUM),
        rounding=ROUND_HALF_UP,
    )
    return int(quantized)


def _goal_echo(goal: object) -> ProteinGoal | None:
    """Echo goal only when it is a valid ProteinGoal instance."""
    if isinstance(goal, ProteinGoal):
        return goal
    return None


def _weight_echo(weight: object) -> float | None:
    """Echo weight only when it is a real float (schema-valid)."""
    # bool is a subclass of int, not float — already rejected at schema,
    # but guard defensively so True never echoes as a weight.
    if isinstance(weight, bool):
        return None
    if isinstance(weight, float):
        return weight
    return None


def _result(
    *,
    status: ProteinStatus,
    issues: tuple[ProteinIssueCode, ...] | list[ProteinIssueCode],
    weight: object = None,
    goal: object = None,
    protein_g: int | None = None,
    factor: float | None = None,
) -> ProteinResult:
    """Build a ProteinResult with safe echoes and policy version.

    issues is always stored as an immutable tuple (nested mutability
    hardening — append/pop/extend on the result are impossible).
    """
    if isinstance(issues, list):
        issues = tuple(issues)
    return ProteinResult(
        status=status,
        protein_g=protein_g,
        protein_factor_g_per_kg=factor,
        current_weight_kg=_weight_echo(weight),
        goal=_goal_echo(goal),
        issues=issues,
        policy_version=PROTEIN_POLICY_VERSION,
    )


def _resolve_goal(goal: ProteinGoal | None) -> ProteinGoal:
    """Resolve/validate goal for calculation; raise on unsupported.

    Layer A contract already restricts goal to Optional[ProteinGoal].
    A model_construct bypass can inject arbitrary values — those must
    raise ValueError, never fall through to maintenance behavior.
    """
    if isinstance(goal, ProteinGoal):
        return goal
    raise ValueError(f"Unsupported goal for protein-v1: {goal!r}")


def calculate_protein(input_data: ProteinInput) -> ProteinResult:
    """Calculate daily protein target from validated ProteinInput.

    Execution order:
        1. Presence — weight None -> INCOMPLETE/MISSING_WEIGHT;
           goal None -> INCOMPLETE/MISSING_GOAL
        2. Weight domain — non-finite or <= 0 -> INVALID/INVALID_WEIGHT;
           0 < w < 0.5 or w > 500.0 -> INVALID/OUT_OF_RANGE_WEIGHT
        3. Goal resolution — non-ProteinGoal (bypass) -> ValueError
        4. Factor lookup (locked map; never default fall-through)
        5. Stage 1 float multiply, Stage 2 string Decimal,
           Stage 3 ROUND_HALF_UP integer
        6. Frozen ProteinResult with echoes and policy_version

    Args:
        input_data: Validated ProteinInput (strict/frozen schema).

    Returns:
        ProteinResult with status, protein_g, factor, echoes, issues.

    Raises:
        ValueError: Unsupported goal reaches calculator (bypass only).
    """
    weight = input_data.current_weight_kg
    goal = input_data.goal

    # Step 1: Presence checks (first failure wins; halt immediately)
    if weight is None:
        return _result(
            status=ProteinStatus.INCOMPLETE,
            issues=(ProteinIssueCode.MISSING_WEIGHT,),
            weight=None,
            goal=goal,
        )
    if goal is None:
        return _result(
            status=ProteinStatus.INCOMPLETE,
            issues=(ProteinIssueCode.MISSING_GOAL,),
            weight=weight,
            goal=None,
        )

    # Step 2: Weight domain — finiteness then engineering bounds
    if not math.isfinite(weight):
        return _result(
            status=ProteinStatus.INVALID,
            issues=(ProteinIssueCode.INVALID_WEIGHT,),
            weight=weight,
            goal=goal,
        )
    if weight <= 0.0:
        return _result(
            status=ProteinStatus.INVALID,
            issues=(ProteinIssueCode.INVALID_WEIGHT,),
            weight=weight,
            goal=goal,
        )
    if weight < WEIGHT_DOMAIN_MIN_KG or weight > WEIGHT_DOMAIN_MAX_KG:
        return _result(
            status=ProteinStatus.INVALID,
            issues=(ProteinIssueCode.OUT_OF_RANGE_WEIGHT,),
            weight=weight,
            goal=goal,
        )

    # Step 3: Goal resolution (bypass guard — explicit reject)
    resolved_goal = _resolve_goal(goal)

    # Step 4: Locked factor lookup (ValueError if not in map)
    factor = get_protein_factor(resolved_goal)

    # Steps 5–6: Three-stage calculation
    try:
        unrounded = weight * factor
        protein_g = _round_protein_grams(unrounded)
    except Exception:
        # Unexpected arithmetic/runtime failure — reserved ERROR path.
        # ValueError from goal/factor resolution is not caught here
        # (it is raised above, outside this block).
        return _result(
            status=ProteinStatus.ERROR,
            issues=(ProteinIssueCode.INTERNAL_ERROR,),
            weight=weight,
            goal=resolved_goal,
        )

    return _result(
        status=ProteinStatus.OK,
        issues=(),
        weight=weight,
        goal=resolved_goal,
        protein_g=protein_g,
        factor=factor,
    )


# ---------------------------------------------------------------------------
# Layer B orchestration helpers (adapter + target binding)
# ---------------------------------------------------------------------------


def map_goal_to_protein_goal(goal: GoalType) -> ProteinGoal:
    """Layer B adapter: shared GoalType -> Layer A ProteinGoal (1:1).

    MUSCLE_GAIN maps explicitly to ProteinGoal.MUSCLE_GAIN — never
    silently remapped to WEIGHT_GAIN. Medical screening and safety
    threshold evaluation remain Layer B responsibilities outside this
    pure adapter.
    """
    mapping: dict[GoalType, ProteinGoal] = {
        GoalType.MAINTENANCE: ProteinGoal.MAINTENANCE,
        GoalType.WEIGHT_LOSS: ProteinGoal.WEIGHT_LOSS,
        GoalType.WEIGHT_GAIN: ProteinGoal.WEIGHT_GAIN,
        GoalType.MUSCLE_GAIN: ProteinGoal.MUSCLE_GAIN,
    }
    try:
        return mapping[goal]
    except KeyError:
        raise ValueError(
            f"Unsupported GoalType for protein-v1: {goal!r}"
        ) from None


def build_protein_input(
    current_weight_kg: float | None,
    goal: GoalType | ProteinGoal | None,
) -> ProteinInput:
    """Layer B helper: build ProteinInput from extracted profile fields.

    Accepts shared GoalType or Layer A ProteinGoal and normalizes to
    ProteinGoal via the explicit 1:1 adapter. None passes through so
    missing fields surface as INCOMPLETE.
    """
    if goal is None:
        protein_goal: ProteinGoal | None = None
    elif isinstance(goal, ProteinGoal):
        protein_goal = goal
    else:
        protein_goal = map_goal_to_protein_goal(goal)
    return ProteinInput(
        current_weight_kg=current_weight_kg,
        goal=protein_goal,
    )


def bind_protein_target(
    protein_result: ProteinResult,
    targets,  # NutritionTargets — untyped to avoid circular import
):
    """Layer B: bind ProteinResult.protein_g into NutritionTargets.

    Binding occurs ONLY when status == OK. Non-OK results leave the
    existing targets unchanged (no partial/null binding).
    Returns a new NutritionTargets instance (model_copy).
    """
    if protein_result.status != ProteinStatus.OK:
        return targets
    if protein_result.protein_g is None:
        return targets
    return targets.model_copy(
        update={"protein_g": float(protein_result.protein_g)}
    )
