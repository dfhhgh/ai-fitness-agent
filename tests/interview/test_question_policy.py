"""Tests for app.interview.question_policy -- deterministic question mapping."""

import pytest

from app.interview.question_policy import (
    QUESTION_SPECS,
    QuestionSpec,
    UnknownQuestionFieldError,
    get_question_spec,
)
from app.profile.missing_fields import REQUIRED_ONBOARDING_FIELDS


class TestQuestionPolicy:
    """Deterministic question policy test suite."""

    def test_all_required_fields_have_specs(self):
        """All 10 required onboarding fields have question specs."""
        for field in REQUIRED_ONBOARDING_FIELDS:
            assert field in QUESTION_SPECS, f"Missing spec for required field: {field}"

    def test_spec_field_matches_dictionary_key(self):
        """Every spec.field matches its dictionary key."""
        for key, spec in QUESTION_SPECS.items():
            assert spec.field == key, f"Spec field {spec.field!r} does not match key {key!r}"

    def test_every_field_has_non_empty_intent(self):
        """Every field has a non-empty intent string."""
        for field, spec in QUESTION_SPECS.items():
            assert spec.intent, f"Empty intent for field: {field}"
            assert isinstance(spec.intent, str), f"Intent is not a string for: {field}"

    def test_every_field_has_non_empty_answer_type(self):
        """Every field has a non-empty answer_type string."""
        for field, spec in QUESTION_SPECS.items():
            assert spec.answer_type, f"Empty answer_type for field: {field}"
            assert isinstance(spec.answer_type, str), f"answer_type is not a string for: {field}"

    def test_every_field_has_non_empty_template(self):
        """Every field has a non-empty Egyptian Arabic template."""
        for field, spec in QUESTION_SPECS.items():
            assert spec.template, f"Empty template for field: {field}"
            assert isinstance(spec.template, str), f"Template is not a string for: {field}"

    def test_unknown_field_raises_error(self):
        """Unknown field raises UnknownQuestionFieldError."""
        with pytest.raises(UnknownQuestionFieldError, match="personal.unknown"):
            get_question_spec("personal.unknown")

    def test_unknown_field_error_lists_known_fields(self):
        """UnknownQuestionFieldError message includes known fields."""
        with pytest.raises(UnknownQuestionFieldError, match="Known fields"):
            get_question_spec("nonexistent.field")

    def test_policy_does_not_include_optional_fields(self):
        """Policy does not include optional fields like goal.target_weight_kg."""
        optional_fields = [
            "goal.target_weight_kg",
            "goal.weight_change_target_kg",
            "nutrition.food_preferences",
            "nutrition.disliked_foods",
            "nutrition.disliked_activities",
            "inbody.weight_kg",
            "inbody.body_fat_percent",
        ]
        for field in optional_fields:
            assert field not in QUESTION_SPECS, f"Optional field should not be in policy: {field}"

    def test_policy_is_deterministic(self):
        """Policy is deterministic: same input always yields same output."""
        for _ in range(10):
            spec = get_question_spec("personal.age")
            assert spec.field == "personal.age"
            assert spec.intent == "ask age"
            assert spec.template == "عندك كام سنة؟"

    def test_get_question_spec_returns_frozen_dataclass(self):
        """QuestionSpec is a frozen (immutable) dataclass."""
        spec = get_question_spec("personal.gender")
        with pytest.raises(AttributeError):
            spec.field = "modified"

    def test_exactly_10_specs(self):
        """There are exactly 10 question specs, one per required field."""
        assert len(QUESTION_SPECS) == 10

    def test_spec_count_matches_required_fields(self):
        """Number of specs equals number of required onboarding fields."""
        assert len(QUESTION_SPECS) == len(REQUIRED_ONBOARDING_FIELDS)
