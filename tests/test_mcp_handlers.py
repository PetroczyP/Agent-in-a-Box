"""Tests for MCP tool handler logic — test phase coverage for server/mcp_server.py.

Exercises the actual handler functions with mocked engine to verify error mapping,
response shapes, and edge cases from spec edge case section.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from server.copilot_client import (
    CopilotAuthError,
    CopilotRateLimitError,
    CopilotTimeoutError,
    CopilotUnavailableError,
    NoCredentialError,
)
from server.models import (
    DiscussResult,
    ReviewResult,
    ReviewSummary,
    SessionList,
)
from server.review_engine import BundleTooLargeError, ContentDeniedError


@pytest.fixture
def mock_engine():
    engine = AsyncMock()
    engine.start_review = AsyncMock()
    engine.discuss = AsyncMock()
    engine.get_summary = AsyncMock()
    engine.list_sessions = AsyncMock()
    return engine


@pytest.fixture
def _patch_engine(mock_engine):
    """Patch the module-level _engine in mcp_server."""
    with patch("server.mcp_server._engine", mock_engine):
        yield mock_engine


class TestStartReviewHandler:
    @pytest.mark.asyncio
    async def test_success_returns_model_dump(self, _patch_engine):
        from server.mcp_server import start_review

        result = ReviewResult(
            session_id="s-1",
            findings=[],
            finding_count=0,
            severity_summary={},
            model="gpt-4o",
        )
        _patch_engine.start_review.return_value = result

        response = await start_review(
            diff="--- a/f.py\n+++ b/f.py\n",
            files={"f.py": "pass"},
        )
        assert response["session_id"] == "s-1"
        assert response["findings"] == []

    @pytest.mark.asyncio
    async def test_content_denied_error(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = ContentDeniedError(
            denied_files=[".env", "secret.key"]
        )

        response = await start_review(
            diff="--- a/.env\n+++ b/.env\n",
            files={".env": "SECRET=x"},
        )
        assert response["error"] == "content_denied"
        assert response["denied_files"] == [".env", "secret.key"]
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_bundle_too_large_error(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = BundleTooLargeError(
            bundle_size=500000,
            model_limit=200000,
        )

        response = await start_review(
            diff="huge diff",
            files={"big.py": "x" * 500000},
        )
        assert response["error"] == "bundle_too_large"
        assert response["bundle_size"] == 500000
        assert response["model_limit"] == 200000
        assert "guidance" in response
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_empty_diff_error(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = ValueError("empty_diff")

        response = await start_review(diff="", files={"f.py": "pass"})
        assert response["error"] == "empty_diff"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_idempotency_conflict_error(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = ValueError(
            "idempotency_conflict: token reused"
        )

        response = await start_review(
            diff="d",
            files={"f.py": "pass"},
            idempotency_token="tok-1",
        )
        assert response["error"] == "idempotency_conflict"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_auth_error_maps_correctly(self, _patch_engine):
        """Spec edge case: terminal error (auth revoked) → auth_failed."""
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = CopilotAuthError("bad token")

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "auth_failed"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_timeout_error_maps_correctly(self, _patch_engine):
        """Spec edge case: transient error → retryable."""
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = CopilotTimeoutError("timed out")

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "timeout"
        assert response["retryable"] is True

    @pytest.mark.asyncio
    async def test_rate_limit_error_maps_correctly(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = CopilotRateLimitError("429")

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "rate_limited"
        assert response["retryable"] is True

    @pytest.mark.asyncio
    async def test_unavailable_error_maps_correctly(self, _patch_engine):
        """FR-013: terminal unavailable error must not fall through to internal."""
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = CopilotUnavailableError("model unavailable")

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "unavailable"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_no_credential_error_maps_correctly(self, _patch_engine):
        """NoCredentialError must map to no_credential, not fall through to internal."""
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = NoCredentialError(
            "No credential configured. Set up a token at localhost:8080, "
            "provide GITHUB_TOKEN env var, or mount a Docker secret at "
            "/run/secrets/github_token."
        )

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "no_credential"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_unknown_error_maps_to_internal(self, _patch_engine):
        from server.mcp_server import start_review

        _patch_engine.start_review.side_effect = RuntimeError("unexpected")

        response = await start_review(diff="d", files={"f.py": "pass"})
        assert response["error"] == "internal"


class TestDiscussHandler:
    @pytest.mark.asyncio
    async def test_success(self, _patch_engine):
        from server.mcp_server import discuss

        result = DiscussResult(
            response="Agreed, fixing.",
            updated_findings=[],
            finding_count_by_status={"open": 0},
        )
        _patch_engine.discuss.return_value = result

        response = await discuss(session_id="s-1", message="I disagree with F-001")
        assert response["response"] == "Agreed, fixing."

    @pytest.mark.asyncio
    async def test_session_not_found(self, _patch_engine):
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = ValueError("session_not_found")

        response = await discuss(session_id="bad-id", message="hello")
        assert response["error"] == "session_not_found"

    @pytest.mark.asyncio
    async def test_session_not_active(self, _patch_engine):
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = ValueError("session_not_active")

        response = await discuss(session_id="s-1", message="hello")
        assert response["error"] == "session_not_active"

    @pytest.mark.asyncio
    async def test_discuss_content_denied(self, _patch_engine):
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = ContentDeniedError(
            denied_files=[".env"]
        )

        response = await discuss(
            session_id="s-1",
            message="check this",
            additional_files={".env": "SECRET=x"},
        )
        assert response["error"] == "content_denied"

    @pytest.mark.asyncio
    async def test_discuss_timeout(self, _patch_engine):
        """Spec edge case: transient error mid-conversation."""
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = CopilotTimeoutError("timed out")

        response = await discuss(session_id="s-1", message="hello")
        assert response["error"] == "timeout"
        assert response["retryable"] is True

    @pytest.mark.asyncio
    async def test_discuss_rate_limit(self, _patch_engine):
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = CopilotRateLimitError("429")

        response = await discuss(session_id="s-1", message="hello")
        assert response["error"] == "rate_limited"
        assert response["retryable"] is True

    @pytest.mark.asyncio
    async def test_discuss_auth_error(self, _patch_engine):
        """H-1: Terminal auth error mid-conversation must map to auth_failed, not internal."""
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = CopilotAuthError("bad token")

        response = await discuss(session_id="s-1", message="hello")
        assert response["error"] == "auth_failed"
        assert response["retryable"] is False

    @pytest.mark.asyncio
    async def test_discuss_unavailable_error(self, _patch_engine):
        """H-1: Terminal unavailable error mid-conversation must map to unavailable, not internal."""
        from server.mcp_server import discuss

        _patch_engine.discuss.side_effect = CopilotUnavailableError("model unavailable")

        response = await discuss(session_id="s-1", message="hello")
        assert response["error"] == "unavailable"
        assert response["retryable"] is False


class TestGetReviewSummaryHandler:
    @pytest.mark.asyncio
    async def test_success(self, _patch_engine):
        from server.mcp_server import get_review_summary

        result = ReviewSummary(
            session_id="s-1",
            status="active",
            model="gpt-4o",
            round_count=1,
            findings=[],
            finding_count=0,
            by_severity={},
            by_category={},
            by_status={},
        )
        _patch_engine.get_summary.return_value = result

        response = await get_review_summary(session_id="s-1")
        assert response["finding_count"] == 0

    @pytest.mark.asyncio
    async def test_session_not_found(self, _patch_engine):
        from server.mcp_server import get_review_summary

        _patch_engine.get_summary.side_effect = ValueError("session_not_found")

        response = await get_review_summary(session_id="bad-id")
        assert response["error"] == "session_not_found"


class TestListSessionsHandler:
    @pytest.mark.asyncio
    async def test_success(self, _patch_engine):
        from server.mcp_server import list_sessions

        result = SessionList(sessions=[])
        _patch_engine.list_sessions.return_value = result

        response = await list_sessions()
        assert response["sessions"] == []
