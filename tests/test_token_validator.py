"""Tests for TokenValidator — T010 (RED).

Covers: validate_format(), _probe_github_auth(), validate_copilot_access(),
validate() orchestration. All 4 error types must assert message content and
remediation URLs per contracts/token-validator.md (AC-3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.token_validator import TokenValidationError, TokenValidator


@pytest.fixture
def mock_copilot():
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client._available_models = [{"id": "gpt-4o", "name": "gpt-4o"}]
    return client


@pytest.fixture
def validator(mock_copilot):
    return TokenValidator(copilot_client_factory=lambda: mock_copilot)


class TestValidateFormat:
    def test_accepts_fine_grained_pat(self, validator):
        """github_pat_ prefix accepted."""
        validator.validate_format("github_pat_1234567890abcdef")

    def test_rejects_empty(self, validator):
        """Empty string → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("")
        assert exc_info.value.error_type == "format"
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_whitespace_only(self, validator):
        """Whitespace-only → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("   ")
        assert exc_info.value.error_type == "format"
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_classic_pat(self, validator):
        """ghp_ prefix → format error identifying classic PAT with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("ghp_1234567890abcdef")
        assert exc_info.value.error_type == "format"
        assert "Classic PATs" in exc_info.value.message
        assert "ghp_" in exc_info.value.message
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_oauth_token(self, validator):
        """gho_ prefix → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("gho_1234567890abcdef")
        assert exc_info.value.error_type == "format"
        assert "OAuth" in exc_info.value.message
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_ghs_token(self, validator):
        """ghs_ prefix → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("ghs_1234567890abcdef")
        assert exc_info.value.error_type == "format"
        assert "GitHub App" in exc_info.value.message
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_ghu_token(self, validator):
        """ghu_ prefix → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("ghu_1234567890abcdef")
        assert exc_info.value.error_type == "format"
        assert "GitHub App" in exc_info.value.message
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message

    def test_rejects_unrecognized_format(self, validator):
        """Unknown format → format error with URL."""
        with pytest.raises(TokenValidationError) as exc_info:
            validator.validate_format("some_random_token")
        assert exc_info.value.error_type == "format"
        assert "github_pat_" in exc_info.value.message
        assert "github.com/settings/tokens?type=beta" in exc_info.value.message


class TestProbeGithubAuth:
    @pytest.mark.asyncio
    async def test_returns_true_on_2xx(self, validator):
        """GET /user 200 → True (auth confirmed)."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 200
            result = await validator._probe_github_auth("github_pat_valid")
        assert result is True

    @pytest.mark.asyncio
    async def test_raises_auth_on_401(self, validator):
        """GET /user 401 → auth error with verbose message and URL."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 401
            with pytest.raises(TokenValidationError) as exc_info:
                await validator._probe_github_auth("github_pat_expired")
        assert exc_info.value.error_type == "auth"
        assert "expired or revoked" in exc_info.value.message
        assert "github.com/settings/tokens" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_returns_none_on_403(self, validator):
        """GET /user 403 → None (inconclusive)."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 403
            result = await validator._probe_github_auth("github_pat_test")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_500(self, validator):
        """GET /user 500 → None (inconclusive)."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 500
            result = await validator._probe_github_auth("github_pat_test")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self, validator):
        """Network error → None (inconclusive)."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.side_effect = OSError("connection refused")
            result = await validator._probe_github_auth("github_pat_test")
        assert result is None


