"""Tests for app.interview.service and app.storage.memory -- application service layer."""

import pytest

from app.interview.clarification_resolver import ClarificationResolver
from app.interview.controller import InterviewController
from app.interview.models import InterviewTurnResult
from app.interview.service import InterviewService
from app.profile.conflicts import Conflict
from app.profile.models import ClientProfile, ProfilePatch
from app.profile.state_machine import InterviewState
from app.storage.memory import InMemoryConversationStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeExtractor:
    """Fake LLM extractor returning a predefined ProfilePatch."""

    def __init__(self, patch: ProfilePatch) -> None:
        self._patch = patch
        self.calls: list[str] = []

    def extract(self, user_message: str) -> ProfilePatch:
        self.calls.append(user_message)
        return self._patch


def _make_empty_profile(client_id: str = "100") -> ClientProfile:
    return ClientProfile(client_id=client_id)


def _make_full_profile(client_id: str = "100") -> ClientProfile:
    return ClientProfile(
        client_id=client_id,
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


def _make_conflict(
    path: str = "personal.age",
    existing: object = 25,
    incoming: object = 26,
) -> Conflict:
    return Conflict(
        path=path,
        existing_value=existing,
        incoming_value=incoming,
        reason="existing_value_conflicts_with_incoming_value",
    )


# ===========================================================================
# A. Store Tests
# ===========================================================================

class TestInMemoryConversationStore:
    """InMemoryConversationStore behavior."""

    def setup_method(self):
        self.store = InMemoryConversationStore()

    def test_save_and_get_profile(self):
        """Save a profile and retrieve it."""
        profile = _make_empty_profile("100")
        self.store.save_profile("100", profile)
        result = self.store.get_profile("100")
        assert result is not None
        assert result.client_id == "100"

    def test_missing_profile_returns_none(self):
        """get_profile returns None for unknown client_id."""
        assert self.store.get_profile("unknown") is None

    def test_save_and_get_pending_conflicts(self):
        """Save conflicts and retrieve them."""
        conflicts = [_make_conflict()]
        self.store.save_pending_conflicts("100", conflicts)
        result = self.store.get_pending_conflicts("100")
        assert result is not None
        assert len(result) == 1
        assert result[0].path == "personal.age"

    def test_missing_conflicts_returns_none(self):
        """get_pending_conflicts returns None when none exist."""
        assert self.store.get_pending_conflicts("100") is None

    def test_clear_conflicts(self):
        """clear_pending_conflicts removes stored conflicts."""
        self.store.save_pending_conflicts("100", [_make_conflict()])
        self.store.clear_pending_conflicts("100")
        assert self.store.get_pending_conflicts("100") is None

    def test_clear_conflicts_is_idempotent(self):
        """Clearing already-cleared conflicts does not raise."""
        self.store.clear_pending_conflicts("100")
        self.store.clear_pending_conflicts("100")

    def test_different_client_ids_are_isolated(self):
        """Profiles for different client_ids do not interfere."""
        p1 = _make_empty_profile("100")
        p2 = _make_empty_profile("200")
        self.store.save_profile("100", p1)
        self.store.save_profile("200", p2)
        assert self.store.get_profile("100").client_id == "100"
        assert self.store.get_profile("200").client_id == "200"

    def test_get_pending_conflicts_returns_copy(self):
        """get_pending_conflicts returns a copy, not the internal list."""
        conflicts = [_make_conflict()]
        self.store.save_pending_conflicts("100", conflicts)
        result1 = self.store.get_pending_conflicts("100")
        result2 = self.store.get_pending_conflicts("100")
        assert result1 == result2
        assert result1 is not result2


# ===========================================================================
# B. New Conversation
# ===========================================================================

class TestNewConversation:
    """First message creates a profile."""

    def test_first_message_creates_profile(self):
        """First handle_message creates a new profile in the store."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "أنا 25 سنة")

        profile = store.get_profile("100")
        assert profile is not None
        assert profile.client_id == "100"

    def test_client_id_is_str_of_chat_id(self):
        """client_id is str(chat_id)."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(123456789, "مرحبا")

        profile = store.get_profile("123456789")
        assert profile is not None
        assert profile.client_id == "123456789"

    def test_profile_persists_for_next_message(self):
        """Profile saved by first message is available for second message."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "أنا 25 سنة")
        service.handle_message(100, "بتمرن 4 أيام")

        profile = store.get_profile("100")
        assert profile is not None


# ===========================================================================
# C. Normal Flow
# ===========================================================================

class TestNormalFlow:
    """Normal interview flow without pending conflicts."""

    def test_normal_message_calls_controller(self):
        """Normal message goes through InterviewController."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "أنا 25 سنة")

        assert len(extractor.calls) == 1
        assert extractor.calls[0] == "أنا 25 سنة"

    def test_successful_merge_saves_profile(self):
        """When controller merges, the updated profile is saved."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "أنا 25 سنة")

        profile = store.get_profile("100")
        assert profile.personal.age == 25

    def test_interviewing_returns_question(self):
        """INTERVIEWING state returns the next question from QuestionGenerator."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(
            updates={"personal.age": 25},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "أنا 25 سنة")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_ready_for_plan_returns_completion(self):
        """READY_FOR_PLAN returns a completion message."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "شكرا")

        assert "اكتملت" in response

    def test_waiting_for_clarification_saves_conflict(self):
        """WAITING_FOR_CLARIFICATION saves pending conflict."""
        store = InMemoryConversationStore()
        existing_profile = _make_full_profile("100")
        store.save_profile("100", existing_profile)

        fake_patch = ProfilePatch(
            updates={"personal.age": 26},
            unknown_fields=[],
            conflicts=[],
        )
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "أنا 26 سنة")

        pending = store.get_pending_conflicts("100")
        assert pending is not None
        assert len(pending) == 1
        assert pending[0].path == "personal.age"
        assert isinstance(response, str)
        assert "؟" in response


# ===========================================================================
# D. Clarification Flow
# ===========================================================================

class TestClarificationFlow:
    """Clarification flow when pending conflicts exist."""

    def test_pending_conflict_routes_to_resolver(self):
        """Pending conflict routes user answer to ClarificationResolver."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "الجديد هو الصح")

        profile = store.get_profile("100")
        assert profile.personal.age == 26
        assert store.get_pending_conflicts("100") is None

    def test_resolved_clarification_validates_patch(self):
        """Resolved clarification produces a valid patch before merge."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "الجديد هو الصح")

        profile = store.get_profile("100")
        assert profile.personal.age == 26

    def test_resolved_clarification_merges_profile(self):
        """Resolved clarification merges the resolved value into the profile."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "القديم هو الصح")

        profile = store.get_profile("100")
        assert profile.personal.age == 25

    def test_resolved_conflict_is_cleared(self):
        """After resolution, pending conflict is cleared."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "الجديد هو الصح")

        assert store.get_pending_conflicts("100") is None

    def test_next_question_after_resolution(self):
        """After resolving a conflict, next question is generated if fields remain."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "الجديد هو الصح")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_ready_for_plan_after_clarification(self):
        """READY_FOR_PLAN after clarification returns completion message."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "الجديد هو الصح")

        assert "اكتملت" in response

    def test_unresolved_keeps_profile_unchanged(self):
        """Unresolved clarification keeps profile unchanged."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "مش عارف")

        profile = store.get_profile("100")
        assert profile.personal.age == 25

    def test_unresolved_keeps_pending_conflict(self):
        """Unresolved clarification keeps the pending conflict."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "مش عارف")

        pending = store.get_pending_conflicts("100")
        assert pending is not None
        assert len(pending) == 1

    def test_unresolved_re_asks_question(self):
        """Unresolved clarification re-sends the clarification question."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "مش عارف")

        assert isinstance(response, str)
        assert "؟" in response

    def test_controller_not_called_during_clarification(self):
        """During clarification, controller.process_message is NOT called."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "الجديد هو الصح")

        assert len(extractor.calls) == 0


# ===========================================================================
# E. Atomicity
# ===========================================================================

class TestAtomicity:
    """Atomicity guarantees for clarification and normal flow."""

    def test_failed_resolution_no_profile_mutation(self):
        """Unresolved clarification does not mutate the profile."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "مش عارف")

        profile = store.get_profile("100")
        assert profile.personal.age == 25
        assert profile.personal.gender == "رجل"
        assert profile.personal.height_cm == 175.0

    def test_multiple_conflicts_first_handled_first(self):
        """First conflict is handled first; remaining stay pending."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)

        c1 = _make_conflict("personal.age", 25, 26)
        c2 = _make_conflict("personal.height_cm", 175.0, 180.0)
        store.save_pending_conflicts("100", [c1, c2])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "الجديد هو الصح")

        profile = store.get_profile("100")
        assert profile.personal.age == 26
        assert profile.personal.height_cm == 175.0

        remaining = store.get_pending_conflicts("100")
        assert remaining is not None
        assert len(remaining) == 1
        assert remaining[0].path == "personal.height_cm"

    def test_resolving_one_conflict_does_not_modify_unrelated_fields(self):
        """Resolving age conflict does not change height or gender."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        service.handle_message(100, "الجديد هو الصح")

        profile = store.get_profile("100")
        assert profile.personal.gender == "رجل"
        assert profile.personal.height_cm == 175.0
        assert profile.personal.weight_kg == 85.0


