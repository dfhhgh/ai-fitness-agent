"""Tests for app.interview.clarification_generator -- deterministic clarification generation."""

import pytest

from app.interview.clarification_generator import ClarificationGenerator
from app.profile.conflicts import Conflict
from app.interview.clarification_policy import UnknownClarificationFieldError
from app.profile.policies import CONTRADICTION_SENSITIVE_FIELDS


class TestClarificationGenerator:
    """Deterministic clarification generator test suite."""

    def setup_method(self):
        self.generator = ClarificationGenerator()

    def _make_conflict(self, path: str, existing: object, incoming: object) -> Conflict:
        """Helper to create a Conflict with a standard reason."""
        return Conflict(
            path=path,
            existing_value=existing,
            incoming_value=incoming,
            reason="existing_value_conflicts_with_incoming_value",
        )

    # --- Every contradiction-sensitive field ---

    def test_all_contradiction_sensitive_fields_generate_output(self):
        """Every contradiction-sensitive field can generate a clarification string."""
        for field in CONTRADICTION_SENSITIVE_FIELDS:
            conflict = self._make_conflict(field, "a", "b")
            result = self.generator.generate(conflict)
            assert isinstance(result, str)
            assert result.strip(), f"Empty clarification for field: {field}"

    # --- Specific field content tests ---

    def test_personal_age_egyptian_arabic(self):
        """personal.age produces Egyptian Arabic clarification."""
        conflict = self._make_conflict("personal.age", 25, 30)
        result = self.generator.generate(conflict)
        assert "سنك 25 سنة" in result
        assert "بتقول 30 سنة" in result
        assert "تحب نعتمد أنهي سن" in result

    def test_personal_gender_egyptian_arabic(self):
        """personal.gender produces clarification with gender terms."""
        conflict = self._make_conflict("personal.gender", "راجل", "ست")
        result = self.generator.generate(conflict)
        assert "راجل" in result
        assert "ست" in result
        assert "الصح" in result

    def test_personal_height_cm_includes_cm(self):
        """personal.height_cm produces clarification mentioning centimeters."""
        conflict = self._make_conflict("personal.height_cm", 175.0, 180.0)
        result = self.generator.generate(conflict)
        assert "طولك 175 سم" in result
        assert "بتقول 180 سم" in result
        assert "سم" in result

    def test_training_days_per_week_includes_days(self):
        """training.days_per_week produces clarification mentioning days."""
        conflict = self._make_conflict("training.days_per_week", 3, 5)
        result = self.generator.generate(conflict)
        assert "3 أيام" in result
        assert "5 أيام" in result
        assert "أسبوع" in result

    def test_training_experience_egyptian_arabic(self):
        """training.experience produces clarification."""
        conflict = self._make_conflict("training.experience", "مبتدئ", "متوسط")
        result = self.generator.generate(conflict)
        assert "مبتدئ" in result
        assert "متوسط" in result
        assert "خبرتك" in result

    def test_training_duration_egyptian_arabic(self):
        """training.duration produces clarification."""
        conflict = self._make_conflict("training.duration", "6 شهور", "سنتين")
        result = self.generator.generate(conflict)
        assert "6 شهور" in result
        assert "سنتين" in result
        assert "ملتزم" in result

    def test_training_activity_description_egyptian_arabic(self):
        """training.activity_description produces clarification."""
        conflict = self._make_conflict(
            "training.activity_description", "مكتبي", "بتحرك كتير"
        )
        result = self.generator.generate(conflict)
        assert "مكتبي" in result
        assert "بتحرك كتير" in result
        assert "نشاط" in result

    def test_goal_type_converts_weight_loss(self):
        """goal.type converts internal 'weight_loss' to Arabic label."""
        conflict = self._make_conflict("goal.type", "weight_loss", "muscle_gain")
        result = self.generator.generate(conflict)
        assert "خسارة الوزن" in result
        assert "بناء العضلات" in result
        assert "هدف" in result

    def test_goal_type_converts_weight_gain(self):
        """goal.type converts internal 'weight_gain' to Arabic label."""
        conflict = self._make_conflict("goal.type", "weight_gain", "maintenance")
        result = self.generator.generate(conflict)
        assert "زيد الوزن" in result
        assert "الحفاظ على الوزن" in result

    def test_goal_type_converts_muscle_gain(self):
        """goal.type converts internal 'muscle_gain' to Arabic label."""
        conflict = self._make_conflict("goal.type", "muscle_gain", "weight_loss")
        result = self.generator.generate(conflict)
        assert "بناء العضلات" in result
        assert "خسارة الوزن" in result

    def test_goal_type_converts_maintenance(self):
        """goal.type converts internal 'maintenance' to Arabic label."""
        conflict = self._make_conflict("goal.type", "maintenance", "weight_gain")
        result = self.generator.generate(conflict)
        assert "الحفاظ على الوزن" in result
        assert "زيد الوزن" in result

    def test_goal_target_weight_kg_includes_kg(self):
        """goal.target_weight_kg produces clarification mentioning kilos."""
        conflict = self._make_conflict("goal.target_weight_kg", 80.0, 75.0)
        result = self.generator.generate(conflict)
        assert "80 كيلو" in result
        assert "75 كيلو" in result
        assert "المستهدف" in result

    def test_goal_weight_change_target_kg_clearly_refers_to_change(self):
        """goal.weight_change_target_kg refers to change amount, not current weight."""
        conflict = self._make_conflict("goal.weight_change_target_kg", 10.0, 5.0)
        result = self.generator.generate(conflict)
        assert "10 كيلو" in result
        assert "5 كيلو" in result
        assert "التغيير" in result or "تغيير" in result

    # --- Numeric formatting ---

    def test_integer_like_floats_display_without_decimal(self):
        """25.0 displays as '25', 175.0 as '175', 85.0 as '85'."""
        conflict = self._make_conflict("personal.age", 25.0, 30.0)
        result = self.generator.generate(conflict)
        assert "25 سنة" in result
        assert "30 سنة" in result
        assert "25.0" not in result
        assert "30.0" not in result

    def test_height_floats_no_trailing_decimal(self):
        """Height values like 175.0 display as '175'."""
        conflict = self._make_conflict("personal.height_cm", 175.0, 180.0)
        result = self.generator.generate(conflict)
        assert "175 سم" in result
        assert "180 سم" in result
        assert "175.0" not in result
        assert "180.0" not in result

    def test_weight_floats_no_trailing_decimal(self):
        """Weight values like 85.0 display as '85'."""
        conflict = self._make_conflict("goal.target_weight_kg", 85.0, 80.0)
        result = self.generator.generate(conflict)
        assert "85 كيلو" in result
        assert "80 كيلو" in result
        assert "85.0" not in result
        assert "80.0" not in result

    def test_non_integer_floats_keep_decimal(self):
        """Non-integer floats keep their decimal (e.g. 175.5)."""
        conflict = self._make_conflict("personal.height_cm", 175.5, 180.5)
        result = self.generator.generate(conflict)
        assert "175.5 سم" in result
        assert "180.5 سم" in result

    # --- Unknown field ---

    def test_unknown_field_raises_error(self):
        """Unknown field raises UnknownClarificationFieldError."""
        conflict = self._make_conflict("personal.unknown", "a", "b")
        with pytest.raises(UnknownClarificationFieldError, match="personal.unknown"):
            self.generator.generate(conflict)

    # --- Conflict immutability ---

    def test_generator_does_not_mutate_conflict(self):
        """Generator does not mutate the Conflict object."""
        conflict = self._make_conflict("personal.age", 25, 30)
        original_path = conflict.path
        original_existing = conflict.existing_value
        original_incoming = conflict.incoming_value
        original_reason = conflict.reason

        self.generator.generate(conflict)

        assert conflict.path == original_path
        assert conflict.existing_value == original_existing
        assert conflict.incoming_value == original_incoming
        assert conflict.reason == original_reason

    # --- Determinism ---

    def test_generator_is_deterministic(self):
        """Same Conflict always produces the same output."""
        conflict = self._make_conflict("personal.age", 25, 30)
        results = [self.generator.generate(conflict) for _ in range(10)]
        assert len(set(results)) == 1

    # --- Communication of both values and choice ---

    def test_personal_age_communicates_both_values_and_choice(self):
        """Age clarification presents both values and asks user to choose."""
        conflict = self._make_conflict("personal.age", 25, 30)
        result = self.generator.generate(conflict)
        assert "25" in result
        assert "30" in result
        assert "إنت دلوقتي بتقول" in result

    def test_personal_gender_communicates_both_values_and_choice(self):
        """Gender clarification presents both values and asks user to choose."""
        conflict = self._make_conflict("personal.gender", "راجل", "ست")
        result = self.generator.generate(conflict)
        assert "راجل" in result
        assert "ست" in result
        assert "إنت دلوقتي بتقول" in result

    def test_height_communicates_both_values_and_choice(self):
        """Height clarification presents both values and asks user to choose."""
        conflict = self._make_conflict("personal.height_cm", 175, 180)
        result = self.generator.generate(conflict)
        assert "175" in result
        assert "180" in result
        assert "إنت دلوقتي بتقول" in result

    def test_days_per_week_communicates_both_values_and_choice(self):
        """Days per week clarification presents both values and asks to choose."""
        conflict = self._make_conflict("training.days_per_week", 3, 5)
        result = self.generator.generate(conflict)
        assert "3" in result
        assert "5" in result
        assert "إنت دلوقتي بتقول" in result

    def test_experience_communicates_both_values_and_choice(self):
        """Experience clarification presents both values and asks to choose."""
        conflict = self._make_conflict("training.experience", "مبتدئ", "متوسط")
        result = self.generator.generate(conflict)
        assert "مبتدئ" in result
        assert "متوسط" in result
        assert "إنت دلوقتي بتقول" in result

    def test_duration_communicates_both_values_and_choice(self):
        """Duration clarification presents both values and asks to choose."""
        conflict = self._make_conflict("training.duration", "6 شهور", "سنتين")
        result = self.generator.generate(conflict)
        assert "6 شهور" in result
        assert "سنتين" in result
        assert "إنت دلوقتي بتقول" in result

    def test_activity_description_communicates_both_values_and_choice(self):
        """Activity clarification presents both values and asks to choose."""
        conflict = self._make_conflict(
            "training.activity_description", "مكتبي", "بتحرك كتير"
        )
        result = self.generator.generate(conflict)
        assert "مكتبي" in result
        assert "بتحرك كتير" in result
        assert "إنت دلوقتي بتقول" in result

    def test_goal_type_communicates_both_values_and_choice(self):
        """Goal type clarification presents both values and asks to choose."""
        conflict = self._make_conflict("goal.type", "weight_loss", "muscle_gain")
        result = self.generator.generate(conflict)
        assert "خسارة الوزن" in result
        assert "بناء العضلات" in result
        assert "إنت دلوقتي بتقول" in result

    def test_target_weight_communicates_both_values_and_choice(self):
        """Target weight clarification presents both values and asks to choose."""
        conflict = self._make_conflict("goal.target_weight_kg", 80, 75)
        result = self.generator.generate(conflict)
        assert "80 كيلو" in result
        assert "75 كيلو" in result
        assert "إنت دلوقتي بتقول" in result

    def test_weight_change_communicates_both_values_and_choice(self):
        """Weight change clarification presents both values and asks to choose."""
        conflict = self._make_conflict("goal.weight_change_target_kg", 10, 5)
        result = self.generator.generate(conflict)
        assert "10 كيلو" in result
        assert "5 كيلو" in result
        assert "إنت دلوقتي بتقول" in result

    def test_each_clarification_has_single_question_mark(self):
        """Each clarification has exactly one question mark."""
        for field in CONTRADICTION_SENSITIVE_FIELDS:
            conflict = self._make_conflict(field, "a", "b")
            result = self.generator.generate(conflict)
            assert result.count("؟") == 1, (
                f"Clarification for {field} has {result.count('؟')} question marks: {result}"
            )

    def test_generator_returns_string_type(self):
        """Generator always returns a str."""
        conflict = self._make_conflict("personal.age", 25, 30)
        result = self.generator.generate(conflict)
        assert type(result) is str
