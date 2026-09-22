"""Deterministic activity classifier — STUB.

This module will contain the deterministic classification logic that
converts structured activity inputs into an ActivityCategory.

STATUS: AMBIGUOUS — classification matrix not fully specified.

The repository's Nutrition Core specification defines activity factors
per category but does NOT specify the exact classification rules for
determining which category a given set of inputs belongs to.

The unresolved decision:

The specification mentions both OR and AND semantics:

- SEDENTARY: office/desk job, minimal daily movement
- LIGHT: light daily movement OR training 1–2 days/week
- MODERATE: moderate daily movement AND training 3–4 days/week
- HIGH: physical job AND training 5+ days/week

The ambiguity:

1. For LIGHT, the spec says OR — but what if work_activity=moderate
   and training_days=1? Is that LIGHT or MODERATE?

2. For MODERATE and HIGH, the spec says AND — but what if work_activity
   is sedentary and training_days=5? Is that HIGH or MODERATE?

3. When work_activity and training_days_per_week suggest different
   categories, which takes precedence?

4. Can training_days_per_week upgrade but not downgrade the category
   set by work_activity?

This module REFUSES to classify until the ambiguity is resolved.

DO NOT invent thresholds, OR/AND semantics, or precedence rules.
"""

from dataclasses import dataclass
from typing import List

from app.nutrition.models import ActivityCategory


class ActivityClassificationAmbiguous(Exception):
    """Raised when the activity classification policy is ambiguous.

    This exception documents that the classification matrix has not been
    fully specified. It should be resolved before this classifier is used
    in production.
    """

    pass


@dataclass(frozen=True)
class ActivityClassificationInput:
    """Structured activity inputs for classification.

    This is NOT NutritionAssessmentInput. This is the raw structured
    data before normalization into a single ActivityCategory.

    The mapper will eventually construct this from ClientProfile data.

    Attributes:
        work_activity: Pre-classified work/daily activity level.
            Expected values: "sedentary", "light", "moderate", "high".
        training_days_per_week: Training frequency, 0–7.
        training_duration_minutes: Optional normalized training duration.
        exercise_intensity: Optional exercise intensity.
    """

    work_activity: str
    training_days_per_week: int
    training_duration_minutes: int | None = None
    exercise_intensity: str | None = None


@dataclass(frozen=True)
class ActivityClassificationResult:
    """Result of activity classification.

    When classification is ambiguous, category is None and issues
    describe exactly what is unresolved.

    Attributes:
        category: Determined category (None if ambiguous).
        factor: Activity factor (None if ambiguous).
        issues: List of unresolved issues preventing classification.
    """

    category: ActivityCategory | None
    factor: float | None
    issues: List[str]


class ActivityClassifier:
    """Deterministic activity classifier.

    STATUS: STUB — refuses to classify until policy is resolved.

    The classifier accepts structured activity inputs and returns an
    ActivityCategory. It does NOT:
    - Interpret Egyptian Arabic
    - Inspect free-form text
    - Calculate nutrition
    - Calculate TDEE
    - Access ClientProfile

    When the classification matrix is fully specified, this class will
    implement the exact deterministic rules.
    """

    def classify(self, inputs: ActivityClassificationInput) -> ActivityClassificationResult:
        """Classify structured activity inputs into an ActivityCategory.

        CURRENT BEHAVIOR: Always raises ActivityClassificationAmbiguous
        because the classification matrix is not fully specified.

        FUTURE BEHAVIOR: Will implement the exact deterministic rules
        once the OR/AND semantics and precedence are resolved.

        Args:
            inputs: Structured activity inputs.

        Returns:
            ActivityClassificationResult with category and factor.

        Raises:
            ActivityClassificationAmbiguous: Always, until policy is resolved.
        """
        issues = self._identify_ambiguities(inputs)

        if issues:
            raise ActivityClassificationAmbiguous(
                "Activity classification policy is ambiguous. "
                "The following issues must be resolved before classification:\n"
                + "\n".join(f"  - {issue}" for issue in issues)
            )

        # If no ambiguities (currently unreachable), classify here.
        # This branch will be implemented once the policy is resolved.
        raise ActivityClassificationAmbiguous(
            "Activity classification logic not yet implemented. "
            "The classification matrix must be fully specified first."
        )

    def _identify_ambiguities(self, inputs: ActivityClassificationInput) -> List[str]:
        """Identify unresolved ambiguities in the activity inputs.

        This method documents exactly what is ambiguous about the
        current classification policy.
        """
        issues: List[str] = []

        # Document the core ambiguity: OR vs AND semantics
        issues.append(
            "Classification matrix not specified: the repository does not define "
            "whether activity categories are determined by work_activity OR "
            "training_days_per_week, by AND, or by precedence rules."
        )

        # Document specific ambiguous scenarios
        if inputs.work_activity not in ("sedentary", "light", "moderate", "high"):
            issues.append(
                f"work_activity={inputs.work_activity!r} is not a recognized "
                f"category. Expected: sedentary, light, moderate, high."
            )

        if not (0 <= inputs.training_days_per_week <= 7):
            issues.append(
                f"training_days_per_week={inputs.training_days_per_week} "
                f"is out of valid range 0–7."
            )

        # Document the specific OR/AND ambiguity
        issues.append(
            "Unresolved: When work_activity and training_days_per_week "
            "suggest different categories, which takes precedence? "
            "Can training upgrade but not downgrade the work_activity baseline?"
        )

        return issues