# ===========================================================================
# F. Isolation
# ===========================================================================

class TestIsolation:
    """Different chat_ids have independent state."""

    def test_two_chat_ids_independent_profiles(self):
        """Two chat_ids have independent profiles."""
        store = InMemoryConversationStore()

        patches = [
            ProfilePatch(updates={"personal.age": 25}, unknown_fields=[], conflicts=[]),
            ProfilePatch(updates={"personal.age": 30}, unknown_fields=[], conflicts=[]),
        ]
        call_count = [0]

        class SequentialExtractor:
            def extract(self, msg):
                p = patches[call_count[0]]
                call_count[0] += 1
                return p

        controller = InterviewController(SequentialExtractor())
        service = InterviewService(controller, store)

        service.handle_message(100, "أنا 25 سنة")
        service.handle_message(200, "أنا 30 سنة")

        p1 = store.get_profile("100")
        p2 = store.get_profile("200")
        assert p1.personal.age == 25
        assert p2.personal.age == 30

    def test_two_chat_ids_independent_conflicts(self):
        """Two chat_ids have independent pending conflicts."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_profile("200", _make_full_profile("200"))
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        assert store.get_pending_conflicts("100") is not None
        assert store.get_pending_conflicts("200") is None


# ===========================================================================
# G. Edge Cases
# ===========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_message_to_new_user(self):
        """Empty message to a new user still creates profile."""
        store = InMemoryConversationStore()
        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "")

        profile = store.get_profile("100")
        assert profile is not None

    def test_clarification_with_explicit_value(self):
        """Clarification flow supports explicit value answers."""
        store = InMemoryConversationStore()
        full_profile = _make_full_profile("100")
        store.save_profile("100", full_profile)
        store.save_pending_conflicts("100", [_make_conflict()])

        fake_patch = ProfilePatch(updates={}, unknown_fields=[], conflicts=[])
        extractor = FakeExtractor(fake_patch)
        controller = InterviewController(extractor)
        service = InterviewService(controller, store)

        response = service.handle_message(100, "أنا عندي 27 سنة")

        profile = store.get_profile("100")
        assert profile.personal.age == 27

    def test_consecutive_normal_messages(self):
        """Multiple normal messages in sequence work correctly."""
        store = InMemoryConversationStore()

        patches = [
            ProfilePatch(updates={"personal.age": 25}, unknown_fields=[], conflicts=[]),
            ProfilePatch(updates={"personal.gender": "رجل"}, unknown_fields=[], conflicts=[]),
            ProfilePatch(updates={"personal.height_cm": 175.0}, unknown_fields=[], conflicts=[]),
        ]
        call_count = [0]

        class SequentialExtractor:
            def extract(self, msg):
                p = patches[call_count[0]]
                call_count[0] += 1
                return p

        controller = InterviewController(SequentialExtractor())
        service = InterviewService(controller, store)

        service.handle_message(100, "عمري 25 سنة")
        service.handle_message(100, "أنا راجل")
        service.handle_message(100, "طول 175 سم")

        profile = store.get_profile("100")
        assert profile.personal.age == 25
        assert profile.personal.gender == "رجل"
        assert profile.personal.height_cm == 175.0
