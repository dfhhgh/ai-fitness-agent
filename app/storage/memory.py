"""In-memory conversation store for MVP state persistence.

Stores profiles and pending conflicts by client_id.
No database, no network, no Telegram imports.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.profile.conflicts import Conflict
from app.profile.models import ClientProfile


class ConversationStore(ABC):
    """Abstract interface for conversation state persistence."""

    @abstractmethod
    def get_profile(self, client_id: str) -> Optional[ClientProfile]:
        """Return the profile for client_id, or None if not found."""

    @abstractmethod
    def save_profile(self, client_id: str, profile: ClientProfile) -> None:
        """Save or replace the profile for client_id."""

    @abstractmethod
    def get_pending_conflicts(self, client_id: str) -> Optional[List[Conflict]]:
        """Return pending conflicts for client_id, or None if none exist."""

    @abstractmethod
    def save_pending_conflicts(self, client_id: str, conflicts: List[Conflict]) -> None:
        """Save pending conflicts for client_id."""

    @abstractmethod
    def clear_pending_conflicts(self, client_id: str) -> None:
        """Clear pending conflicts for client_id. Idempotent."""


class InMemoryConversationStore(ConversationStore):
    """In-memory dictionary-backed conversation store.

    State is lost on process restart. Single-process only.
    Sufficient for MVP and testing.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ClientProfile] = {}
        self._conflicts: dict[str, list[Conflict]] = {}

    def get_profile(self, client_id: str) -> Optional[ClientProfile]:
        """Return the profile for client_id, or None if not found."""
        return self._profiles.get(client_id)

    def save_profile(self, client_id: str, profile: ClientProfile) -> None:
        """Save or replace the profile for client_id."""
        self._profiles[client_id] = profile

    def get_pending_conflicts(self, client_id: str) -> Optional[List[Conflict]]:
        """Return pending conflicts for client_id, or None if none exist."""
        conflicts = self._conflicts.get(client_id)
        if conflicts is None:
            return None
        return list(conflicts)

    def save_pending_conflicts(self, client_id: str, conflicts: List[Conflict]) -> None:
        """Save pending conflicts for client_id."""
        self._conflicts[client_id] = list(conflicts)

    def clear_pending_conflicts(self, client_id: str) -> None:
        """Clear pending conflicts for client_id. Idempotent."""
        self._conflicts.pop(client_id, None)
