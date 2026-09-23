"""Current Weight Authority Resolver — Milestone 2.2.9.

Responsibilities:
- Resolve authoritative body mass for downstream calculation engines.
- Precedence:
  1. Primary: NutritionAssessmentInput.weight_kg (session survey).
  2. Profile prefill: ClientProfile.personal.weight_kg only as pre-assembly fill.
  3. InBody measurement: NEVER becomes the calculation weight.
- Equality-based data-quality comparison between InBody and resolved weight:
  - If abs(inbody_weight - resolved_weight) > 0: append INBODY_WEIGHT_MISMATCH flag.
  - Resolved weight remains completely untouched.
- Tracking weight_authority_source (SURVEY, PROFILE_PREFILL, UNRESOLVED).
"""

from typing import List, NamedTuple, Optional

from app.nutrition.models import InBodySnapshot, NutritionAssessmentInput
from app.nutrition.orchestrator.contracts import WeightAuthoritySource
from app.profile.models import ClientProfile

INBODY_WEIGHT_MISMATCH: str = "INBODY_WEIGHT_MISMATCH"


class WeightResolutionResult(NamedTuple):
    """Result of weight authority resolution."""

    resolved_weight_kg: Optional[float]
    source: WeightAuthoritySource
    review_flags: List[str]


def prefill_survey_weight(
    survey_weight: Optional[float],
    profile: Optional[ClientProfile],
) -> tuple[Optional[float], WeightAuthoritySource]:
    """Pre-assembly helper to populate survey weight before NutritionAssessmentInput creation.

    Follows locked precedence:
    1. If survey_weight is present and > 0 → SURVEY.
    2. Else if profile.personal.weight_kg is present and > 0 → PROFILE_PREFILL.
    3. Else → UNRESOLVED.
    """
    if survey_weight is not None and survey_weight > 0:
        return survey_weight, WeightAuthoritySource.SURVEY

    if (
        profile is not None
        and profile.personal.weight_kg is not None
        and profile.personal.weight_kg > 0
    ):
        return profile.personal.weight_kg, WeightAuthoritySource.PROFILE_PREFILL

    return None, WeightAuthoritySource.UNRESOLVED


class WeightAuthorityResolver:
    """Deterministic body mass resolution engine."""

    def resolve(
        self,
        nutrition_input: NutritionAssessmentInput,
        client_profile: Optional[ClientProfile] = None,
        inbody_snapshot: Optional[InBodySnapshot] = None,
        forced_source: Optional[WeightAuthoritySource] = None,
    ) -> WeightResolutionResult:
        """Resolve authoritative current weight and evaluate InBody discrepancy.

        Args:
            nutrition_input: Validated survey input.
            client_profile: Client profile context.
            inbody_snapshot: Optional InBody measurement device snapshot.
            forced_source: Optional source override (e.g. PROFILE_PREFILL or UNRESOLVED).

        Returns:
            WeightResolutionResult containing resolved mass, source, and review flags.
        """
        review_flags: List[str] = []

        # Check explicit unresolved marker
        if forced_source == WeightAuthoritySource.UNRESOLVED:
            return WeightResolutionResult(
                resolved_weight_kg=None,
                source=WeightAuthoritySource.UNRESOLVED,
                review_flags=[],
            )

        raw_weight = getattr(nutrition_input, "weight_kg", None)
        if raw_weight is None or raw_weight <= 0:
            return WeightResolutionResult(
                resolved_weight_kg=None,
                source=WeightAuthoritySource.UNRESOLVED,
                review_flags=[],
            )

        resolved_weight = float(raw_weight)

        if forced_source == WeightAuthoritySource.PROFILE_PREFILL:
            source = WeightAuthoritySource.PROFILE_PREFILL
        else:
            source = WeightAuthoritySource.SURVEY

        # InBody comparison (InBody NEVER overrides resolved weight)
        if (
            inbody_snapshot is not None
            and inbody_snapshot.weight_kg is not None
        ):
            inbody_weight = float(inbody_snapshot.weight_kg)
            if abs(inbody_weight - resolved_weight) > 0:
                review_flags.append(INBODY_WEIGHT_MISMATCH)

        return WeightResolutionResult(
            resolved_weight_kg=resolved_weight,
            source=source,
            review_flags=review_flags,
        )
