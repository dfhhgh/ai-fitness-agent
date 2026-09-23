"""Deterministic Weight Target calculator — weight-target-v1-rev1.

This module calculates reference weight ranges, an initial weight
milestone, user-target validation flags, and safety review flags.

Policy version: weight-target-v1-rev1

Formulas:
    height_m = height_cm / 100.0
    height_m_squared = height_cm * height_cm / 10000.0
        (algebraically equal to height_m ** 2; pure float64, no rounding)
    BMI = current_weight_kg / height_m_squared

    age < 65:  reference_min_bmi = 18.5, reference_max_bmi = 24.9
    age >= 65: reference_min_bmi = 23.0, reference_max_bmi = 29.9

    reference_min_kg = reference_min_bmi * height_cm * height_cm / 10000.0
    reference_max_kg = reference_max_bmi * height_cm * height_cm / 10000.0

Weight-loss milestone (when no review gate fires):
    milestone = max(current_weight_kg * 0.95, reference_min_kg)

Weight-gain milestone (when no review gate fires):
    milestone = current_weight_kg * 1.05
    (ENGINEERING pacing decision — not clinical consensus; not
    clamped to reference_max)

Maintenance:
    milestone = current_weight_kg

Numerical precision:
    - Internal calculation and comparison use full float64 precision.
    - No intermediate rounding.
    - Output only: Decimal(str(value)).quantize(0.1, ROUND_HALF_UP).

This module is deterministic and side-effect free:
- No LLM calls
- No database access
- No external APIs
- No system clock
- No random state
- No RMR / activity / TDEE / calorie / macro recalculation
- No clinical condition coding (V1 is reference ranges + gates only)
- No WHtR, waist, body-fat, InBody, pregnancy, or eating-disorder fields
"""

from decimal import Decimal, ROUND_HALF_UP

