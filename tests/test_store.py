"""Tests for session store — T009."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from server.models import (
    FindingStatus,
    IdempotencyRecord,
    ReviewSession,
    SessionStatus,
    TokenUsage,
)
from server.store import SessionStore


@pytest.fixture
def store() -> SessionStore:
    return SessionStore()


@pytest.fixture
def sample_session() -> ReviewSession:
    return ReviewSession(
        session_id="sess-1",
        branch="feature/test",
        status=SessionStatus.ACTIVE,
        model="gpt-4o",
        copilot_session_key="copilot-key-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        messages=[],
        findings=[],
        idempotency_token=None,
        token_usage=TokenUsage(),
    )


class TestSessionCRUD:
    def test_save_and_get(self, store, sample_session):
        store.save(sample_session)
        retrieved = store.get("sess-1")
        assert retrieved is not None
        assert retrieved.session_id == "sess-1"
        assert retrieved.branch == "feature/test"

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent") is None

    def test_list_all_empty(self, store):
        assert store.list_all() == []

    def test_list_all_multiple(self, store, sample_session):
        store.save(sample_session)
        session2 = ReviewSession(
            session_id="sess-2",
            branch="feature/other",
            status=SessionStatus.RESOLVED,
            model="gpt-4o",
            copilot_session_key="copilot-key-2",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            messages=[],
            findings=[],
            idempotency_token=None,
            token_usage=TokenUsage(),
        )
        store.save(session2)
        sessions = store.list_all()
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert ids == {"sess-1", "sess-2"}

    def test_save_overwrites(self, store, sample_session):
        store.save(sample_session)
        sample_session.status = SessionStatus.RESOLVED
        store.save(sample_session)
        retrieved = store.get("sess-1")
        assert retrieved.status == SessionStatus.RESOLVED


class TestCopilotSessionMapping:
    def test_set_and_get_copilot_session(self, store):
        mock_session = object()
        store.set_copilot_session("copilot-key-1", mock_session)
        retrieved = store.get_copilot_session("copilot-key-1")
        assert retrieved is mock_session

    def test_get_missing_copilot_session(self, store):
        assert store.get_copilot_session("nonexistent") is None


class TestIdempotencyRecords:
    def test_save_and_get_record(self, store):
        record = IdempotencyRecord(
            key="start_review::tok-1",
            tool="start_review",
            session_id=None,
            token="tok-1",
            result_snapshot='{"session_id": "sess-1"}',
            created_at=datetime.now(timezone.utc),
        )
        store.save_idempotency_record(record)
        retrieved = store.get_idempotency_record("start_review::tok-1")
        assert retrieved is not None
        assert retrieved.token == "tok-1"
        assert retrieved.result_snapshot == '{"session_id": "sess-1"}'

    def test_get_missing_record(self, store):
        assert store.get_idempotency_record("nonexistent") is None

    def test_token_exists_elsewhere_true(self, store):
        record = IdempotencyRecord(
            key="start_review::tok-1",
            tool="start_review",
            session_id=None,
            token="tok-1",
            result_snapshot="{}",
            created_at=datetime.now(timezone.utc),
        )
        store.save_idempotency_record(record)
        # Token tok-1 exists under start_review::tok-1, checking from different key
        assert store.token_exists_elsewhere("tok-1", "discuss:sess-1:tok-1") is True

    def test_token_exists_elsewhere_false_same_key(self, store):
        record = IdempotencyRecord(
            key="start_review::tok-1",
            tool="start_review",
            session_id=None,
            token="tok-1",
            result_snapshot="{}",
            created_at=datetime.now(timezone.utc),
        )
        store.save_idempotency_record(record)
        # Same key — not "elsewhere"
        assert store.token_exists_elsewhere("tok-1", "start_review::tok-1") is False

    def test_token_exists_elsewhere_false_not_found(self, store):
        assert store.token_exists_elsewhere("tok-nonexistent", "any-key") is False
