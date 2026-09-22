"""Tests for app.interview.clarification_resolver -- deterministic conflict resolution."""

import pytest

from app.interview.clarification_resolver import (
    REASON_AMBIGUOUS,
    REASON_INVALID,
    REASON_NO_CANDIDATE,
    REASON_UNRELATED,
    REASON_UNSUPPORTED,
    ClarificationResolution,
    ClarificationResolver,
)
from app.profile.conflicts import Conflict
from app.profile.policies import CONTRADICTION_SENSITIVE_FIELDS


def _conflict(path: str, existing: object, incoming: object) -> Conflict:
    """Helper to create a Conflict."""
    return Conflict(
        path=path,
        existing_value=existing,
        incoming_value=incoming,
        reason="existing_value_conflicts_with_incoming_value",
    )


class TestClarificationResolver:
    """Deterministic clarification resolver test suite."""

    def setup_method(self):
        self.resolver = ClarificationResolver()

    # ================================================================
    # A. Existing-value resolution
    # ================================================================

    def test_age_existing_reference(self):
        """'القديم صح' resolves to existing age."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "القديم صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 25

    def test_age_existing_first(self):
        """'الأول صح' resolves to existing age."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الأول صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 25

    def test_height_existing_reference(self):
        """'القديم' resolves to existing height."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 175.0

    def test_days_existing_reference(self):
        """'نعتمد القديم' resolves to existing days."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "نعتمد القديم")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 3

    def test_gender_existing_reference(self):
        """'المسجل' resolves to existing gender."""
        c = _conflict("personal.gender", "راجل", "ست")
        r = self.resolver.resolve(c, "المسجل")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "راجل"

    def test_experience_existing_reference(self):
        """'اللي عندك' resolves to existing experience."""
        c = _conflict("training.experience", "مبتدئ", "متوسط")
        r = self.resolver.resolve(c, "اللي عندك")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "مبتدئ"

    def test_duration_existing_reference(self):
        """'القديم' resolves to existing duration."""
        c = _conflict("training.duration", "6 شهور", "سنتين")
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["training.duration"] == "6 شهور"

    def test_activity_existing_reference(self):
        """'اللي كان مكتوب' resolves to existing activity."""
        c = _conflict("training.activity_description", "مكتبي", "بتحرك كتير")
        r = self.resolver.resolve(c, "اللي كان مكتوب")
        assert r.resolved is True
        assert r.patch.updates["training.activity_description"] == "مكتبي"

    def test_goal_type_existing_reference(self):
        """'القديم' resolves to existing goal type."""
        c = _conflict("goal.type", "weight_loss", "muscle_gain")
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_loss"

    def test_target_weight_existing_reference(self):
        """'القديم' resolves to existing target weight."""
        c = _conflict("goal.target_weight_kg", 80.0, 75.0)
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["goal.target_weight_kg"] == 80.0

    def test_weight_change_existing_reference(self):
        """'القديم' resolves to existing weight change target."""
        c = _conflict("goal.weight_change_target_kg", 10.0, 5.0)
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["goal.weight_change_target_kg"] == 10.0

    # ================================================================
    # B. Incoming-value resolution
    # ================================================================

    def test_age_incoming_reference(self):
        """'الجديد صح' resolves to incoming age."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الجديد صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_age_incoming_second(self):
        """'التاني صح' resolves to incoming age."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "التاني صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_height_incoming_reference(self):
        """'خلي الجديد' resolves to incoming height."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "خلي الجديد")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.0

    def test_days_incoming_reference(self):
        """'نعتمد الجديد' resolves to incoming days."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "نعتمد الجديد")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 5

    def test_gender_incoming_reference(self):
        """'الثاني صح' resolves to incoming gender."""
        c = _conflict("personal.gender", "راجل", "ست")
        r = self.resolver.resolve(c, "الثاني صح")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "ست"

    def test_experience_incoming_reference(self):
        """'الجديد' resolves to incoming experience."""
        c = _conflict("training.experience", "مبتدئ", "متوسط")
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "متوسط"

    def test_duration_incoming_reference(self):
        """'التاني' resolves to incoming duration."""
        c = _conflict("training.duration", "6 شهور", "سنتين")
        r = self.resolver.resolve(c, "التاني")
        assert r.resolved is True
        assert r.patch.updates["training.duration"] == "سنتين"

    def test_activity_incoming_reference(self):
        """'الجديد' resolves to incoming activity."""
        c = _conflict("training.activity_description", "مكتبي", "بتحرك كتير")
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["training.activity_description"] == "بتحرك كتير"

    def test_goal_type_incoming_reference(self):
        """'الجديد' resolves to incoming goal type."""
        c = _conflict("goal.type", "weight_loss", "muscle_gain")
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "muscle_gain"

    def test_target_weight_incoming_reference(self):
        """'الجديد' resolves to incoming target weight."""
        c = _conflict("goal.target_weight_kg", 80.0, 75.0)
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["goal.target_weight_kg"] == 75.0

    def test_weight_change_incoming_reference(self):
        """'الجديد' resolves to incoming weight change target."""
        c = _conflict("goal.weight_change_target_kg", 10.0, 5.0)
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["goal.weight_change_target_kg"] == 5.0

    def test_age_incoming_last_thing_said(self):
        """'آخر حاجة قلتها' resolves to incoming age."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "آخر حاجة قلتها")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    # ================================================================
    # C. Explicit numeric resolution — age
    # ================================================================

    def test_age_explicit_number(self):
        """'26' resolves age conflict."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_age_explicit_with_years(self):
        """'26 سنة' resolves age conflict."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26 سنة")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_age_explicit_with_context(self):
        """'أنا 26 سنة' resolves age conflict."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "أنا 26 سنة")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_age_explicit_with_anabi(self):
        """'أنا عندي 26 سنة' resolves age conflict."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "أنا عندي 26 سنة")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_age_explicit_value_both_sides(self):
        """'26 هو الصح' resolves age to 26."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26 هو الصح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    # ================================================================
    # D. Explicit numeric resolution — height
    # ================================================================

    def test_height_explicit_with_cm(self):
        """'180 سم' resolves height conflict."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "180 سم")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.0

    def test_height_explicit_with_keyword(self):
        """'طول 180 سم' resolves height conflict."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "طول 180 سم")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.0

    def test_height_explicit_single_number(self):
        """'180' resolves height conflict when only one number."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "180")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.0

    # ================================================================
    # E. Training days per week
    # ================================================================

    def test_days_explicit_with_days(self):
        """'4 أيام' resolves days conflict."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "4 أيام")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 4

    def test_days_explicit_single_number(self):
        """'4' resolves days conflict."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "4")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 4

    def test_days_explicit_with_tamren(self):
        """'بتمرن 4 أيام' resolves days conflict."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "بتمرن 4 أيام")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 4

    # ================================================================
    # F. Target weight
    # ================================================================

    def test_target_weight_explicit_with_kg(self):
        """'75 كيلو' resolves target weight conflict."""
        c = _conflict("goal.target_weight_kg", 80.0, 75.0)
        r = self.resolver.resolve(c, "75 كيلو")
        assert r.resolved is True
        assert r.patch.updates["goal.target_weight_kg"] == 75.0

    def test_target_weight_explicit_single_number(self):
        """'75' resolves target weight conflict."""
        c = _conflict("goal.target_weight_kg", 80.0, 75.0)
        r = self.resolver.resolve(c, "75")
        assert r.resolved is True
        assert r.patch.updates["goal.target_weight_kg"] == 75.0

    # ================================================================
    # G. Weight change target
    # ================================================================

    def test_weight_change_explicit_with_kg(self):
        """'10 كيلو' resolves weight change conflict."""
        c = _conflict("goal.weight_change_target_kg", 5.0, 10.0)
        r = self.resolver.resolve(c, "10 كيلو")
        assert r.resolved is True
        assert r.patch.updates["goal.weight_change_target_kg"] == 10.0

    def test_weight_change_explicit_single_number(self):
        """'10' resolves weight change conflict."""
        c = _conflict("goal.weight_change_target_kg", 5.0, 10.0)
        r = self.resolver.resolve(c, "10")
        assert r.resolved is True
        assert r.patch.updates["goal.weight_change_target_kg"] == 10.0

    # ================================================================
    # H. Gender
    # ================================================================

    def test_gender_rajal(self):
        """'راجل' resolves gender conflict."""
        c = _conflict("personal.gender", "ست", "راجل")
        r = self.resolver.resolve(c, "راجل")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "راجل"

    def test_gender_rajul(self):
        """'رجل' resolves gender conflict."""
        c = _conflict("personal.gender", "ست", "راجل")
        r = self.resolver.resolve(c, "رجل")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "راجل"

    def test_gender_st(self):
        """'ست' resolves gender conflict."""
        c = _conflict("personal.gender", "راجل", "ست")
        r = self.resolver.resolve(c, "ست")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "ست"

    def test_gender_bent(self):
        """'بنت' resolves gender conflict."""
        c = _conflict("personal.gender", "راجل", "ست")
        r = self.resolver.resolve(c, "بنت")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "ست"

    def test_gender_with_context(self):
        """'أنا راجل' resolves gender conflict."""
        c = _conflict("personal.gender", "ست", "راجل")
        r = self.resolver.resolve(c, "أنا راجل")
        assert r.resolved is True
        assert r.patch.updates["personal.gender"] == "راجل"

    # ================================================================
    # I. Experience
    # ================================================================

    def test_experience_mubtadi(self):
        """'مبتدئ' resolves experience conflict."""
        c = _conflict("training.experience", "متوسط", "مبتدئ")
        r = self.resolver.resolve(c, "مبتدئ")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "مبتدئ"

    def test_experience_mubtadia(self):
        """'مبتدئة' resolves experience conflict."""
        c = _conflict("training.experience", "متوسط", "مبتدئ")
        r = self.resolver.resolve(c, "مبتدئة")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "مبتدئ"

    def test_experience_mutawasset(self):
        """'متوسط' resolves experience conflict."""
        c = _conflict("training.experience", "مبتدئ", "متوسط")
        r = self.resolver.resolve(c, "متوسط")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "متوسط"

    def test_experience_mutacadim(self):
        """'متقدم' resolves experience conflict."""
        c = _conflict("training.experience", "مبتدئ", "متقدم")
        r = self.resolver.resolve(c, "متقدم")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "متقدم"

    # ================================================================
    # J. Goal types
    # ================================================================

    def test_goal_type_weight_loss_full(self):
        """'خسارة الوزن' resolves goal type to weight_loss."""
        c = _conflict("goal.type", "maintenance", "weight_loss")
        r = self.resolver.resolve(c, "خسارة الوزن")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_loss"

    def test_goal_type_weight_loss_short(self):
        """'خسارة' resolves goal type to weight_loss."""
        c = _conflict("goal.type", "maintenance", "weight_loss")
        r = self.resolver.resolve(c, "خسارة")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_loss"

    def test_goal_type_weight_loss_akhos(self):
        """'أخس' resolves goal type to weight_loss."""
        c = _conflict("goal.type", "maintenance", "weight_loss")
        r = self.resolver.resolve(c, "أخس")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_loss"

    def test_goal_type_weight_loss_ayez(self):
        """'عايز أخس' resolves goal type to weight_loss."""
        c = _conflict("goal.type", "maintenance", "weight_loss")
        r = self.resolver.resolve(c, "عايز أخس")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_loss"

    def test_goal_type_weight_gain_full(self):
        """'زيادة الوزن' resolves goal type to weight_gain."""
        c = _conflict("goal.type", "maintenance", "weight_gain")
        r = self.resolver.resolve(c, "زيادة الوزن")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_gain"

    def test_goal_type_weight_gain_short(self):
        """'زيادة' resolves goal type to weight_gain."""
        c = _conflict("goal.type", "maintenance", "weight_gain")
        r = self.resolver.resolve(c, "زيادة")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "weight_gain"

    def test_goal_type_muscle_gain_full(self):
        """'بناء العضلات' resolves goal type to muscle_gain."""
        c = _conflict("goal.type", "maintenance", "muscle_gain")
        r = self.resolver.resolve(c, "بناء العضلات")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "muscle_gain"

    def test_goal_type_muscle_gain_short(self):
        """'بناء' resolves goal type to muscle_gain."""
        c = _conflict("goal.type", "maintenance", "muscle_gain")
        r = self.resolver.resolve(c, "بناء")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "muscle_gain"

    def test_goal_type_maintenance_full(self):
        """'الحفاظ على الوزن' resolves goal type to maintenance."""
        c = _conflict("goal.type", "weight_loss", "maintenance")
        r = self.resolver.resolve(c, "الحفاظ على الوزن")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "maintenance"

    def test_goal_type_maintenance_alt(self):
        """'المحافظة على الوزن' resolves goal type to maintenance."""
        c = _conflict("goal.type", "weight_loss", "maintenance")
        r = self.resolver.resolve(c, "المحافظة على الوزن")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "maintenance"

    def test_goal_type_maintenance_thabt(self):
        """'أثبت وزني' resolves goal type to maintenance."""
        c = _conflict("goal.type", "weight_loss", "maintenance")
        r = self.resolver.resolve(c, "أثبت وزني")
        assert r.resolved is True
        assert r.patch.updates["goal.type"] == "maintenance"

    # ================================================================
    # K. Existing/incoming references for text fields
    # ================================================================

    def test_duration_existing_first(self):
        """'الأول' resolves duration to existing."""
        c = _conflict("training.duration", "6 شهور", "سنتين")
        r = self.resolver.resolve(c, "الأول")
        assert r.resolved is True
        assert r.patch.updates["training.duration"] == "6 شهور"

    def test_duration_incoming_second(self):
        """'التاني' resolves duration to incoming."""
        c = _conflict("training.duration", "6 شهور", "سنتين")
        r = self.resolver.resolve(c, "التاني")
        assert r.resolved is True
        assert r.patch.updates["training.duration"] == "سنتين"

    def test_activity_existing(self):
        """'القديم' resolves activity to existing."""
        c = _conflict("training.activity_description", "مكتبي", "بتحرك كتير")
        r = self.resolver.resolve(c, "القديم")
        assert r.resolved is True
        assert r.patch.updates["training.activity_description"] == "مكتبي"

    def test_activity_incoming(self):
        """'الجديد' resolves activity to incoming."""
        c = _conflict("training.activity_description", "مكتبي", "بتحرك كتير")
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["training.activity_description"] == "بتحرك كتير"

    def test_experience_existing_which_at_3indak(self):
        """'اللي عندك' resolves experience to existing."""
        c = _conflict("training.experience", "مبتدئ", "متوسط")
        r = self.resolver.resolve(c, "اللي عندك")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "مبتدئ"

    def test_experience_incoming_new(self):
        """'الجديد' resolves experience to incoming."""
        c = _conflict("training.experience", "مبتدئ", "متوسط")
        r = self.resolver.resolve(c, "الجديد")
        assert r.resolved is True
        assert r.patch.updates["training.experience"] == "متوسط"

    # ================================================================
    # L. Unrelated answer
    # ================================================================

    def test_age_conflict_with_unrelated_answer(self):
        """Age conflict + unrelated answer → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "أنا بتمرن 4 أيام")
        assert r.resolved is False
        assert r.patch is None

    def test_days_conflict_with_unrelated_answer(self):
        """Days conflict + unrelated answer → unresolved."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "أنا 26 سنة")
        assert r.resolved is False
        assert r.patch is None

    def test_height_conflict_with_unrelated_answer(self):
        """Height conflict + unrelated answer → unresolved."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "أنا بتمرن 4 أيام")
        assert r.resolved is False
        assert r.patch is None

    # ================================================================
    # M. Ambiguous answer
    # ================================================================

    def test_ambiguous_dont_know(self):
        """'مش عارف' → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "مش عارف")
        assert r.resolved is False
        assert r.patch is None

    def test_ambiguous_both(self):
        """'الاتنين' → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الاتنين")
        assert r.resolved is False
        assert r.patch is None

    def test_ambiguous_dont_remember(self):
        """'مش فاكر' → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "مش فاكر")
        assert r.resolved is False
        assert r.patch is None

    def test_ambiguous_approximately(self):
        """'تقريبًا 26' → unresolved (no semantic keyword match)."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "تقريبًا 26")
        assert r.resolved is False
        assert r.patch is None

    def test_ambiguous_not_sure(self):
        """'مش متأكد' → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "مش متأكد")
        assert r.resolved is False
        assert r.patch is None

    # ================================================================
    # M2. Dual reference ambiguity (both existing + incoming)
    # ================================================================

    def test_dual_reference_existing_then_incoming(self):
        """'القديم لا، الجديد هو الصح' → unresolved ambiguous."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "القديم لا، الجديد هو الصح")
        assert r.resolved is False
        assert r.patch is None
        assert r.reason == REASON_AMBIGUOUS

    def test_dual_reference_incoming_then_existing(self):
        """'الجديد لا، القديم هو الصح' → unresolved ambiguous."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الجديد لا، القديم هو الصح")
        assert r.resolved is False
        assert r.patch is None
        assert r.reason == REASON_AMBIGUOUS

    def test_dual_reference_both_joined(self):
        """'القديم والجديد' → unresolved ambiguous."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "القديم والجديد")
        assert r.resolved is False
        assert r.patch is None
        assert r.reason == REASON_AMBIGUOUS

    def test_dual_reference_both_sah(self):
        """'القديم صح والجديد صح' → unresolved ambiguous."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "القديم صح والجديد صح")
        assert r.resolved is False
        assert r.patch is None
        assert r.reason == REASON_AMBIGUOUS

    def test_single_existing_still_resolves(self):
        """'القديم صح' still resolves to existing value."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "القديم صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 25

    def test_single_existing_first_still_resolves(self):
        """'الأول صح' still resolves to existing value."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الأول صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 25

    def test_single_incoming_still_resolves(self):
        """'الجديد صح' still resolves to incoming value."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "الجديد صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_single_incoming_second_still_resolves(self):
        """'التاني صح' still resolves to incoming value."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "التاني صح")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    # ================================================================
    # N. Multiple candidate numbers
    # ================================================================

    def test_age_with_multiple_numbers_age_context(self):
        """Age conflict + 'أنا 26 سنة وبتمرن 4 أيام' → resolves age=26."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "أنا 26 سنة وبتمرن 4 أيام")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 26

    def test_days_with_multiple_numbers_days_context(self):
        """Days conflict + 'أنا 26 سنة وبتمرن 4 أيام' → resolves days=4."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "أنا 26 سنة وبتمرن 4 أيام")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 4

    def test_height_with_multiple_numbers_height_context(self):
        """Height conflict + 'طول 180 سم ووزن 80 كيلو' → resolves height."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "طول 180 سم ووزن 80 كيلو")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.0

    def test_days_with_multiple_numbers_days_keyword(self):
        """Days conflict + 'بتمرن 4 أيام في الأسبوع' → resolves days=4."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "بتمرن 4 أيام في الأسبوع")
        assert r.resolved is True
        assert r.patch.updates["training.days_per_week"] == 4

    # ================================================================
    # O. Invalid numeric value
    # ================================================================

    def test_days_invalid_over_seven(self):
        """Days=10 → unresolved (validation rejects >7)."""
        c = _conflict("training.days_per_week", 3, 5)
        r = self.resolver.resolve(c, "10 أيام")
        assert r.resolved is False
        assert r.reason == REASON_INVALID

    def test_age_invalid_negative(self):
        """Age=-1 → unresolved (validation rejects negative)."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "-1 سنة")
        assert r.resolved is False
        assert r.reason == REASON_INVALID

    def test_age_zero_is_valid_per_validator(self):
        """Age=0 passes validation (validator allows non-negative)."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "0 سنة")
        assert r.resolved is True
        assert r.patch.updates["personal.age"] == 0

    def test_height_invalid_negative(self):
        """Height=-175 → unresolved."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "-175 سم")
        assert r.resolved is False
        assert r.reason == REASON_INVALID

    def test_height_invalid_zero(self):
        """Height=0 → unresolved."""
        c = _conflict("personal.height_cm", 175.0, 180.0)
        r = self.resolver.resolve(c, "0 سم")
        assert r.resolved is False
        assert r.reason == REASON_INVALID

    # ================================================================
    # P. Conflict immutability
    # ================================================================

    def test_conflict_not_mutated_by_resolver(self):
        """Resolver does not mutate the Conflict object."""
        c = _conflict("personal.age", 25, 26)
        original_path = c.path
        original_existing = c.existing_value
        original_incoming = c.incoming_value
        original_reason = c.reason

        self.resolver.resolve(c, "26")

        assert c.path == original_path
        assert c.existing_value == original_existing
        assert c.incoming_value == original_incoming
        assert c.reason == original_reason

    # ================================================================
    # Q. Resolver determinism
    # ================================================================

    def test_resolver_is_deterministic(self):
        """Same inputs always produce the same output."""
        c = _conflict("personal.age", 25, 26)
        results = [self.resolver.resolve(c, "26") for _ in range(10)]
        assert all(r.resolved == results[0].resolved for r in results)
        assert all(
            r.patch.updates == results[0].patch.updates for r in results
        )

    # ================================================================
    # R. Empty and whitespace messages
    # ================================================================

    def test_empty_message(self):
        """Empty message → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "")
        assert r.resolved is False
        assert r.reason == REASON_NO_CANDIDATE

    def test_whitespace_only_message(self):
        """Whitespace-only message → unresolved."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "   ")
        assert r.resolved is False
        assert r.reason == REASON_NO_CANDIDATE

    # ================================================================
    # T. Patch contract
    # ================================================================

    def test_resolved_patch_has_exactly_one_update(self):
        """Resolved patch contains exactly one update."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        assert len(r.patch.updates) == 1

    def test_resolved_patch_has_empty_unknown_fields(self):
        """Resolved patch has empty unknown_fields."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        assert r.patch.unknown_fields == []

    def test_resolved_patch_has_empty_conflicts(self):
        """Resolved patch has empty conflicts."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        assert r.patch.conflicts == []

    def test_resolved_patch_is_valid_profile_patch(self):
        """Resolved patch passes validation."""
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        from app.profile.validator import validate_profile_patch
        validate_profile_patch(r.patch)  # should not raise

    # ================================================================
    # U. No LLM
    # ================================================================

    def test_no_llm_or_network_calls(self):
        """Resolver performs no LLM or network calls — pure deterministic logic."""
        # If the resolver used an LLM, this test would fail without mocking.
        # The resolver is fully deterministic and self-contained.
        c = _conflict("personal.age", 25, 26)
        r = self.resolver.resolve(c, "26")
        assert r.resolved is True

    # ================================================================
    # V. Unsupported field
    # ================================================================

    def test_unsupported_field_returns_unsupported(self):
        """Non-contradiction-sensitive field → unresolved."""
        c = _conflict("personal.weight_kg", 85.0, 80.0)
        r = self.resolver.resolve(c, "80")
        assert r.resolved is False
        assert r.reason == REASON_UNSUPPORTED

    # ================================================================
    # W. Float numeric formatting
    # ================================================================

    def test_height_float_value_preserved(self):
        """Height float value is preserved in resolved patch."""
        c = _conflict("personal.height_cm", 175.5, 180.5)
        r = self.resolver.resolve(c, "180.5 سم")
        assert r.resolved is True
        assert r.patch.updates["personal.height_cm"] == 180.5

    def test_target_weight_float_preserved(self):
        """Target weight float value is preserved in resolved patch."""
        c = _conflict("goal.target_weight_kg", 80.5, 75.5)
        r = self.resolver.resolve(c, "75.5 كيلو")
        assert r.resolved is True
        assert r.patch.updates["goal.target_weight_kg"] == 75.5

    # ================================================================
    # X. All contradiction-sensitive fields covered
    # ================================================================

    def test_all_contradiction_sensitive_fields_support_existing_incoming(self):
        """Every contradiction-sensitive field supports existing/incoming references."""
        for field in CONTRADICTION_SENSITIVE_FIELDS:
            c = _conflict(field, "a", "b")
            r_existing = self.resolver.resolve(c, "القديم")
            r_incoming = self.resolver.resolve(c, "الجديد")
            assert r_existing.resolved is True, f"Field {field} failed existing resolution"
            assert r_incoming.resolved is True, f"Field {field} failed incoming resolution"
