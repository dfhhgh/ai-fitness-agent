"""End-to-end interview flow tests — simulating complete onboarding conversations.

Uses a deterministic ConversationExtractor (no real LLM) and the REAL
QuestionGenerator to verify that the full pipeline works together:

    User message
      -> FakeExtractor -> ProfilePatch
      -> InterviewController.process_message
      -> State Machine determines next_field
      -> QuestionGenerator generates correct Egyptian Arabic question

No network calls, no LLM, no Telegram, no n8n.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from app.interview.controller import InterviewController
from app.interview.models import InterviewTurnResult
from app.interview.question_generator import QuestionGenerator
from app.profile.missing_fields import get_missing_fields
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState


# ---------------------------------------------------------------------------
# Deterministic fake extractor
# ---------------------------------------------------------------------------


class ConversationExtractor:
    """Maps user messages to predetermined ProfilePatch objects.

    Tests control exactly what the extractor returns for each message.
    No keyword parsing, no regex, no fake LLM.
    """

    def __init__(self, patches: Dict[str, ProfilePatch]) -> None:
        self._patches = patches

    def extract(self, user_message: str) -> ProfilePatch:
        return self._patches[user_message]


def _empty_patch() -> ProfilePatch:
    return ProfilePatch(updates={}, unknown_fields=[], conflicts=[])


def _patch(**updates: Any) -> ProfilePatch:
    return ProfilePatch(updates=updates, unknown_fields=[], conflicts=[])


def _patch_with_unknown(
    updates: Dict[str, Any], unknown_fields: List[str]
) -> ProfilePatch:
    return ProfilePatch(updates=updates, unknown_fields=unknown_fields, conflicts=[])


# ---------------------------------------------------------------------------
# Question semantic markers for field verification
# ---------------------------------------------------------------------------

FIELD_QUESTION_MARKERS: Dict[str, List[str]] = {
    "personal.gender": ["راجل", "ست"],
    "personal.age": ["سنة"],
    "personal.height_cm": ["طول", "سم"],
    "personal.weight_kg": ["وزن", "كيلو"],
    "health.injuries": ["إصابات", "إصابة"],
    "training.experience": ["تمرن", "الجيم"],
    "training.days_per_week": ["أسبوع"],
    "training.duration": ["ملتزم", "بقالك"],
    "training.activity_description": ["نشاط"],
    "goal.type": ["هدف"],
}


def _assert_question_targets_field(field: str, question: str) -> None:
    """Assert that the generated question corresponds to the expected field."""
    markers = FIELD_QUESTION_MARKERS[field]
    assert any(
        marker in question for marker in markers
    ), f"Question for {field!r} does not contain any of {markers!r}: {question!r}"


# ---------------------------------------------------------------------------
# Test class: Happy-path interview
# ---------------------------------------------------------------------------


class TestHappyPathInterview:
    """Complete onboarding flow from empty profile to READY_FOR_PLAN."""

    def test_complete_onboarding_flow(self) -> None:
        """Full 8-turn onboarding conversation reaches READY_FOR_PLAN.

        Verifies:
        - Each turn merges correctly
        - State Machine determines next_field correctly
        - QuestionGenerator generates the right question for each next_field
        - Original profile is never mutated
        - Final profile contains exactly the expected values
        """
        # --- Turn definitions ---
        turns: List[Dict[str, Any]] = [
            {
                "user_message": "أنا 25 سنة وراجل",
                "patch": _patch(**{"personal.age": 25, "personal.gender": "رجل"}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "personal.height_cm",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "طولي 175 سم ووزني 85 كيلو",
                "patch": _patch(
                    **{"personal.height_cm": 175.0, "personal.weight_kg": 85.0}
                ),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "health.injuries",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "مفيش عندي أي إصابات",
                "patch": _patch(**{"health.injuries": []}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "training.experience",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "أنا مبتدئ",
                "patch": _patch(**{"training.experience": "beginner"}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "training.days_per_week",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "بتمرن 4 أيام في الأسبوع",
                "patch": _patch(**{"training.days_per_week": 4}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "training.duration",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "بقالي شهرين بتمرن بشكل منتظم",
                "patch": _patch(**{"training.duration": "2 months"}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "training.activity_description",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "شغلي مكتبي ومش بتحرك كتير",
                "patch": _patch(**{"training.activity_description": "مكتبي"}),
                "expected_state": InterviewState.INTERVIEWING,
                "expected_next_field": "goal.type",
                "expected_merged": True,
                "expected_conflicts": [],
            },
            {
                "user_message": "عايز أخس",
                "patch": _patch(**{"goal.type": "weight_loss"}),
                "expected_state": InterviewState.READY_FOR_PLAN,
                "expected_next_field": None,
                "expected_merged": True,
                "expected_conflicts": [],
            },
        ]

        # Build extractor mapping
        patches_map = {t["user_message"]: t["patch"] for t in turns}
        extractor = ConversationExtractor(patches_map)
        controller = InterviewController(extractor)
        question_gen = QuestionGenerator()

        # Start with empty profile
        current_profile = ClientProfile()

        for i, turn in enumerate(turns, start=1):
            user_message = turn["user_message"]
            expected_state = turn["expected_state"]
            expected_next_field = turn["expected_next_field"]
            expected_merged = turn["expected_merged"]
            expected_conflicts = turn["expected_conflicts"]

            # --- Immutability check ---
            before_dump = current_profile.model_dump()

            result = controller.process_message(current_profile, user_message)

            # Original profile must not be mutated
            assert current_profile.model_dump() == before_dump, (
                f"Turn {i}: Original profile was mutated"
            )

            # --- Core assertions ---
            assert isinstance(result, InterviewTurnResult), (
                f"Turn {i}: Result is not InterviewTurnResult"
            )
            assert result.merged is expected_merged, (
                f"Turn {i}: merged={result.merged}, expected={expected_merged}"
            )
            assert result.state == expected_state, (
                f"Turn {i}: state={result.state}, expected={expected_state}"
            )
            assert result.next_field == expected_next_field, (
                f"Turn {i}: next_field={result.next_field}, expected={expected_next_field}"
            )
            assert result.conflicts == expected_conflicts, (
                f"Turn {i}: conflicts={result.conflicts}, expected={expected_conflicts}"
            )

            # --- missing_fields consistency ---
            assert result.missing_fields == get_missing_fields(result.profile), (
                f"Turn {i}: missing_fields does not match get_missing_fields(profile)"
            )

            # --- Question generation for INTERVIEWING turns ---
            if expected_state == InterviewState.INTERVIEWING:
                assert result.next_field is not None, (
                    f"Turn {i}: INTERVIEWING but next_field is None"
                )
                assert result.next_field == result.missing_fields[0], (
                    f"Turn {i}: next_field != first missing field"
                )
                question = question_gen.generate(result.next_field)
                _assert_question_targets_field(result.next_field, question)

            # Carry forward the returned profile for the next turn
            current_profile = result.profile

        # --- Final profile assertions ---
        final = current_profile
        assert final.personal.age == 25
        assert final.personal.gender == "رجل"
        assert final.personal.height_cm == 175.0
        assert final.personal.weight_kg == 85.0
        assert final.health.injuries == []
        assert final.training.experience == "beginner"
        assert final.training.days_per_week == 4
        assert final.training.duration == "2 months"
        assert final.training.activity_description == "مكتبي"
        assert final.goal.type == "weight_loss"

        # Optional fields must not be set
        assert final.goal.target_weight_kg is None
        assert final.goal.weight_change_target_kg is None
        assert final.nutrition.food_preferences == []
        assert final.nutrition.disliked_foods == []
        assert final.nutrition.disliked_activities == []
        assert final.inbody.weight_kg is None


# ---------------------------------------------------------------------------
# Test class: Interview edge cases
# ---------------------------------------------------------------------------


class TestInterviewEdgeCases:
    """Edge-case scenarios: conflicts, empty messages, atomicity, etc."""

    def test_conflict_stops_flow(self) -> None:
        """Conflict prevents merge and returns WAITING_FOR_CLARIFICATION.

        Profile has age=25, user says age=26 + height=180.
        Both fields are in the patch, but age conflicts.
        NOTHING should merge (atomicity).
        """
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل"},
        )

        # Patch: age=26 (conflict) + height=180 (no conflict)
        patch = _patch(**{"personal.age": 26, "personal.height_cm": 180.0})
        extractor = ConversationExtractor(
            {"لا أنا 26 سنة وطولي 180": patch}
        )
        controller = InterviewController(extractor)

        before_dump = profile.model_dump()
        result = controller.process_message(profile, "لا أنا 26 سنة وطولي 180")

        assert result.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert result.merged is False
        assert result.next_field is None
        assert len(result.conflicts) == 1
        assert result.conflicts[0].path == "personal.age"
        assert result.conflicts[0].existing_value == 25
        assert result.conflicts[0].incoming_value == 26

        # Profile must remain unchanged (atomicity)
        assert result.profile.model_dump() == before_dump
        assert profile.model_dump() == before_dump

        # Height must NOT have been merged
        assert result.profile.personal.height_cm is None

    def test_empty_patch(self) -> None:
        """Empty patch does not merge, does not invent data.

        Profile has age=25. Empty patch arrives. Profile unchanged.
        State is INTERVIEWING (gender still missing).
        """
        profile = ClientProfile(personal={"age": 25})
        extractor = ConversationExtractor({"تمام": _empty_patch()})
        controller = InterviewController(extractor)
        question_gen = QuestionGenerator()

        before_dump = profile.model_dump()
        result = controller.process_message(profile, "تمام")

        assert result.merged is False
        assert result.profile.model_dump() == before_dump
        assert result.state == InterviewState.INTERVIEWING
        assert result.next_field == "personal.gender"

        # Question should target gender
        question = question_gen.generate(result.next_field)
        _assert_question_targets_field("personal.gender", question)

    def test_unknown_only_patch(self) -> None:
        """Unknown-only patch does not merge, does not cause conflict.

        Extractor returns updates={} with unknown_fields=["personal.weight_kg"].
        Profile should remain unchanged. State determined from current profile.
        """
        profile = ClientProfile(personal={"age": 25, "gender": "رجل"})
        patch = _patch_with_unknown({}, ["personal.weight_kg"])
        extractor = ConversationExtractor({"مش عارف وزني": patch})
        controller = InterviewController(extractor)

        before_dump = profile.model_dump()
        result = controller.process_message(profile, "مش عارف وزني")

        assert result.merged is False
        assert result.profile.model_dump() == before_dump
        assert result.conflicts == []
        # Next missing field is height_cm (gender and age already set)
        assert result.state == InterviewState.INTERVIEWING
        assert result.next_field == "personal.height_cm"

    def test_atomicity_conflict_prevents_partial_merge(self) -> None:
        """Patch with conflict + non-conflicting field: nothing merges.

        Profile: age=25, gender=رجل, height=None, weight=85
        Patch: age=26 (conflict), height=180 (no conflict)
        Result: age stays 25, height stays None.
        """
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "weight_kg": 85.0},
        )
        patch = _patch(**{"personal.age": 26, "personal.height_cm": 180.0})
        extractor = ConversationExtractor({"test": patch})
        controller = InterviewController(extractor)

        before_dump = profile.model_dump()
        result = controller.process_message(profile, "test")

        assert result.state == InterviewState.WAITING_FOR_CLARIFICATION
        assert result.merged is False
        assert len(result.conflicts) == 1

        # Both fields must remain unchanged
        assert result.profile.personal.age == 25
        assert result.profile.personal.height_cm is None
        assert result.profile.model_dump() == before_dump

    def test_experience_and_duration_are_separate(self) -> None:
        """training.experience and training.duration remain separate fields.

        After setting experience, duration must still be None.
        After setting duration, experience must still be its previous value.
        """
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            health={"injuries": []},
        )
        extractor = ConversationExtractor(
            {
                "أنا مبتدئ": _patch(**{"training.experience": "beginner"}),
                "بقالي شهرين": _patch(**{"training.duration": "2 months"}),
            }
        )
        controller = InterviewController(extractor)

        # Turn 1: set experience
        result1 = controller.process_message(profile, "أنا مبتدئ")
        assert result1.merged is True
        assert result1.profile.training.experience == "beginner"
        assert result1.profile.training.duration is None
        assert result1.next_field == "training.days_per_week"

        # Turn 2: set duration (on the updated profile)
        result2 = controller.process_message(result1.profile, "بقالي شهرين")
        assert result2.merged is True
        assert result2.profile.training.duration == "2 months"
        assert result2.profile.training.experience == "beginner"

    def test_mutable_weight_update(self) -> None:
        """personal.weight_kg is mutable: updating it does not cause a conflict.

        Profile has weight=85. Patch has weight=82. No conflict, merges cleanly.
        """
        profile = ClientProfile(
            personal={"age": 25, "gender": "رجل", "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "beginner",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        patch = _patch(**{"personal.weight_kg": 82.0})
        extractor = ConversationExtractor({"وزني 82 كيلو": patch})
        controller = InterviewController(extractor)

        result = controller.process_message(profile, "وزني 82 كيلو")

        assert result.merged is True
        assert result.conflicts == []
        assert result.profile.personal.weight_kg == 82.0
        # Profile should now be complete -> READY_FOR_PLAN
        assert result.state == InterviewState.READY_FOR_PLAN
        assert result.next_field is None

    def test_question_generator_integration(self) -> None:
        """Verify question flow: each next_field maps to the correct question.

        Uses the real QuestionGenerator and checks semantic markers.
        """
        # Build a profile with only gender and age set
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25},
        )
        # Empty patch -> no merge
        extractor = ConversationExtractor({"مرحبا": _empty_patch()})
        controller = InterviewController(extractor)
        question_gen = QuestionGenerator()

        result = controller.process_message(profile, "مرحبا")

        assert result.state == InterviewState.INTERVIEWING
        assert result.next_field is not None

        question = question_gen.generate(result.next_field)
        _assert_question_targets_field(result.next_field, question)

        # Verify the next field is height_cm (gender and age are set)
        assert result.next_field == "personal.height_cm"

        # Verify all missing fields are accounted for
        expected_missing = get_missing_fields(result.profile)
        assert result.missing_fields == expected_missing

    def test_final_turn_no_question_needed(self) -> None:
        """On READY_FOR_PLAN, next_field is None and no question is generated."""
        # Complete profile
        profile = ClientProfile(
            personal={"gender": "رجل", "age": 25, "height_cm": 175.0, "weight_kg": 85.0},
            goal={"type": "weight_loss"},
            training={
                "days_per_week": 4,
                "duration": "2 months",
                "experience": "beginner",
                "activity_description": "مكتبي",
            },
            health={"injuries": []},
        )
        # Mutable weight update on complete profile
        patch = _patch(**{"personal.weight_kg": 82.0})
        extractor = ConversationExtractor({"وزني 82": patch})
        controller = InterviewController(extractor)

        result = controller.process_message(profile, "وزني 82")

        assert result.state == InterviewState.READY_FOR_PLAN
        assert result.next_field is None
        assert result.missing_fields == []
        assert result.merged is True