from app.nutrition.models import GoalType
from app.nutrition.weight_target.models import (
    ReviewFlag,
    ValidationFlag,
    WeightTargetInput,
    WeightTargetResult,
    WeightTargetStatus,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

WEIGHT_TARGET_POLICY_VERSION: str = "weight-target-v1-rev1"

REFERENCE_MIN_BMI_ADULT: float = 18.5
REFERENCE_MAX_BMI_ADULT: float = 24.9
REFERENCE_MIN_BMI_OLDER: float = 23.0
REFERENCE_MAX_BMI_OLDER: float = 29.9

OLDER_ADULT_AGE_THRESHOLD: int = 65
OLDER_ADULT_LOW_BMI_WEIGHT_LOSS_THRESHOLD: float = 25.0
HIGH_BMI_WEIGHT_GAIN_THRESHOLD: float = 30.0

WEIGHT_LOSS_MILESTONE_FACTOR: float = 0.95
WEIGHT_GAIN_MILESTONE_FACTOR: float = 1.05

OUTPUT_QUANTUM: str = "0.1"


def _round_weight(value: float) -> float:
    """Round a weight to 1 decimal place using Decimal ROUND_HALF_UP.

    Uses Decimal(str(value)) so the decimal string representation is
    the rounding boundary (avoids binary float artifacts). This is
    round-half-up, NOT Python's default round-half-even.

    Applied ONLY at output serialization — never to intermediate
    calculations or comparisons.
    """
    quantized = Decimal(str(value)).quantize(
        Decimal(OUTPUT_QUANTUM),
        rounding=ROUND_HALF_UP,
    )
    return float(quantized)


def _reference_bmi_bounds(age_years: int) -> tuple[float, float]:
    """Return (reference_min_bmi, reference_max_bmi) for the age band."""
    if age_years >= OLDER_ADULT_AGE_THRESHOLD:
        return REFERENCE_MIN_BMI_OLDER, REFERENCE_MAX_BMI_OLDER
    return REFERENCE_MIN_BMI_ADULT, REFERENCE_MAX_BMI_ADULT


def _collect_review_flags(
    *,
    age_years: int,
    bmi: float,
    current_weight_kg: float,
    reference_min_kg: float,
    goal: GoalType,
) -> list[ReviewFlag]:
    """Evaluate ALL applicable review gates for the goal.

    Does not short-circuit — every applicable gate is evaluated so
    multiple flags can be returned together.

    Only WEIGHT_LOSS and WEIGHT_GAIN define safety gates in V1.
    MAINTENANCE has no loss/gain gates. Any other goal value is a
    contract violation (WeightTargetInput rejects it at Layer A).
    """
    flags: list[ReviewFlag] = []

    if goal == GoalType.WEIGHT_LOSS:
        if current_weight_kg < reference_min_kg:
            flags.append(ReviewFlag.CURRENT_WEIGHT_BELOW_REFERENCE_MIN)
        if (
            age_years >= OLDER_ADULT_AGE_THRESHOLD
            and bmi < OLDER_ADULT_LOW_BMI_WEIGHT_LOSS_THRESHOLD
        ):
            flags.append(ReviewFlag.OLDER_ADULT_LOW_BMI_WEIGHT_LOSS)
    elif goal == GoalType.WEIGHT_GAIN:
        if bmi >= HIGH_BMI_WEIGHT_GAIN_THRESHOLD:
            flags.append(ReviewFlag.HIGH_BMI_WEIGHT_GAIN_REQUEST)
    elif goal == GoalType.MAINTENANCE:
        # MAINTENANCE: no weight-loss or weight-gain safety gates in V1.
        pass
    else:
        raise ValueError(
            f"Unsupported goal for weight-target-v1-rev1: {goal!r}"
        )

    return flags


def _collect_validation_flags(
    user_target: float | None,
    reference_min_kg: float,
    reference_max_kg: float,
) -> list[ValidationFlag]:
    """Validate user-requested target against the reference range.

    Boundary equality produces no flag. Uses `is not None` (never
    truthiness) so a valid target is never skipped.
    """
    if user_target is None:
        return []

    if user_target < reference_min_kg:
        return [ValidationFlag.USER_TARGET_BELOW_REFERENCE_RANGE]
    if user_target > reference_max_kg:
        return [ValidationFlag.USER_TARGET_ABOVE_REFERENCE_RANGE]
    return []


def _initial_milestone(
    *,
    goal: GoalType,
    current_weight_kg: float,
    reference_min_kg: float,
) -> float:
    """Compute the unrounded initial milestone for an OK path.

    Only WEIGHT_LOSS, WEIGHT_GAIN, and MAINTENANCE are supported.
    MUSCLE_GAIN (or any other value) must not fall through to the
    maintenance behavior — WeightTargetInput rejects it at Layer A,
    and this helper raises if an unsupported goal reaches it.
    """
    if goal == GoalType.WEIGHT_LOSS:
        return max(
            current_weight_kg * WEIGHT_LOSS_MILESTONE_FACTOR,
            reference_min_kg,
        )
    if goal == GoalType.WEIGHT_GAIN:
        return current_weight_kg * WEIGHT_GAIN_MILESTONE_FACTOR
    if goal == GoalType.MAINTENANCE:
        return current_weight_kg
    raise ValueError(
        f"Unsupported goal for weight-target-v1-rev1: {goal!r}"
    )


def determine_weight_targets(
    input_data: WeightTargetInput,
) -> WeightTargetResult:
    """Determine weight targets from validated WeightTargetInput.

    Execution order:
        1. Read validated input (age, height, weight, goal, user target)
        2. Compute height_m, BMI, age-band reference BMI bounds
        3. Compute reference_min_kg / reference_max_kg (full precision)
        4. Evaluate ALL applicable review gates for the goal
        5. If any review flag → status REVIEW_REQUIRED, milestone None
        6. Else compute initial milestone (full precision)
        7. Collect user-target validation flags (does not alter status)
        8. Round outputs only: Decimal ROUND_HALF_UP → 1 decimal place

    Args:
        input_data: Validated WeightTargetInput.

    Returns:
        WeightTargetResult with status, reference range, milestone,
        flags, and policy version.
    """
    age = input_data.age_years
    height_cm = input_data.height_cm
    weight = input_data.current_weight_kg
    goal = input_data.goal
    user_target = input_data.user_requested_target_weight_kg

    # Step 2: height squared and BMI (full float64 precision)
    # height_m_squared = height_cm**2 / 10000 is algebraically equal to
    # (height_cm/100)**2, with better boundary behavior for exact decimal
    # cases (e.g. height 180 → 3.24) while remaining pure float64 with
    # no intermediate rounding.
    height_m_squared = height_cm * height_cm / 10000.0
    bmi = weight / height_m_squared

    # Step 3: Reference range (unrounded for comparisons)
    ref_min_bmi, ref_max_bmi = _reference_bmi_bounds(age)
    reference_min_kg = ref_min_bmi * height_cm * height_cm / 10000.0
    reference_max_kg = ref_max_bmi * height_cm * height_cm / 10000.0

    # Step 4: Review gates (all applicable; no short-circuit)
    review_flags = _collect_review_flags(
        age_years=age,
        bmi=bmi,
        current_weight_kg=weight,
        reference_min_kg=reference_min_kg,
        goal=goal,
    )

    # Steps 5–6: Status and milestone
    if review_flags:
        status = WeightTargetStatus.REVIEW_REQUIRED
        milestone_unrounded: float | None = None
    else:
        status = WeightTargetStatus.OK
        milestone_unrounded = _initial_milestone(
            goal=goal,
            current_weight_kg=weight,
            reference_min_kg=reference_min_kg,
        )

    # Step 7: Validation flags (informational; independent of status)
    validation_flags = _collect_validation_flags(
        user_target,
        reference_min_kg,
        reference_max_kg,
    )

    # Step 8: Output rounding only (ROUND_HALF_UP → 1 decimal)
    return WeightTargetResult(
        status=status,
        current_weight_kg=_round_weight(weight),
        user_requested_target_weight_kg=(
            _round_weight(user_target) if user_target is not None else None
        ),
        reference_weight_range_min_kg=_round_weight(reference_min_kg),
        reference_weight_range_max_kg=_round_weight(reference_max_kg),
        initial_milestone_weight_kg=(
            _round_weight(milestone_unrounded)
            if milestone_unrounded is not None
            else None
        ),
        validation_flags=validation_flags,
        review_flags=review_flags,
        policy_version=WEIGHT_TARGET_POLICY_VERSION,
    )
