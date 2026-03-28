"""Tests for MCP server configuration and startup — Issue #14, M-1."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.copilot_client import (
    CopilotAuthError,
    CopilotUnavailableError,
    NoCredentialError,
)
from server.credential_resolver import CredentialSource, ResolvedCredential
from server.mcp_server import _initialize_copilot, _parse_timeout


class TestParseTimeout:
    """AC-5, AC-6: Env var parsing for timeout configuration."""

    def test_valid_value(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "180")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 180.0

    def test_valid_float_value(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "90.5")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 90.5

    def test_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("REVIEW_TIMEOUT", raising=False)
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_negative_value_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "-5")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_zero_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "0")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_non_numeric_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "abc")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_inf_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "inf")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_large_exponent_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "1e999")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_negative_inf_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "-inf")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_nan_returns_default(self, monkeypatch):
        monkeypatch.setenv("REVIEW_TIMEOUT", "nan")
        assert _parse_timeout("REVIEW_TIMEOUT", 120.0) == 120.0

    def test_discuss_timeout_env_var(self, monkeypatch):
        monkeypatch.setenv("DISCUSS_TIMEOUT", "45")
        assert _parse_timeout("DISCUSS_TIMEOUT", 60.0) == 45.0

    def test_discuss_timeout_invalid_returns_default(self, monkeypatch):
        monkeypatch.setenv("DISCUSS_TIMEOUT", "nope")
        assert _parse_timeout("DISCUSS_TIMEOUT", 60.0) == 60.0


# --- _initialize_copilot() tests (M-1: mcp_server.py:90-111 coverage) ---


@pytest.fixture
def mock_copilot():
    """Replace module-level _copilot with a mock."""
    copilot = AsyncMock()
    copilot._startup_error = None
    copilot.is_connected = True

    def _set_startup_error(error):
        copilot._startup_error = error

    copilot.set_startup_error = _set_startup_error
    with patch("server.mcp_server._copilot", copilot):
        yield copilot


def _patch_resolver(resolve_return):
    """Patch CredentialStore + CredentialResolver so resolve() returns the given value."""
    mock_cls = MagicMock()
    mock_cls.return_value.resolve.return_value = resolve_return
    return (
        patch("server.mcp_server.CredentialStore"),
        patch("server.mcp_server.CredentialResolver", mock_cls),
    )


class TestInitializeCopilotNoCredential:
    """resolve() -> None sets NoCredentialError with all 3 remediation paths."""

    @pytest.mark.asyncio
    async def test_sets_no_credential_error(self, mock_copilot):
        p1, p2 = _patch_resolver(None)
        with p1, p2:
            await _initialize_copilot()

        assert isinstance(mock_copilot._startup_error, NoCredentialError)

    @pytest.mark.asyncio
    async def test_message_contains_web_ui_path(self, mock_copilot):
        p1, p2 = _patch_resolver(None)
        with p1, p2:
            await _initialize_copilot()

        assert "localhost:8080" in str(mock_copilot._startup_error)

    @pytest.mark.asyncio
    async def test_message_contains_env_var_path(self, mock_copilot):
        p1, p2 = _patch_resolver(None)
        with p1, p2:
            await _initialize_copilot()

        assert "GITHUB_TOKEN" in str(mock_copilot._startup_error)

    @pytest.mark.asyncio
    async def test_message_contains_docker_secret_path(self, mock_copilot):
        p1, p2 = _patch_resolver(None)
        with p1, p2:
            await _initialize_copilot()

        assert "/run/secrets/github_token" in str(mock_copilot._startup_error)

    @pytest.mark.asyncio
    async def test_copilot_start_not_called(self, mock_copilot):
        p1, p2 = _patch_resolver(None)
        with p1, p2:
            await _initialize_copilot()

        mock_copilot.start.assert_not_called()


class TestInitializeCopilotWithToken:
    """resolve() -> token passes that token into _copilot.start()."""

    @pytest.mark.asyncio
    async def test_token_passed_to_start(self, mock_copilot):
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        mock_copilot.start.assert_awaited_once_with(github_token="github_pat_abc123")

    @pytest.mark.asyncio
    async def test_select_model_not_called_redundantly(self, mock_copilot):
        """I-6: select_model() is handled internally by start(), not called again."""
        mock_copilot.is_connected = True
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        mock_copilot.select_model.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_startup_error_on_success(self, mock_copilot):
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        assert mock_copilot._startup_error is None

    @pytest.mark.asyncio
    async def test_copilot_error_stored_on_start_failure(self, mock_copilot):
        mock_copilot.start.side_effect = CopilotAuthError("bad token")
        cred = ResolvedCredential(token="github_pat_bad", source=CredentialSource.ENV_VAR)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        assert isinstance(mock_copilot._startup_error, CopilotAuthError)

    @pytest.mark.asyncio
    async def test_not_connected_after_start_sets_unavailable(self, mock_copilot):
        """Post-start is_connected=False sets CopilotUnavailableError."""
        mock_copilot.is_connected = False
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()
        assert isinstance(mock_copilot._startup_error, CopilotUnavailableError)
        assert "not available" in str(mock_copilot._startup_error).lower()


class TestInitializeCopilotRotation:
    """Fresh _initialize_copilot() after rotation picks up the new token."""

    @pytest.mark.asyncio
    async def test_second_init_uses_rotated_token(self, mock_copilot):
        old_cred = ResolvedCredential(token="github_pat_OLD", source=CredentialSource.STORED)
        new_cred = ResolvedCredential(token="github_pat_NEW", source=CredentialSource.STORED)

        # First call: old token
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve.return_value = old_cred
        with patch("server.mcp_server.CredentialStore"), \
             patch("server.mcp_server.CredentialResolver", resolver_cls):
            await _initialize_copilot()
        mock_copilot.start.assert_awaited_with(github_token="github_pat_OLD")

        # Simulate rotation: second call picks up new token
        resolver_cls2 = MagicMock()
        resolver_cls2.return_value.resolve.return_value = new_cred
        with patch("server.mcp_server.CredentialStore"), \
             patch("server.mcp_server.CredentialResolver", resolver_cls2):
            await _initialize_copilot()
        mock_copilot.start.assert_awaited_with(github_token="github_pat_NEW")

    @pytest.mark.asyncio
    async def test_rotation_creates_fresh_resolver(self, mock_copilot):
        """Each _initialize_copilot() call creates a new CredentialResolver."""
        cred = ResolvedCredential(token="github_pat_X", source=CredentialSource.STORED)
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve.return_value = cred

        with patch("server.mcp_server.CredentialStore") as store_cls, \
             patch("server.mcp_server.CredentialResolver", resolver_cls):
            await _initialize_copilot()
            await _initialize_copilot()

        # Two calls = two fresh CredentialStore + CredentialResolver instances
        assert store_cls.call_count == 2
        assert resolver_cls.call_count == 2


class TestInitializeCopilotNonCopilotError:
    """C-2: Non-CopilotError exceptions are logged and wrapped."""

    @pytest.mark.asyncio
    async def test_runtime_error_stored_as_unavailable(self, mock_copilot):
        """RuntimeError during start() is wrapped in CopilotUnavailableError."""
        mock_copilot.start.side_effect = RuntimeError("segfault in SDK")
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        assert isinstance(mock_copilot._startup_error, CopilotUnavailableError)
        assert "RuntimeError" in str(mock_copilot._startup_error)
        # Raw exception text must NOT leak into user-facing error (security)
        assert "segfault in SDK" not in str(mock_copilot._startup_error)

    @pytest.mark.asyncio
    async def test_runtime_error_logged(self, mock_copilot, caplog):
        """RuntimeError during start() is logged at ERROR level."""
        mock_copilot.start.side_effect = RuntimeError("segfault in SDK")
        cred = ResolvedCredential(token="github_pat_abc123", source=CredentialSource.STORED)
        p1, p2 = _patch_resolver(cred)
        with p1, p2, caplog.at_level(logging.ERROR, logger="server.mcp_server"):
            await _initialize_copilot()

        assert any("Unexpected error during Copilot initialization" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_copilot_error_still_stored_directly(self, mock_copilot):
        """CopilotAuthError is still stored as-is (not wrapped)."""
        mock_copilot.start.side_effect = CopilotAuthError("bad token")
        cred = ResolvedCredential(token="github_pat_bad", source=CredentialSource.ENV_VAR)
        p1, p2 = _patch_resolver(cred)
        with p1, p2:
            await _initialize_copilot()

        assert isinstance(mock_copilot._startup_error, CopilotAuthError)
        assert "bad token" in str(mock_copilot._startup_error)


class TestInitializeCopilotResolverFailure:
    """C-2/Finding 14: resolver.resolve() OSError is caught separately."""

    @pytest.mark.asyncio
    async def test_resolver_oserror_stored_as_unavailable(self, mock_copilot):
        """OSError from resolver.resolve() is wrapped in CopilotUnavailableError."""
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve.side_effect = OSError("disk read failed")
        with patch("server.mcp_server.CredentialStore"), \
             patch("server.mcp_server.CredentialResolver", resolver_cls):
            await _initialize_copilot()

        assert isinstance(mock_copilot._startup_error, CopilotUnavailableError)
        assert "OSError" in str(mock_copilot._startup_error)
        # Raw exception text must NOT leak into user-facing error (security)
        assert "disk read failed" not in str(mock_copilot._startup_error)

    @pytest.mark.asyncio
    async def test_resolver_oserror_logged(self, mock_copilot, caplog):
        """OSError from resolver.resolve() is logged at ERROR level."""
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve.side_effect = OSError("disk read failed")
        with patch("server.mcp_server.CredentialStore"), \
             patch("server.mcp_server.CredentialResolver", resolver_cls), \
             caplog.at_level(logging.ERROR, logger="server.mcp_server"):
            await _initialize_copilot()

        assert any("Credential resolver failed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_resolver_oserror_does_not_call_start(self, mock_copilot):
        """When resolver crashes, start() is never called."""
        resolver_cls = MagicMock()
        resolver_cls.return_value.resolve.side_effect = OSError("disk read failed")
        with patch("server.mcp_server.CredentialStore"), \
             patch("server.mcp_server.CredentialResolver", resolver_cls):
            await _initialize_copilot()

        mock_copilot.start.assert_not_called()
