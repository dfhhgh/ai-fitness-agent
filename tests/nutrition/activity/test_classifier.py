"""Tests for app.nutrition.activity.classifier — activity classification stub.

The classifier is currently a STUB because the classification matrix
is not fully specified. These tests verify:

- The stub refuses to classify (ambiguity documented)
- The ambiguity is clearly reported
- No LLM/network dependency exists
- Structured inputs are accepted
"""

import pytest

from app.nutrition.activity.classifier import (
    ActivityClassificationAmbiguous,
    ActivityClassificationInput,
    ActivityClassificationResult,
    ActivityClassifier,
)
from app.nutrition.models import ActivityCategory


class TestActivityClassifierStub:
    """Verify the classifier stub behaves correctly."""

    def setup_method(self):
        self.classifier = ActivityClassifier()

    def test_classifier_refuses_to_classify(self):
        """Classifier raises ActivityClassificationAmbiguous for any input."""
        inputs = ActivityClassificationInput(
            work_activity="moderate",
            training_days_per_week=4,
        )
        with pytest.raises(ActivityClassificationAmbiguous):
            self.classifier.classify(inputs)

    def test_ambiguity_documented_in_exception(self):
        """Exception message documents the unresolved ambiguity."""
        inputs = ActivityClassificationInput(
            work_activity="light",
            training_days_per_week=2,
        )
        with pytest.raises(ActivityClassificationAmbiguous, match="ambiguous"):
            self.classifier.classify(inputs)

    def test_ambiguity_mentions_or_vs_and(self):
        """Exception message mentions the OR/AND ambiguity."""
        inputs = ActivityClassificationInput(
            work_activity="sedentary",
            training_days_per_week=5,
        )
        with pytest.raises(ActivityClassificationAmbiguous, match="OR.*AND|AND.*OR"):
            self.classifier.classify(inputs)

    def test_classifier_accepts_structured_inputs(self):
        """Classifier accepts structured ActivityClassificationInput."""
        inputs = ActivityClassificationInput(
            work_activity="high",
            training_days_per_week=6,
            training_duration_minutes=60,
            exercise_intensity="high",
        )
        # Should not raise on input construction
        assert inputs.work_activity == "high"
        assert inputs.training_days_per_week == 6

    def test_classifier_has_no_llm_dependency(self):
        """Classifier does not import or use LLM modules."""
        import app.nutrition.activity.classifier as mod
        source = open(mod.__file__).read()
        assert "llm" not in source.lower()
        assert "LLMClient" not in source
        assert "ProfileExtractor" not in source

    def test_classifier_has_no_network_dependency(self):
        """Classifier does not import or use network modules."""
        import app.nutrition.activity.classifier as mod
        source = open(mod.__file__).read()
        assert "httpx" not in source
        assert "httpcore" not in source
        assert "telegram" not in source


class TestActivityClassificationInput:
    """Test the input dataclass."""

    def test_valid_construction(self):
        """Valid input with all fields."""
        inp = ActivityClassificationInput(
            work_activity="moderate",
            training_days_per_week=4,
            training_duration_minutes=60,
            exercise_intensity="high",
        )
        assert inp.work_activity == "moderate"
        assert inp.training_days_per_week == 4
        assert inp.training_duration_minutes == 60
        assert inp.exercise_intensity == "high"

    def test_optional_fields_default_to_none(self):
        """Optional fields default to None."""
        inp = ActivityClassificationInput(
            work_activity="light",
            training_days_per_week=2,
        )
        assert inp.training_duration_minutes is None
        assert inp.exercise_intensity is None

    def test_is_frozen(self):
        """Input is immutable (frozen dataclass)."""
        inp = ActivityClassificationInput(
            work_activity="sedentary",
            training_days_per_week=0,
        )
        with pytest.raises(AttributeError):
            inp.work_activity = "moderate"  # type: ignore


class TestActivityClassificationResult:
    """Test the result dataclass."""

    def test_valid_construction(self):
        """Valid result with category and factor."""
        result = ActivityClassificationResult(
            category=ActivityCategory.MODERATE,
            factor=1.55,
            issues=[],
        )
        assert result.category == ActivityCategory.MODERATE
        assert result.factor == 1.55
        assert result.issues == []

    def test_ambiguous_result(self):
        """Result can represent ambiguous classification."""
        result = ActivityClassificationResult(
            category=None,
            factor=None,
            issues=["Classification matrix not specified"],
        )
        assert result.category is None
        assert result.factor is None
        assert len(result.issues) == 1

    def test_is_frozen(self):
        """Result is immutable (frozen dataclass)."""
        result = ActivityClassificationResult(
            category=ActivityCategory.HIGH,
            factor=1.75,
            issues=[],
        )
        with pytest.raises(AttributeError):
            result.category = ActivityCategory.LOW  # type: ignore
