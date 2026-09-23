"""Deterministic Carbohydrate Calculator — carb-v1 (Layer A pure calculator).

Policy version: carb-v1

Formula (residual-macro processor):
    Stage 1: protein_calories = protein_g * 4
    Stage 2: residual_calories = target_calories - protein_calories - fat_calories
    Stage 3: if residual < 0  → INVALID (preserve negative residual)
             if residual == 0 → OK, carbs = 0
             if residual > 0  → raw_carb_g = Decimal(residual) / Decimal(4)
                                 carbohydrates_g = quantize(1, ROUND_HALF_UP) → int
    Stage 4: carbohydrate_calories = carbohydrates_g * 4

Rounding:
    Decimal ROUND_HALF_UP to integer grams (never Python built-in
    rounding).

Layer A / Layer B boundary:
    - Layer A: pure calculator on CarbInput → frozen CarbResult.
      No medical screening, no clinical thresholds, no LLM/network/clock.
      Total carbohydrate only. No minimum floors or range enforcement.
    - Layer B: extracts upstream outputs, screens clinical conditions,
      binds carbohydrates_g into NutritionTargets only when status == OK.

Schema vs domain:
    - Schema violations (string/bool/extra/negative) raise Pydantic
      ValidationError — never CarbResult.
    - The only domain-level invalid state is a negative residual.
"""


from decimal import ROUND_HALF_UP, Decimal

from app.nutrition.carbohydrate.models import (
    CarbInput,
    CarbIssueCode,
    CarbResult,
    CarbStatus,
)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

CARB_POLICY_VERSION: str = "carb-v1"

PROTEIN_KCAL_PER_G: int = 4
CARB_KCAL_PER_G: int = 4

OUTPUT_QUANTUM = Decimal("1")


def _round_carb_grams(residual_calories: int) -> int:
    """Round residual_calories / 4 to integer grams (Decimal ROUND_HALF_UP).

    Uses exact Decimal arithmetic to avoid binary float artifacts.
    This is arithmetic half-up, NOT Python's default round-half-even.
    """
    raw = Decimal(residual_calories) / Decimal(CARB_KCAL_PER_G)
    quantized = raw.quantize(OUTPUT_QUANTUM, rounding=ROUND_HALF_UP)
    return int(quantized)


def calculate_carbohydrates(input_data: CarbInput) -> CarbResult:
    """Calculate daily carbohydrate target from validated CarbInput.

    Execution order:
        1. protein_calories = protein_g * 4
        2. residual_calories = target_calories - protein_calories - fat_calories
        3. If residual < 0 → INVALID with negative residual preserved
        4. If residual == 0 → OK with carbs = 0
        5. If residual > 0 → Decimal ROUND_HALF_UP integer grams
        6. carbohydrate_calories = carbohydrates_g * 4

    Args:
        input_data: Validated CarbInput (strict/frozen schema).

    Returns:
        CarbResult with status, carbohydrate fields, residual, issues.
    """
    # Stage 1: protein energy
    protein_calories = input_data.protein_g * PROTEIN_KCAL_PER_G

    # Stage 2: residual energy
    residual_calories = (
        input_data.target_calories - protein_calories - input_data.fat_calories
    )

    # Stage 3: negative residual → INVALID
    if residual_calories < 0:
        return CarbResult(
            status=CarbStatus.INVALID,
            carbohydrates_g=None,
            carbohydrate_calories=None,
            residual_calories=residual_calories,
            issues=(CarbIssueCode.NEGATIVE_CARBOHYDRATE_RESIDUAL,),
            policy_version=CARB_POLICY_VERSION,
        )

    # Stage 4: zero residual → OK with carbs = 0
    if residual_calories == 0:
        return CarbResult(
            status=CarbStatus.OK,
            carbohydrates_g=0,
            carbohydrate_calories=0,
            residual_calories=0,
            issues=(),
            policy_version=CARB_POLICY_VERSION,
        )

    # Stage 5: positive residual → Decimal ROUND_HALF_UP
    carbohydrates_g = _round_carb_grams(residual_calories)

    # Stage 6: realized carbohydrate energy
    carbohydrate_calories = carbohydrates_g * CARB_KCAL_PER_G

    return CarbResult(
        status=CarbStatus.OK,
        carbohydrates_g=carbohydrates_g,
        carbohydrate_calories=carbohydrate_calories,
        residual_calories=residual_calories,
        issues=(),
        policy_version=CARB_POLICY_VERSION,
    )
