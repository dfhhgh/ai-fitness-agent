"""Deterministic tests for PROFILE_EXTRACTION_SYSTEM_PROMPT contract.

These tests verify the prompt contains required sections, rules, and examples
WITHOUT calling the LLM. They protect against accidental prompt regressions.
"""

import re

from app.llm.prompts import PROFILE_EXTRACTION_SYSTEM_PROMPT
from app.profile.policies import ALLOWED_UPDATE_PATHS


# ---------------------------------------------------------------------------
# Section presence
# ---------------------------------------------------------------------------

class TestPromptSections:
    """Verify all required sections exist in the prompt."""

    def test_strict_rules_section(self):
        assert "=== قواعد صارمة ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_output_format_section(self):
        assert "=== صيغة الإخراج ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_allowed_paths_section(self):
        assert "=== المسارات المسموح بها فقط ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_type_rules_section(self):
        assert "=== قواعد الأنواع ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_semantic_boundaries_section(self):
        assert "=== الحدود الدلالية ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_unknown_fields_section(self):
        assert "=== المعلومات غير المعروفة ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_conflicts_section(self):
        assert "=== التعارضات ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_messages_section(self):
        assert "=== الرسائل المتعددة الحقول ===" in PROFILE_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Strict rules
# ---------------------------------------------------------------------------

class TestStrictRules:
    """Verify the prompt contains all required strict rules."""

    def test_positive_extraction_mandate(self):
        """Rule: MUST extract all applicable fields from user message."""
        assert "استخرج كل حقل يمكن استخراجه من رسالة المستخدم" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_message_mandate(self):
        """Rule: MUST extract all fields when multiple appear in one message."""
        assert "استخرج جميعها في نفس الإخراج" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_inference_rule(self):
        assert "لا تستنتج معلومات لم يذكرها المستخدم" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_guessing_rule(self):
        assert "لا تخمّن" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_calorie_calculation_rule(self):
        assert "لا تحسب سعرات حرارية" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_workout_plan_rule(self):
        assert "لا تولّد خطة تمرين" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_extra_fields_rule(self):
        assert "لا تضف حقول لم يذكرها المستخدم" in PROFILE_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:
    """Verify the prompt defines the correct output structure."""

    def test_updates_key_in_format(self):
        assert '"updates"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_unknown_fields_key_in_format(self):
        assert '"unknown_fields"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_conflicts_key_in_format(self):
        assert '"conflicts"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_populated_example_exists(self):
        """Output format section must show a populated example, not just empty."""
        # Find the section after "=== صيغة الإخراج ==="
        idx = PROFILE_EXTRACTION_SYSTEM_PROMPT.index("=== صيغة الإخراج ===")
        section = PROFILE_EXTRACTION_SYSTEM_PROMPT[idx:]
        # Must contain a non-empty updates example
        assert '"personal.age": 25' in section or '"personal.age":25' in section

    def test_no_markdown_instruction(self):
        assert "بدون Markdown" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_json_fences_instruction(self):
        assert "بدون ```json" in PROFILE_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Allowed paths match policies.py
# ---------------------------------------------------------------------------

class TestAllowedPaths:
    """Verify the prompt's allowed paths match the authoritative ALLOWED_UPDATE_PATHS."""

    def test_all_allowed_paths_listed_in_prompt(self):
        """Every path in ALLOWED_UPDATE_PATHS must appear in the prompt."""
        for path in ALLOWED_UPDATE_PATHS:
            assert path in PROFILE_EXTRACTION_SYSTEM_PROMPT, (
                f"Allowed path '{path}' missing from prompt"
            )

    def test_prompt_does_not_add_extra_paths(self):
        """Extract all paths listed in the prompt's allowed paths section and verify
        they are all in ALLOWED_UPDATE_PATHS."""
        idx = PROFILE_EXTRACTION_SYSTEM_PROMPT.index("=== المسارات المسموح بها فقط ===")
        end_idx = PROFILE_EXTRACTION_SYSTEM_PROMPT.index("===", idx + 10)
        paths_section = PROFILE_EXTRACTION_SYSTEM_PROMPT[idx:end_idx]

        prompt_paths = set()
        for line in paths_section.splitlines():
            line = line.strip()
            if line and "." in line and not line.startswith("="):
                prompt_paths.add(line)

        for path in prompt_paths:
            assert path in ALLOWED_UPDATE_PATHS, (
                f"Prompt lists '{path}' but it is not in ALLOWED_UPDATE_PATHS"
            )


# ---------------------------------------------------------------------------
# Semantic boundary rules
# ---------------------------------------------------------------------------