class TestValidateCopilotAccess:
    @pytest.mark.asyncio
    async def test_success(self, validator, mock_copilot):
        """list_models() succeeds → no error raised."""
        await validator.validate_copilot_access("github_pat_valid", github_auth_confirmed=True)
        mock_copilot.start.assert_called_once()
        mock_copilot.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_error_when_auth_confirmed(self, validator, mock_copilot):
        """Confirmed auth + Copilot failure → permission error with verbose message and URL."""
        from server.copilot_client import CopilotAuthError
        mock_copilot.start.side_effect = CopilotAuthError("403 Forbidden")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=True)
        assert exc_info.value.error_type == "permission"
        assert "authenticates to GitHub but cannot access Copilot" in exc_info.value.message
        assert "github.com/settings/tokens" in exc_info.value.message
        assert "github.com/settings/copilot" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_auth_error_when_inconclusive(self, validator, mock_copilot):
        """Inconclusive probe + Copilot failure → auth error (combined) with verbose message and URL."""
        from server.copilot_client import CopilotAuthError
        mock_copilot.start.side_effect = CopilotAuthError("403 Forbidden")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=None)
        assert exc_info.value.error_type == "auth"
        assert "couldn't determine the exact cause" in exc_info.value.message
        assert "github.com/settings/tokens" in exc_info.value.message
        assert "github.com/settings/copilot" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_sdk_error_on_import_error(self, validator, mock_copilot):
        """ImportError → sdk error with verbose message and URL."""
        mock_copilot.start.side_effect = ImportError("No module named 'copilot'")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=True)
        assert exc_info.value.error_type == "sdk"
        assert "container configuration issue" in exc_info.value.message
        assert "docker compose build --no-cache" in exc_info.value.message
        assert "docs.github.com/en/copilot" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_sdk_error_on_unavailable(self, validator, mock_copilot):
        """CopilotUnavailableError → sdk error with verbose message and URL."""
        from server.copilot_client import CopilotUnavailableError
        mock_copilot.start.side_effect = CopilotUnavailableError("CLI not found")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=True)
        assert exc_info.value.error_type == "sdk"
        assert "container configuration issue" in exc_info.value.message
        assert "docs.github.com/en/copilot" in exc_info.value.message


class TestValidateOrchestration:
    @pytest.mark.asyncio
    async def test_format_error_short_circuits(self, validator):
        """Format error stops validation before any network call."""
        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate("ghp_classic_token")
        assert exc_info.value.error_type == "format"

    @pytest.mark.asyncio
    async def test_auth_error_on_401_short_circuits(self, validator, mock_copilot):
        """401 from probe short-circuits before Copilot check."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 401
            with pytest.raises(TokenValidationError) as exc_info:
                await validator.validate("github_pat_expired")
        assert exc_info.value.error_type == "auth"
        mock_copilot.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_success(self, validator, mock_copilot):
        """Valid token passes all three steps."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 200
            await validator.validate("github_pat_valid_token")
        mock_copilot.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_inconclusive_probe_still_checks_copilot(self, validator, mock_copilot):
        """Inconclusive probe (non-401, non-2xx) → Copilot check still runs."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.return_value = 403
            await validator.validate("github_pat_valid_token")
        mock_copilot.start.assert_called_once()


class TestProbeGithubAuthNarrowCatch:
    @pytest.mark.asyncio
    async def test_non_network_error_propagates(self, validator):
        """Non-network errors (e.g. TypeError) must NOT be caught — they propagate."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.side_effect = TypeError("unexpected argument")
            with pytest.raises(TypeError, match="unexpected argument"):
                await validator._probe_github_auth("github_pat_test")

    @pytest.mark.asyncio
    async def test_attribute_error_propagates(self, validator):
        """AttributeError must NOT be caught — it indicates a bug."""
        with patch("server.token_validator._http_get_status") as mock_get:
            mock_get.side_effect = AttributeError("bad attribute")
            with pytest.raises(AttributeError, match="bad attribute"):
                await validator._probe_github_auth("github_pat_test")


class TestValidateCopilotAccessUnexpectedError:
    @pytest.mark.asyncio
    async def test_unexpected_runtime_error_raises_unknown(self, validator, mock_copilot):
        """Unexpected RuntimeError → TokenValidationError with error_type='unknown'."""
        mock_copilot.start.side_effect = RuntimeError("something broke")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=True)
        assert exc_info.value.error_type == "unknown"
        assert "unexpected error" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_unexpected_os_error_raises_unknown(self, validator, mock_copilot):
        """Unexpected OSError → TokenValidationError with error_type='unknown'."""
        mock_copilot.start.side_effect = OSError("disk failure")

        with pytest.raises(TokenValidationError) as exc_info:
            await validator.validate_copilot_access("github_pat_test", github_auth_confirmed=None)
        assert exc_info.value.error_type == "unknown"
        assert "Check container logs" in exc_info.value.message
