"""In-memory session store — T013.

Per FR-015: all state is ephemeral, lost on process exit.
Per data-model.md: three dicts for sessions, copilot sessions, and idempotency records.
"""

from __future__ import annotations

from typing import Any

from server.models import IdempotencyRecord, ReviewSession


class SessionStore:
    """In-memory session storage for MVP."""

    def __init__(self) -> None:
        self._sessions: dict[str, ReviewSession] = {}
        self._copilot_sessions: dict[str, Any] = {}
        self._idempotency_records: dict[str, IdempotencyRecord] = {}

    def save(self, session: ReviewSession) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> ReviewSession | None:
        return self._sessions.get(session_id)

    def list_all(self) -> list[ReviewSession]:
        return list(self._sessions.values())

    def set_copilot_session(self, key: str, copilot_session: Any) -> None:
        self._copilot_sessions[key] = copilot_session

    def get_copilot_session(self, key: str) -> Any | None:
        return self._copilot_sessions.get(key)

    def save_idempotency_record(self, record: IdempotencyRecord) -> None:
        self._idempotency_records[record.key] = record

    def get_idempotency_record(self, key: str) -> IdempotencyRecord | None:
        return self._idempotency_records.get(key)

    def token_exists_elsewhere(self, token: str, expected_key: str) -> bool:
        """Check if token is already used under a different composite key."""
        for key, record in self._idempotency_records.items():
            if record.token == token and key != expected_key:
                return True
        return False