class TestSemanticBoundaries:
    """Verify semantic boundary rules are present and correct."""

    def test_current_weight_rule(self):
        assert '"وزني 85 كيلو" → personal.weight_kg = 85' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_target_weight_rule(self):
        assert '"عايز أوصل لـ 75 كيلو" → goal.target_weight_kg = 75' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_target_weight_not_current_weight(self):
        assert "لا تضع 75 في personal.weight_kg" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_weight_loss_amount_rule(self):
        assert '"عايز أخس 10 كيلو" → goal.type = "weight_loss", goal.weight_change_target_kg = 10' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_weight_loss_not_current_weight(self):
        assert "لا تضع 10 في personal.weight_kg" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_training_days_rule(self):
        assert '"بتمرن 4 أيام في الأسبوع" → training.days_per_week = 4' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_training_duration_rule(self):
        assert '"بقالي شهرين في الجيم" → training.duration = "2 months"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_duration_not_experience(self):
        assert "لا تضع هذا في training.experience" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_experience_requires_explicit_mention(self):
        assert "فقط عندما يذكر المستخدم مستواه صراحةً" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_experience_examples(self):
        assert '"أنا مبتدئ" → training.experience = "beginner"' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert '"أنا متوسط" → training.experience = "intermediate"' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert '"أنا متقدم" → training.experience = "advanced"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_duration_does_not_imply_experience(self):
        assert '"بقالي شهرين في الجيم" بمفردها لا تعني مبتدئ' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_goal_weight_loss(self):
        assert '"عايز أخس" → goal.type = "weight_loss"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_goal_weight_gain(self):
        assert '"عايز أزيد وزني" → goal.type = "weight_gain"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_goal_muscle_gain(self):
        assert '"عايز أعمل muscle gain" → goal.type = "muscle_gain"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_goal_without_explicit_mention(self):
        assert "لا تخترع goal.type" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_activity_description_rule(self):
        assert '"شغلي مكتبي" → training.activity_description = "مكتبي"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_injuries_rule(self):
        assert '"معنديش إصابات" → health.injuries = []' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_injuries_with_values_rule(self):
        assert '"عندي إصابة في الركبة" → health.injuries = ["إصابة في الركبة"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_no_injuries_when_not_mentioned(self):
        assert "إذا لم يذكر الإصابات، لا تضف health.injuries" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_food_preferences_rule(self):
        assert '"بحب الفراخ والرز ومبحبش السمك"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_disliked_foods_rule(self):
        assert 'nutrition.disliked_foods = ["السمك"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_disliked_activities_rule(self):
        assert '"مش بحب الجري" → nutrition.disliked_activities = ["الجري"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_unknown_fields_rule(self):
        assert '"مش عارف وزني" → unknown_fields قد تحتوي "personal.weight_kg"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_conflict_detection_rule(self):
        assert '"وزني 85، لا استنى 90"' in PROFILE_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Compound message examples
# ---------------------------------------------------------------------------

class TestCompoundMessageExamples:
    """Verify compound message examples are present and correct."""

    def test_compound_training_goal_example(self):
        """The exact failing case: training + duration + weight loss."""
        example = "بتمرن 4 أيام في الأسبوع وبقالي شهرين في الجيم وعايز أخس 10 كيلو"
        assert example in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_training_goal_extracts_all_fields(self):
        """Verify the compound example specifies all expected extractions."""
        assert "training.days_per_week = 4" in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert 'training.duration = "2 months"' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert 'goal.type = "weight_loss"' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert "goal.weight_change_target_kg = 10" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_personal_example(self):
        """Multiple personal fields in one message."""
        assert "أنا 25 سنة وطول 175 سم ووزن 85 كيلو" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_nutrition_health_example(self):
        """Nutrition + health in one message."""
        assert "بحب الفراخ ومبحبش السمك وعندي إصابة في الركبة" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_compound_example_extracts_all_fields(self):
        """Verify nutrition+health example specifies all extractions."""
        assert 'nutrition.food_preferences = ["الفراخ"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert 'nutrition.disliked_foods = ["السمك"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT
        assert 'health.injuries = ["إصابة في الركبة"]' in PROFILE_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Type rules
# ---------------------------------------------------------------------------

class TestTypeRules:
    """Verify type coercion rules are present."""

    def test_numeric_values_must_be_numbers(self):
        assert "القيم الرقمية يجب أن تكون أرقام JSON وليست نصوص" in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_age_type_example(self):
        assert '"personal.age": 25' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_height_type_example(self):
        assert '"personal.height_cm": 175' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_weight_type_example(self):
        assert '"personal.weight_kg": 85' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_days_type_example(self):
        assert '"training.days_per_week": 4' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_string_age_is_wrong(self):
        assert 'خطأ: "personal.age": "25"' in PROFILE_EXTRACTION_SYSTEM_PROMPT

    def test_int_age_is_correct(self):
        assert 'صح: "personal.age": 25' in PROFILE_EXTRACTION_SYSTEM_PROMPT
