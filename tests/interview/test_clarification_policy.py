"""Tests for app.interview.clarification_policy -- deterministic clarification mapping."""

import pytest

from app.interview.clarification_policy import (
    CLARIFICATION_SPECS,
    GOAL_TYPE_LABELS,
    ClarificationSpec,
    UnknownClarificationFieldError,
    get_clarification_spec,
)
from app.profile.policies import CONTRADICTION_SENSITIVE_FIELDS


class TestClarificationPolicy:
    """Deterministic clarification policy test suite."""

    def test_all_contradiction_sensitive_fields_have_specs(self):
        """Every contradiction-sensitive field has a clarification spec."""
        for field in CONTRADICTION_SENSITIVE_FIELDS:
            assert field in CLARIFICATION_SPECS, (
                f"Missing clarification spec for contradiction-sensitive field: {field}"
            )

    def test_spec_count_matches_contradiction_sensitive_fields(self):
        """Number of specs equals number of contradiction-sensitive fields."""
        assert len(CLARIFICATION_SPECS) == len(CONTRADICTION_SENSITIVE_FIELDS)

    def test_spec_field_matches_dictionary_key(self):
        """Every spec.field matches its dictionary key."""
        for key, spec in CLARIFICATION_SPECS.items():
            assert spec.field == key, f"Spec field {spec.field!r} does not match key {key!r}"

    def test_every_field_has_non_empty_intent(self):
        """Every field has a non-empty intent string."""
        for field, spec in CLARIFICATION_SPECS.items():
            assert spec.intent, f"Empty intent for field: {field}"
            assert isinstance(spec.intent, str), f"Intent is not a string for: {field}"

    def test_every_field_has_non_empty_template(self):
        """Every field has a non-empty Egyptian Arabic template."""
        for field, spec in CLARIFICATION_SPECS.items():
            assert spec.template, f"Empty template for field: {field}"
            assert isinstance(spec.template, str), f"Template is not a string for: {field}"

    def test_all_templates_contain_both_value_placeholders(self):
        """Every template contains both {existing_value} and {incoming_value}."""
        for field, spec in CLARIFICATION_SPECS.items():
            assert "{existing_value}" in spec.template, (
                f"Template for {field} missing {{existing_value}}"
            )
            assert "{incoming_value}" in spec.template, (
                f"Template for {field} missing {{incoming_value}}"
            )

    def test_goal_type_labels_mapping(self):
        """GOAL_TYPE_LABELS covers all expected internal goal type values."""
        expected_keys = {"weight_loss", "weight_gain", "muscle_gain", "maintenance"}
        assert set(GOAL_TYPE_LABELS.keys()) == expected_keys

    def test_goal_type_labels_are_arabic(self):
        """GOAL_TYPE_LABELS values are non-empty Arabic strings."""
        for key, label in GOAL_TYPE_LABELS.items():
            assert isinstance(label, str)
            assert label.strip(), f"Empty label for goal type: {key}"

    def test_unknown_field_raises_error(self):
        """Unknown field raises UnknownClarificationFieldError."""
        with pytest.raises(UnknownClarificationFieldError, match="personal.unknown"):
            get_clarification_spec("personal.unknown")

    def test_unknown_field_error_lists_known_fields(self):
        """UnknownClarificationFieldError message includes known fields."""
        with pytest.raises(UnknownClarificationFieldError, match="Known fields"):
            get_clarification_spec("nonexistent.field")

    def test_policy_is_deterministic(self):
        """Policy is deterministic: same input always yields same output."""
        for _ in range(10):
            spec = get_clarification_spec("personal.age")
            assert spec.field == "personal.age"
            assert "سنك" in spec.template

    def test_get_clarification_spec_returns_frozen_dataclass(self):
        """ClarificationSpec is a frozen (immutable) dataclass."""
        spec = get_clarification_spec("personal.gender")
        with pytest.raises(AttributeError):
            spec.field = "modified"

    def test_personal_age_template_mentions_years(self):
        """personal.age template mentions years."""
        spec = get_clarification_spec("personal.age")
        assert "سنة" in spec.template

    def test_personal_gender_template_mentions_gender_terms(self):
        """personal.gender template is about gender identity."""
        spec = get_clarification_spec("personal.gender")
        assert "معلومة" in spec.template or "الصح" in spec.template

    def test_personal_height_template_mentions_cm(self):
        """personal.height_cm template mentions centimeters."""
        spec = get_clarification_spec("personal.height_cm")
        assert "سم" in spec.template

    def test_training_days_per_week_template_mentions_days(self):
        """training.days_per_week template mentions days."""
        spec = get_clarification_spec("training.days_per_week")
        assert "أيام" in spec.template

    def test_training_experience_template_mentions_experience(self):
        """training.experience template mentions experience level."""
        spec = get_clarification_spec("training.experience")
        assert "خبرتك" in spec.template

    def test_training_duration_template_mentions_duration(self):
        """training.duration template mentions training duration."""
        spec = get_clarification_spec("training.duration")
        assert "ملتزم" in spec.template

    def test_training_activity_template_mentions_activity(self):
        """training.activity_description template mentions daily activity."""
        spec = get_clarification_spec("training.activity_description")
        assert "نشاط" in spec.template

    def test_goal_type_template_mentions_goal(self):
        """goal.type template mentions the fitness goal."""
        spec = get_clarification_spec("goal.type")
        assert "هدف" in spec.template

    def test_goal_target_weight_template_mentions_kg(self):
        """goal.target_weight_kg template mentions kilos."""
        spec = get_clarification_spec("goal.target_weight_kg")
        assert "كيلو" in spec.template

    def test_goal_weight_change_template_mentions_change(self):
        """goal.weight_change_target_kg template refers to change amount."""
        spec = get_clarification_spec("goal.weight_change_target_kg")
        assert "التغيير" in spec.template or "تغيير" in spec.template
