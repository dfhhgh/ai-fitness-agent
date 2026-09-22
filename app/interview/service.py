"""Application service bridging transport adapters to the Interview Core.

Orchestrates both normal interview flow and clarification flow.
Transport-agnostic: no Telegram, no HTTP, no database imports.
"""

from typing import Optional

from app.interview.clarification_generator import ClarificationGenerator
from app.interview.clarification_resolver import ClarificationResolver
from app.interview.controller import InterviewController
from app.interview.question_generator import QuestionGenerator
from app.profile.conflicts import Conflict
from app.profile.merger import merge_profile
from app.profile.models import ClientProfile
from app.profile.state_machine import InterviewState, get_interview_status
from app.profile.validator import validate_profile_patch
from app.storage.memory import ConversationStore


class InterviewService:
    """Application service handling the full interview lifecycle.

    Dependencies are injected. No LLM, no Telegram, no network.
    """

    def __init__(
        self,
        controller: InterviewController,
        store: ConversationStore,
        clarification_resolver: Optional[ClarificationResolver] = None,
    ) -> None:
        self._controller = controller
        self._store = store
        self._resolver = clarification_resolver or ClarificationResolver()
        self._question_generator = QuestionGenerator()
        self._clarification_generator = ClarificationGenerator()

    def handle_message(self, chat_id: int, text: str) -> str:
        """Process one user message and return a response string.

        Routes to normal flow or clarification flow based on pending state.
        """
        client_id = str(chat_id)
        profile = self._store.get_profile(client_id)

        if profile is None:
            profile = ClientProfile(client_id=client_id)
            self._store.save_profile(client_id, profile)

        pending = self._store.get_pending_conflicts(client_id)

        if pending:
            return self._handle_clarification(client_id, profile, text, pending)

        return self._handle_normal(client_id, profile, text)

    def _handle_normal(
        self,
        client_id: str,
        profile: ClientProfile,
        text: str,
    ) -> str:
        """Handle a normal interview turn (no pending clarification)."""
        result = self._controller.process_message(profile, text)

        if result.state == InterviewState.WAITING_FOR_CLARIFICATION:
            self._store.save_profile(client_id, result.profile)
            self._store.save_pending_conflicts(client_id, result.conflicts)
            first_conflict = result.conflicts[0]
            return self._clarification_generator.generate(first_conflict)

        if result.merged:
            self._store.save_profile(client_id, result.profile)
            self._store.clear_pending_conflicts(client_id)

        if result.state == InterviewState.INTERVIEWING and result.next_field:
            return self._question_generator.generate(result.next_field)

        if result.state == InterviewState.READY_FOR_PLAN:
            return "تمام 👌 كده بياناتك الأساسية اكتملت."

        return self._question_generator.generate(result.next_field)

    def _handle_clarification(
        self,
        client_id: str,
        profile: ClientProfile,
        text: str,
        pending: list[Conflict],
    ) -> str:
        """Handle a clarification turn (pending conflict exists)."""
        conflict = pending[0]
        resolution = self._resolver.resolve(conflict, text)

        if not resolution.resolved:
            return self._clarification_generator.generate(conflict)

        validate_profile_patch(resolution.patch)
        merged_profile = merge_profile(profile, resolution.patch)

        self._store.save_profile(client_id, merged_profile)
        self._store.clear_pending_conflicts(client_id)

        remaining = pending[1:]
        if remaining:
            self._store.save_pending_conflicts(client_id, remaining)
            return self._clarification_generator.generate(remaining[0])

        status = get_interview_status(merged_profile)

        if status.state == InterviewState.INTERVIEWING and status.next_field:
            return self._question_generator.generate(status.next_field)

        if status.state == InterviewState.READY_FOR_PLAN:
            return "تمام 👌 كده بياناتك الأساسية اكتملت."

        return "تمام 👌 كده بياناتك الأساسية اكتملت."
