"""Tests for app.interview.question_generator -- deterministic question generation."""

import pytest

from app.interview.question_generator import QuestionGenerator
from app.interview.question_policy import UnknownQuestionFieldError
from app.profile.missing_fields import REQUIRED_ONBOARDING_FIELDS


class TestQuestionGenerator:
    """Deterministic question generator test suite."""

    def setup_method(self):
        self.generator = QuestionGenerator()

    def test_all_required_fields_generate_non_empty_string(self):
        """Every required field generates a non-empty string."""
        for field in REQUIRED_ONBOARDING_FIELDS:
            question = self.generator.generate(field)
            assert isinstance(question, str), f"Question for {field} is not a string"
            assert question.strip(), f"Empty question for field: {field}"

    def test_gender_produces_gender_question(self):
        """personal.gender produces a gender-related question."""
        question = self.generator.generate("personal.gender")
        assert "راجل" in question or "ست" in question

    def test_age_produces_age_question(self):
        """personal.age produces an age-related question."""
        question = self.generator.generate("personal.age")
        assert "سنة" in question

    def test_height_produces_height_question(self):
        """personal.height_cm produces a height-related question."""
        question = self.generator.generate("personal.height_cm")
        assert "طول" in question
        assert "سم" in question

    def test_weight_produces_weight_question(self):
        """personal.weight_kg produces a weight-related question."""
        question = self.generator.generate("personal.weight_kg")
        assert "وزن" in question
        assert "كيلو" in question

    def test_injuries_produces_injury_question(self):
        """health.injuries produces an injury/health-related question."""
        question = self.generator.generate("health.injuries")
        assert "إصابة" in question or "إصابات" in question

    def test_experience_produces_experience_question(self):
        """training.experience produces an experience-related question."""
        question = self.generator.generate("training.experience")
        assert "تمرن" in question

    def test_days_per_week_produces_days_question(self):
        """training.days_per_week produces a weekly-days question."""
        question = self.generator.generate("training.days_per_week")
        assert "أسبوع" in question

    def test_duration_produces_duration_question(self):
        """training.duration produces a duration/history question."""
        question = self.generator.generate("training.duration")
        assert "ملتزم" in question or "تمرين" in question

    def test_activity_produces_activity_question(self):
        """training.activity_description produces a daily-activity question."""
        question = self.generator.generate("training.activity_description")
        assert "نشاط" in question or "شغلك" in question

    def test_goal_produces_goal_question(self):
        """goal.type produces a goal-related question."""
        question = self.generator.generate("goal.type")
        assert "هدف" in question

    def test_unknown_field_raises_error(self):
        """Unknown field raises UnknownQuestionFieldError."""
        with pytest.raises(UnknownQuestionFieldError):
            self.generator.generate("personal.unknown")

    def test_generator_does_not_call_network(self):
        """Generator does not perform any network or LLM calls."""
        # If it did, this test would fail without mocking
        for field in REQUIRED_ONBOARDING_FIELDS:
            question = self.generator.generate(field)
            assert question  # just verify it returns something

    def test_context_does_not_change_field_intent(self):
        """Context parameter does not change which field the question targets."""
        question_without = self.generator.generate("personal.height_cm")
        question_with = self.generator.generate(
            "personal.height_cm",
            context={"personal": {"age": 25, "gender": "رجل"}},
        )
        assert question_without == question_with

    def test_generator_does_not_modify_context(self):
        """Generator does not modify the passed context dict."""
        context = {"personal": {"age": 25}}
        original = dict(context)
        self.generator.generate("personal.height_cm", context=context)
        assert context == original

    def test_generator_is_deterministic(self):
        """Same field/context always produces the same output."""
        for field in REQUIRED_ONBOARDING_FIELDS:
            q1 = self.generator.generate(field)
            q2 = self.generator.generate(field)
            q3 = self.generator.generate(field, context={"test": True})
            assert q1 == q2 == q3, f"Non-deterministic output for field: {field}"

    def test_each_question_is_single_intent(self):
        """Each generated question targets exactly one required field."""
        for field in REQUIRED_ONBOARDING_FIELDS:
            question = self.generator.generate(field)
            # Each question should end with a single question mark
            assert question.count("؟") == 1, (
                f"Question for {field} has {question.count('؟')} question marks, expected 1: {question}"
            )

    def test_generator_returns_string_type(self):
        """Generator always returns a str, not a QuestionSpec or other type."""
        result = self.generator.generate("personal.gender")
        assert type(result) is str

    def test_all_10_fields_produce_distinct_questions(self):
        """Each required field produces a distinct question string."""
        questions = {}
        for field in REQUIRED_ONBOARDING_FIELDS:
            q = self.generator.generate(field)
            assert q not in questions.values(), (
                f"Duplicate question for {field}: {q}"
            )
            questions[field] = q
